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
---

# sparam-conformance

![CI](https://github.com/nickharris808/sparam-conformance/actions/workflows/ci.yml/badge.svg) ![Licence](https://img.shields.io/badge/data-CC--BY--4.0-green) ![Cases](https://img.shields.io/badge/cases-11%20labelled-blue) ![Tests](https://img.shields.io/badge/tests-46%20passing-brightgreen)

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

## Files

```
generate.py               deterministic corpus generator
score.py                  scorer + adapter contract
sparam_lint_adapter.py    reference adapter (5 lines)
data/*.s2p, *.s4p         the corpus
data/manifest.json        labels, tags, SHA-256 digests
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
