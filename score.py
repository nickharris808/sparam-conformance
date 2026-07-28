"""Score any S-parameter physical-validity checker against the corpus.

The metric is deliberately NOT a single accuracy number. A checker has two
independent ways to be wrong and they carry very different costs:

  FALSE PASS   the checker admits a non-physical network.
               This is the one that ships a broken model downstream.

  FALSE FAIL   the checker rejects a realizable network.
               Annoying, erodes trust, but nothing bad reaches a simulator.

So both are reported, per law, and the headline verdict requires ZERO false
passes. A checker that flags everything has no false passes and is useless --
which is why the false-fail count sits beside it, exactly as in the
abstain-bench design.

Adapter contract: point --checker at `module:function` where the function takes
a Touchstone path and returns {law_name: bool_passed}.

Usage:
    python score.py --checker sparam_lint_adapter:check
    python score.py --checker mypkg.mychecker:run --json
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"


def load_manifest(data_dir: Path = DATA) -> dict:
    mf = data_dir / "manifest.json"
    if not mf.exists():
        raise SystemExit(f"no manifest at {mf} -- run generate.py first")
    return json.loads(mf.read_text())


def _load_checker(spec: str):
    if ":" not in spec:
        raise ValueError(f"expected 'module:function', got {spec!r}")
    mod, fn = spec.split(":", 1)
    f = getattr(importlib.import_module(mod), fn, None)
    if f is None or not callable(f):
        raise ValueError(f"{mod} has no callable {fn!r}")
    return f


def score(checker, manifest: dict, data_dir: Path = DATA) -> dict:
    laws = manifest["laws"]
    per_case = []
    false_pass = 0
    false_fail = 0
    errors = 0
    per_law = {law: {"false_pass": 0, "false_fail": 0, "correct": 0} for law in laws}

    for c in manifest["cases"]:
        path = data_dir / c["file"]
        try:
            got = checker(str(path))
        except Exception as exc:  # noqa: BLE001
            errors += 1
            per_case.append({"name": c["name"], "error": f"{type(exc).__name__}: {exc}"})
            continue

        if not isinstance(got, dict):
            errors += 1
            per_case.append({"name": c["name"],
                             "error": f"checker returned {type(got).__name__}, expected dict"})
            continue

        case_fp, case_ff, missing = [], [], []
        for law in laws:
            if law not in got:
                missing.append(law)
                continue
            expected = c["expect"][law]
            actual = bool(got[law])
            if actual == expected:
                per_law[law]["correct"] += 1
            elif actual and not expected:
                per_law[law]["false_pass"] += 1
                case_fp.append(law)
            else:
                per_law[law]["false_fail"] += 1
                case_ff.append(law)

        false_pass += len(case_fp)
        false_fail += len(case_ff)
        per_case.append({
            "name": c["name"],
            "physical": c["physical"],
            "false_pass_laws": case_fp,
            "false_fail_laws": case_ff,
            "missing_laws": missing,
            "correct": not case_fp and not case_ff and not missing,
        })

    n_law_checks = len(manifest["cases"]) * len(laws)
    return {
        "corpus_version": manifest["version"],
        "n_cases": len(manifest["cases"]),
        "n_law_checks": n_law_checks,
        "false_pass": false_pass,
        "false_fail": false_fail,
        "checker_errors": errors,
        "per_law": per_law,
        "per_case": per_case,
        "passed": false_pass == 0 and errors == 0,
        "verdict_rule": (
            "A conforming checker has ZERO false passes and ZERO errors. "
            "False fails are reported but do not fail the verdict, because a "
            "conservative checker is safe; a permissive one is not."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score a checker against sparam-conformance.")
    ap.add_argument("--checker", required=True, help="module:function")
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    data_dir = Path(args.data)
    manifest = load_manifest(data_dir)
    try:
        checker = _load_checker(args.checker)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = score(checker, manifest, data_dir)
    result["checker"] = args.checker

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"sparam-conformance v{result['corpus_version']}  "
              f"{result['n_cases']} cases x {len(manifest['laws'])} laws")
        print()
        for c in result["per_case"]:
            if "error" in c:
                print(f"  [ERR ] {c['name']:<22} {c['error']}")
            elif c["correct"]:
                print(f"  [ OK ] {c['name']}")
            else:
                bits = []
                if c["false_pass_laws"]:
                    bits.append("FALSE PASS: " + ", ".join(c["false_pass_laws"]))
                if c["false_fail_laws"]:
                    bits.append("false fail: " + ", ".join(c["false_fail_laws"]))
                if c["missing_laws"]:
                    bits.append("not reported: " + ", ".join(c["missing_laws"]))
                print(f"  [FAIL] {c['name']:<22} {'; '.join(bits)}")
        print()
        print(f"  false passes : {result['false_pass']}   <- must be 0")
        print(f"  false fails  : {result['false_fail']}")
        print(f"  errors       : {result['checker_errors']}")
        print(f"  verdict      : {'CONFORMING' if result['passed'] else 'NOT CONFORMING'}")

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
