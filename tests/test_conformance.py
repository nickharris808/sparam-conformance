"""Tests for the sparam-conformance corpus.

The load-bearing tests verify the LABELS, not the checker. A corpus whose
ground truth is wrong is worse than no corpus, because every checker scored
against it inherits the error. Each label is therefore re-derived here from
the network itself by independent linear algebra.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "sparam-lint" / "src"))

from sparam_lint import read_touchstone  # noqa: E402

from generate import LAWS  # noqa: E402
from score import load_manifest, score  # noqa: E402

DATA = HERE / "data"
MANIFEST = load_manifest(DATA)


def _read(name):
    case = next(c for c in MANIFEST["cases"] if c["name"] == name)
    return read_touchstone(DATA / case["file"]), case


# --------------------------------------------------- labels re-derived, not trusted

@pytest.mark.parametrize("case", MANIFEST["cases"], ids=lambda c: c["name"])
def test_passivity_label_matches_independent_svd(case):
    net = read_touchstone(DATA / case["file"])
    sig = max(np.linalg.svd(m, compute_uv=False)[0] for m in net.s)
    assert case["expect"]["passivity"] == bool(sig <= 1.0 + 1e-9), (
        f"{case['name']}: label says passivity={case['expect']['passivity']} "
        f"but sigma_max={sig:.6f}"
    )


@pytest.mark.parametrize("case", MANIFEST["cases"], ids=lambda c: c["name"])
def test_reciprocity_label_matches_independent_asymmetry(case):
    net = read_touchstone(DATA / case["file"])
    asym = max(
        np.linalg.norm(m - m.T, "fro") / max(np.linalg.norm(m, "fro"), 1e-300)
        for m in net.s
    )
    assert case["expect"]["reciprocity"] == bool(asym <= 1e-6), (
        f"{case['name']}: label says reciprocity={case['expect']['reciprocity']} "
        f"but asymmetry={asym:.3e}"
    )


@pytest.mark.parametrize("case", MANIFEST["cases"], ids=lambda c: c["name"])
def test_energy_label_matches_independent_row_power(case):
    net = read_touchstone(DATA / case["file"])
    rowp = max(np.sum(np.abs(m) ** 2, axis=1).max() for m in net.s)
    assert case["expect"]["energy_conservation"] == bool(rowp <= 1.0 + 1e-9), (
        f"{case['name']}: label says energy={case['expect']['energy_conservation']} "
        f"but max row power={rowp:.6f}"
    )


def test_physical_cases_pass_every_law_except_declared_exceptions():
    """A case marked physical must pass all five laws, unless it is explicitly
    tagged as a real device that legitimately fails one (e.g. an isolator)."""
    for c in MANIFEST["cases"]:
        if not c["physical"]:
            continue
        fails = [k for k, v in c["expect"].items() if not v]
        if fails:
            assert "expected_law_failure" in c["tags"], (
                f"{c['name']} is marked physical and fails {fails} but is not "
                "tagged expected_law_failure"
            )


def test_at_least_one_case_isolates_a_single_law():
    """Without an isolating case you cannot tell which check is alive."""
    isolating = [c for c in MANIFEST["cases"]
                 if sum(1 for v in c["expect"].values() if not v) == 1
                 and not c["physical"]]
    assert isolating, "corpus needs a case that breaks exactly one law"


def test_corpus_covers_every_law_in_both_directions():
    for law in LAWS:
        passes = [c for c in MANIFEST["cases"] if c["expect"][law]]
        fails = [c for c in MANIFEST["cases"] if not c["expect"][law]]
        assert passes, f"no case where {law} passes"
        assert fails, f"no case where {law} fails"


# ------------------------------------------------------------------- integrity

def test_files_match_recorded_hashes():
    for c in MANIFEST["cases"]:
        digest = hashlib.sha256((DATA / c["file"]).read_bytes()).hexdigest()
        assert digest == c["sha256"], f"{c['file']} changed since manifest was written"


def test_generation_is_deterministic(tmp_path):
    """Regenerating must reproduce byte-identical files."""
    subprocess.run([sys.executable, str(HERE / "generate.py"),
                    "--out", str(tmp_path)], check=True, cwd=HERE,
                   capture_output=True)
    for c in MANIFEST["cases"]:
        a = (DATA / c["file"]).read_bytes()
        b = (tmp_path / c["file"]).read_bytes()
        assert a == b, f"{c['file']} is not reproducible"


def test_multiport_case_present():
    ports = {c["n_ports"] for c in MANIFEST["cases"]}
    assert ports - {2}, "corpus must exercise N>2"


# ---------------------------------------------------------------------- scorer

def _perfect(path):
    case = next(c for c in MANIFEST["cases"] if c["file"] == Path(path).name)
    return dict(case["expect"])


def _always_pass(path):
    return {law: True for law in LAWS}


def _always_fail(path):
    return {law: False for law in LAWS}


def test_scorer_gives_perfect_checker_a_clean_sheet():
    r = score(_perfect, MANIFEST, DATA)
    assert r["false_pass"] == 0 and r["false_fail"] == 0 and r["passed"]


def test_scorer_catches_permissive_checker():
    """The one that matters: a checker that admits everything must NOT pass."""
    r = score(_always_pass, MANIFEST, DATA)
    assert r["false_pass"] > 0
    assert not r["passed"], "a permissive checker must never be CONFORMING"


def test_conservative_checker_has_no_false_passes_but_many_false_fails():
    r = score(_always_fail, MANIFEST, DATA)
    assert r["false_pass"] == 0
    assert r["false_fail"] > 0
    assert r["passed"], "a conservative checker is safe, so it conforms"


def test_scorer_records_checker_errors_without_crashing():
    def boom(path):
        raise RuntimeError("nope")

    r = score(boom, MANIFEST, DATA)
    assert r["checker_errors"] == len(MANIFEST["cases"])
    assert not r["passed"]


def test_scorer_rejects_wrong_return_type():
    r = score(lambda p: "not a dict", MANIFEST, DATA)
    assert r["checker_errors"] == len(MANIFEST["cases"])


def test_missing_law_is_reported_not_silently_passed():
    def partial(path):
        return {"passivity": True}

    r = score(partial, MANIFEST, DATA)
    assert all(c["missing_laws"] for c in r["per_case"])


# ------------------------------------------- the reference adapter really works

def test_reference_adapter_conforms():
    from sparam_lint_adapter import check
    r = score(check, MANIFEST, DATA)
    assert r["checker_errors"] == 0
    assert r["false_pass"] == 0, f"sparam-lint false passes: {r['per_case']}"
    assert r["passed"]
