# Contributing to sparam-conformance

## The most useful contribution is a new pathological case

If you have an S-parameter file that a checker got wrong — passed something
non-physical, or rejected something real — that is the highest-value thing you
can send.

## Every case must be synthesised, not captured

Add a closed-form generator to `generate.py`. The label must be derivable from
the construction: we know a network is non-passive because we built gain into
it, not because a tool said so. Captured measurement data has no ground truth,
which is exactly the problem this corpus exists to fix.

## Every label is re-derived in the tests

`tests/test_conformance.py` recomputes passivity, reciprocity and energy for
every case by independent linear algebra and asserts they match the manifest.
Add your case and the tests will check your label. If they disagree with you,
they are probably right — that check caught three wrong labels during initial
development.

## Isolate one law where physics permits

A case that breaks four laws at once tells you nothing about which check is
alive. Where a single-law violation is impossible (a reflection coefficient
above unity necessarily breaks energy conservation too), say so in the note and
label all the affected laws honestly.

## Determinism

Generation must be reproducible byte-for-byte; there is a test. No randomness
without a pinned seed.

```bash
python generate.py
PYTHONPATH=.:../sparam-lint/src pytest tests/ -q
```
