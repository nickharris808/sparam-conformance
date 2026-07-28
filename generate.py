"""Generate the sparam-conformance corpus.

A labelled set of S-parameter networks with ground-truth physical verdicts.
Every case is synthesised from a closed-form model, so the label is derived
from construction rather than asserted -- we know a network is non-passive
because we built it that way, not because a checker said so.

Run:  python generate.py [--out data]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

FREQ = np.linspace(1e9, 40e9, 64)

# The five laws, in the order every checker should report them.
LAWS = ("passivity", "reciprocity", "energy_conservation",
        "positive_real_z0", "group_delay_nonneg")


@dataclass
class Case:
    name: str
    s: np.ndarray
    freq: np.ndarray
    z0: float
    expect: dict[str, bool]          # law -> should_pass
    physical: bool                    # is this a realizable passive device?
    note: str
    tags: list[str] = field(default_factory=list)


def _line(loss_db=0.5, delay_s=20e-12, refl=0.05):
    amp = 10.0 ** (-abs(loss_db) / 20.0)
    s21 = amp * np.exp(-1j * 2 * np.pi * FREQ * delay_s)
    s = np.zeros((len(FREQ), 2, 2), dtype=complex)
    s[:, 0, 0] = s[:, 1, 1] = refl
    s[:, 0, 1] = s[:, 1, 0] = s21
    return s


def _resonator(f0=20e9, q=30.0, delay_s=10e-12):
    """A passive shunt resonator: sharp phase, still causal and passive."""
    x = (FREQ / f0) - (f0 / FREQ)
    denom = 1.0 + 1j * q * x
    s21 = (1.0 / denom) * np.exp(-1j * 2 * np.pi * FREQ * delay_s)
    s11 = 1.0 - 1.0 / denom
    s = np.zeros((len(FREQ), 2, 2), dtype=complex)
    s[:, 0, 0] = s[:, 1, 1] = s11
    s[:, 0, 1] = s[:, 1, 0] = s21
    # A resonator built naively from these closed forms is NOT passive -- the
    # 2x2 spectral norm exceeds 1 near resonance. Normalise by the worst
    # singular value so the network genuinely satisfies the law its label
    # claims. A corpus whose "passive" case is not passive is worse than no
    # corpus at all.
    worst = max(np.linalg.svd(m, compute_uv=False)[0] for m in s)
    return s * (0.98 / worst)


def _attenuator(db=10.0):
    a = 10.0 ** (-db / 20.0)
    s = np.zeros((len(FREQ), 2, 2), dtype=complex)
    s[:, 0, 1] = s[:, 1, 0] = a
    return s


def _matched_load():
    return np.zeros((len(FREQ), 2, 2), dtype=complex)


def _marginal_passive():
    """sigma_max just below 1 -- a lossless line. Must PASS."""
    s21 = np.exp(-1j * 2 * np.pi * FREQ * 15e-12) * (1.0 - 1e-12)
    s = np.zeros((len(FREQ), 2, 2), dtype=complex)
    s[:, 0, 1] = s[:, 1, 0] = s21
    return s


def _thru_4port():
    """Two independent thru paths: 1-2 and 3-4. Passive and reciprocal."""
    n = len(FREQ)
    s = np.zeros((n, 4, 4), dtype=complex)
    a = 0.9 * np.exp(-1j * 2 * np.pi * FREQ * 12e-12)
    s[:, 0, 1] = s[:, 1, 0] = a
    s[:, 2, 3] = s[:, 3, 2] = a
    return s


def build_cases() -> list[Case]:
    ok = {law: True for law in LAWS}
    cases: list[Case] = []

    # ---------- physically realizable: everything must pass ----------
    cases.append(Case(
        "passive_line", _line(), FREQ, 50.0, dict(ok), True,
        "Lossy 20 ps delay line, 0.5 dB insertion loss. The baseline sane case.",
        ["passive", "2port"]))

    cases.append(Case(
        "passive_resonator", _resonator(), FREQ, 50.0, dict(ok), True,
        "Shunt resonator, Q=30 at 20 GHz. Sharp phase slope near resonance -- "
        "the case where a group-delay check without phase unwrapping fails.",
        ["passive", "2port", "sharp_phase"]))

    cases.append(Case(
        "passive_attenuator", _attenuator(), FREQ, 50.0, dict(ok), True,
        "Ideal 10 dB matched attenuator.", ["passive", "2port"]))

    cases.append(Case(
        "matched_load", _matched_load(), FREQ, 50.0, dict(ok), True,
        "All-zero S: perfectly matched, fully absorbing. A degenerate but "
        "legal network; checkers that divide by |S| must not blow up.",
        ["passive", "2port", "degenerate"]))

    cases.append(Case(
        "marginal_lossless", _marginal_passive(), FREQ, 50.0, dict(ok), True,
        "Lossless line with sigma_max = 1 - 1e-12. Sits on the passivity "
        "boundary; a checker with a too-tight tolerance false-alarms here.",
        ["passive", "2port", "boundary"]))

    cases.append(Case(
        "passive_4port", _thru_4port(), FREQ, 50.0, dict(ok), True,
        "Four-port with two independent thru paths. Exercises N>2 handling.",
        ["passive", "4port"]))

    # ---------- non-physical: exactly one law must fail ----------
    s = _line()
    s[:, 0, 1] *= 3.0
    s[:, 1, 0] *= 3.0
    cases.append(Case(
        "active_gain", s, FREQ, 50.0,
        {**ok, "passivity": False, "energy_conservation": False}, False,
        "Delay line with 3x through-path gain. Creates energy: fails both the "
        "spectral-norm and the row-power tests.", ["nonphysical", "2port"]))

    s = _line()
    s[:, 0, 0] = s[:, 1, 1] = 0.9
    s[:, 0, 1] = s[:, 1, 0] = 0.9
    cases.append(Case(
        "energy_row_violation", s, FREQ, 50.0,
        {**ok, "passivity": False, "energy_conservation": False}, False,
        "Row power > 1 when port 1 is driven.", ["nonphysical", "2port"]))

    s = _line()
    s[:, 0, 0] = s[:, 1, 1] = -1.6
    cases.append(Case(
        "negative_resistance", s, FREQ, 50.0,
        {**ok, "passivity": False, "positive_real_z0": False,
         "energy_conservation": False}, False,
        "|S11| > 1 gives Re(Z_in) < 0: negative resistance at the port. It "
        "unavoidably breaks energy conservation too -- a reflection "
        "coefficient above unity returns more power than arrives -- so this "
        "case cannot isolate a single law, and the label says so.",
        ["nonphysical", "2port"]))

    s = _line()
    amp = np.abs(s[:, 0, 1])
    s[:, 0, 1] = s[:, 1, 0] = amp * np.exp(+1j * 2 * np.pi * FREQ * 20e-12)
    cases.append(Case(
        "noncausal_advance", s, FREQ, 50.0,
        {**ok, "group_delay_nonneg": False}, False,
        "Phase advances with frequency: the output precedes the input. "
        "Passive and reciprocal, so ONLY the causality check should fire.",
        ["nonphysical", "2port", "isolates_one_law"]))

    # ---------- real device that legitimately fails a law ----------
    s = _line()
    s[:, 0, 1] = s[:, 1, 0] * 0.02          # 34 dB isolation one way
    cases.append(Case(
        "ferrite_isolator", s, FREQ, 50.0,
        {**ok, "reciprocity": False}, True,
        "A ferrite isolator. NON-RECIPROCAL BY DESIGN and entirely realizable "
        "-- the medium is not reciprocal. The reciprocity check correctly "
        "fires, and that is a true positive for the law but NOT a defect in "
        "the device. Any tool reporting this must let the user say so.",
        ["physical", "2port", "expected_law_failure"]))

    return cases


def write_touchstone(path: Path, c: Case) -> None:
    n = c.s.shape[1]
    lines = [f"! {c.name}", f"! {c.note}", f"# HZ S RI R {c.z0:g}"]
    for fi, f in enumerate(c.freq):
        m = c.s[fi]
        if n == 2:                       # Touchstone 2-port: S11 S21 S12 S22
            vals = [m[0, 0], m[1, 0], m[0, 1], m[1, 1]]
        else:                            # N>=3: row-major
            vals = list(m.reshape(-1))
        lines.append(f"{f:.12g} " + " ".join(
            f"{v.real:.12g} {v.imag:.12g}" for v in vals))
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    args = ap.parse_args()
    out = Path(__file__).resolve().parent / args.out
    out.mkdir(parents=True, exist_ok=True)

    cases = build_cases()
    manifest = {
        "corpus": "sparam-conformance",
        "version": "1.0.0",
        "license": "CC-BY-4.0",
        "n_cases": len(cases),
        "laws": list(LAWS),
        "freq_hz": {"start": float(FREQ[0]), "stop": float(FREQ[-1]),
                    "n": int(len(FREQ))},
        "note": (
            "Every network is synthesised from a closed-form model, so each "
            "label is derived from construction rather than from a checker's "
            "opinion. 'physical' marks whether the device is realizable; a "
            "device can be physical AND legitimately fail a law -- see "
            "ferrite_isolator."
        ),
        "cases": [],
    }

    for c in cases:
        n = c.s.shape[1]
        fname = f"{c.name}.s{n}p"
        write_touchstone(out / fname, c)
        digest = hashlib.sha256((out / fname).read_bytes()).hexdigest()
        manifest["cases"].append({
            "name": c.name,
            "file": fname,
            "n_ports": n,
            "z0_ohm": c.z0,
            "physical": c.physical,
            "expect": c.expect,
            "expect_all_pass": all(c.expect.values()),
            "note": c.note,
            "tags": c.tags,
            "sha256": digest,
        })

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {len(cases)} cases + manifest.json to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
