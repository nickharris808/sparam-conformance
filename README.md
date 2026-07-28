---
license: cc-by-4.0
task_categories:
  - tabular-classification
tags:
  - rf
  - microwave
  - signal-integrity
  - s-parameters
  - touchstone
  - physics
  - validation
  - benchmark
pretty_name: S-Parameter Physical Conformance Corpus
size_categories:
  - n<1K
configs:
  - config_name: index
    data_files: data/index.jsonl
---

# sparam-conformance

![CI](https://github.com/nickharris808/sparam-conformance/actions/workflows/ci.yml/badge.svg) ![Licence](https://img.shields.io/badge/data-CC--BY--4.0-green) ![Cases](https://img.shields.io/badge/cases-11%20labelled-blue) ![Tests](https://img.shields.io/badge/tests-51%20passing-brightgreen)

**A labelled corpus of S-parameter networks with ground-truth physical verdicts —
and a scorer that grades any checker against it.**

There is no public dataset of *physically invalid* S-parameter files. Everyone
building an RF validation tool tests it on files that happen to be lying around,
which means nobody knows whether their checker catches the cases that matter.

This corpus is 11 networks, each **synthesised from a closed-form model**, so
every label is derived from construction rather than from some other tool's
opinion. We know `active_gain` is non-passive because we built 3× gain into it.

## 30-second quickstart

```bash
git clone https://github.com/nickharris808/sparam-conformance.git && cd sparam-conformance

python score.py --checker mypackage.mychecker:run     # grade your checker
python generate.py                                    # optional: rebuild the corpus
```

The corpus is committed, so scoring needs nothing installed beyond your own
checker. `generate.py` is only needed if you want to prove the files came from
the generator — it rebuilds them byte-identically, and CI checks that it does.

Adapter contract — five lines:

```python
from sparam_lint import read_touchstone, run_battery

def check(path: str) -> dict[str, bool]:
    net = read_touchstone(path)
    return {r.name: r.passed for r in run_battery(net.s, net.freq_hz, net.z0)}
```

## Baseline

```
$ python score.py --checker sparam_lint_adapter:check
sparam-conformance v1.0.0  11 cases x 5 laws

  [ OK ] passive_line
  [ OK ] passive_resonator
  ...
  [ OK ] ferrite_isolator

  false passes : 0   <- must be 0
  false fails  : 0
  errors       : 0
  verdict      : CONFORMING
```

## The metric, and why it is not one number

A checker has two independent ways to be wrong, with very different costs:

| | Meaning | Cost |
|---|---|---|
| **False pass** | admits a non-physical network | **the model ships** |
| **False fail** | rejects a realizable network | annoying, erodes trust, harms nothing |

So both are reported, per law, and **the verdict requires zero false passes**.
False fails are reported but do not fail the verdict.

There is a third state, because there is a third way to be wrong. A checker that
never reports a law has not passed it — it did not look. That is neither a false
pass nor a false fail, and calling it CONFORMING would be a verdict the corpus
did not earn, so it gets its own name:

| Verdict | Meaning | Exit |
|---|---|---|
| `CONFORMING` | every law reported on every case, zero false passes | `0` |
| `INCOMPLETE` | zero false passes, but at least one law was never reported | `1` |
| `NOT CONFORMING` | a false pass, or the adapter raised | `1` |

That asymmetry is deliberate and it has a consequence worth stating plainly: a
checker that rejects *everything* conforms. It has no false passes. It is also
useless — which is why the false-fail count sits beside the verdict, and why you
should read both. Optimising either number alone produces a bad tool.

## Contents

| Case | Ports | Physical? | Expected failures |
|---|---|---|---|
| `passive_line` | 2 | ✅ | — |
| `passive_resonator` | 2 | ✅ | — |
| `passive_attenuator` | 2 | ✅ | — |
| `matched_load` | 2 | ✅ | — |
| `marginal_lossless` | 2 | ✅ | — |
| `passive_4port` | 4 | ✅ | — |
| `active_gain` | 2 | ❌ | passivity, energy |
| `energy_row_violation` | 2 | ❌ | passivity, energy |
| `negative_resistance` | 2 | ❌ | passivity, energy, positive-real Z₀ |
| `noncausal_advance` | 2 | ❌ | group delay |
| `ferrite_isolator` | 2 | ✅ | **reciprocity** |

Several cases exist to catch specific checker bugs:

- **`passive_resonator`** — sharp phase slope at resonance. A group-delay check
  that differences phase without unwrapping reports spurious negative delay here.
- **`marginal_lossless`** — σ_max = 1 − 1e-12. A checker with a too-tight
  tolerance false-alarms on a perfectly legal lossless line.
- **`matched_load`** — all-zero S. Checkers that normalise by ‖S‖ divide by zero.
- **`passive_4port`** — exercises N>2, where Touchstone switches from
  column-major to row-major ordering.

## The case worth arguing about

**`ferrite_isolator` is physically realizable and fails reciprocity.**

A ferrite isolator is a real, buyable component. Its medium is non-reciprocal, so
`S ≠ Sᵀ` is correct behaviour, not a defect. The reciprocity check firing here is
a **true positive for the law and a false alarm for the device**.

The corpus keeps it because any honest tool has to handle this: a checker that
treats every law failure as a defect will reject legitimate hardware, and a
checker that suppresses reciprocity to avoid the noise goes blind to genuine
transpose bugs. The right answer is for the user to declare non-reciprocity
expected — and the corpus exists partly to force that design decision.

## Ground truth is verified, not asserted

Every label in `manifest.json` is re-derived from the network itself in the test
suite, by independent linear algebra — singular values for passivity, Frobenius
asymmetry for reciprocity, row power for energy. A corpus whose ground truth is
wrong is worse than no corpus, because every checker scored against it inherits
the error.

That check earned its place: it caught **three wrong labels** during development.
The "passive" resonator had σ_max = 1.2441 and was not passive at all; a case
meant to isolate energy was also non-reciprocal; and `negative_resistance`
unavoidably breaks energy conservation too, which the original label denied.

That 1.2441 is the one figure on this page you cannot reproduce from the
committed corpus — it belonged to a superseded generator revision, and the
resonator that ships today has σ_max ≤ 1, which the test suite asserts. It is
recorded because "we found bugs in our own ground truth" is worth more with a
number attached than without one.

Generation is deterministic, files are SHA-256 pinned in the manifest, and both
properties are tested.

## Scope, honestly

These are **synthetic closed-form networks**, not measured devices. They exercise
the laws and the specific bugs listed above; they are not a sample of what comes
out of a real VNA, and passing this corpus does not mean a checker is correct on
measured data with noise, drift and de-embedding artefacts.

11 cases is small. It is meant to be a conformance floor — a checker that fails
here is definitely broken; one that passes is merely not-obviously-broken.

Contributions of new pathological cases are the most useful thing you can send.

## A worked example: scoring a checker you just wrote

The corpus is committed, so this needs nothing installed except your checker.

**1 — write the adapter.** It maps your checker onto one dict per file: law name
to boolean.

```python
# mychecker_adapter.py
import mychecker

def check(path: str) -> dict[str, bool]:
    verdicts = mychecker.analyse(path)
    return {
        "passivity":          verdicts.passive,
        "reciprocity":        verdicts.reciprocal,
        "energy_conservation": verdicts.energy_ok,
        "positive_real_z0":   verdicts.z0_ok,
        "group_delay_nonneg": verdicts.causal,
    }
```

Names must match the corpus's law names — `laws` at the top of
`data/manifest.json` is the list. A law you do not implement is absent from the
dict, which the scorer reports as *not reported* and which makes the verdict
`INCOMPLETE`. It is never silently counted as a pass.

**2 — score it.**

```bash
$ python score.py --checker mychecker_adapter:check
```

**3 — read the two numbers separately.** False passes must be zero: each one is
a non-physical network your checker admitted, and admitting them is how a bad
model ships. False fails do not fail the verdict but they are not free — a
checker that rejects everything has zero false passes and no value.

The cases that most often catch a new checker, and what each one is testing:

| If you fail on | The bug is almost certainly |
|---|---|
| `passive_resonator` | differencing phase without unwrapping, so the sharp slope at resonance reads as negative group delay |
| `marginal_lossless` | a passivity tolerance too tight for σ_max = 1 − 1e-12 |
| `matched_load` | dividing by ‖S‖, which is zero for an all-zero S-matrix |
| `passive_4port` | assuming column-major everywhere; N ≥ 3 is row-major |
| `ferrite_isolator` | treating every reciprocity failure as a defect |

That last row is the judgement call rather than a bug, and it is why the corpus
keeps a physically-real device that legitimately fails a law.

## Troubleshooting

**`errors: 11` and every case failed** — the adapter raised. `score.py` reports
an error per case rather than crashing, so the message is in the output; the
usual cause is a checker that expects an open file object rather than a path.

**`false fails` is high on the passive cases** — your tolerances are tighter than
floating point. Look at `marginal_lossless` first: it sits 1e-12 below the
passivity limit precisely to catch this.

**Verdict `INCOMPLETE`** — your adapter did not report every law. Usually the
dict keys do not match the corpus's names, which are listed once at the top of
`data/manifest.json` under `laws` and per case under `expect`. The reference
adapter in `sparam_lint_adapter.py` is five lines long and gets them right.
`INCOMPLETE` exits `1`: an unreported law was not checked, and this corpus
cannot certify what it never saw.

**`generate.py` changes the files** — it should not; regeneration is
byte-identical and CI checks it. If your run differs, you have a different numpy
version doing different rounding, which is worth reporting.

**Scoring passes but your tool still ships bad models** — expected. Eleven cases
is a conformance floor: failing here means definitely broken, passing means
not-obviously-broken. It is not a sample of what comes out of a real VNA.

## Files

```
generate.py               deterministic corpus generator
score.py                  scorer + adapter contract
sparam_lint_adapter.py    reference adapter (5 lines)
data/*.s2p, *.s4p         the corpus
data/manifest.json        labels, tags, SHA-256 digests
data/index.jsonl          the manifest flattened one-row-per-case, so the
                          Hub viewer can render it (generated by build_index.py)
build_index.py            regenerates index.jsonl from the manifest
tests/                    label verification + scorer tests
```

## The rest of the toolkit

Eight artifacts that answer one question in different places: **is this
model physically possible?** Each is a grader — it can tell you a model is
wrong; none can tell you one is right.

| | |
|---|---|
| [`sparam-lint`](https://github.com/nickharris808/sparam-lint) | Is an S-parameter model physically possible? Five laws + a negative control. |
| [`maxwell-lint`](https://github.com/nickharris808/maxwell-lint) | Does a coupling extractor predict impossible physics? Screening ceiling k ≤ 1. |
| [`abstain-bench`](https://github.com/nickharris808/abstain-bench) | Does a model know when to shut up? Abstention recall, never pooled with accuracy. |
| [`sparam-conformance`](https://huggingface.co/datasets/nickh007/sparam-conformance) ← you are here | 11 labelled networks with verified ground truth. Grades the graders. |
| [`screening-ceiling`](https://huggingface.co/datasets/nickh007/screening-ceiling) | A certified impossibility result + 27 counterexamples. Zero-dependency verifier. |
| [`physics-lint-action`](https://github.com/nickharris808/physics-lint-action) | The same checks, in your CI. |
| [`physics-lint-mcp`](https://github.com/nickharris808/physics-lint-mcp) | A physics oracle your AI agent can call. |
| [**Try it in your browser**](https://huggingface.co/spaces/nickh007/physics-lint) | All three checks, no install, runs client-side. |

These tools **grade** a model. Producing one that is passive *by
construction* — so it cannot fail these laws whatever its parameters — and
accurate at speed in the many-body regime, with calibrated abstention and a
fail-closed signoff certificate, is the commercial core:
**[ChipletOS](https://chipletos.com)**.

## Licence

**CC-BY-4.0** — see [LICENSE](LICENSE). Attribution: ChipletOS / Genesis contributors.

The corpus is synthetic and contains no proprietary or measured data.

## Related

- [`sparam-lint`](https://github.com/nickharris808/sparam-lint) — the reference checker (Apache-2.0)
- [ChipletOS](https://chipletos.com) — scattering synthesis that is passive *by
  construction*, so it cannot fail these laws whatever its parameters
