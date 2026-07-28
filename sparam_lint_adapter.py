"""Reference adapter: sparam-lint -> the conformance scorer contract.

Any checker can be scored by writing five lines like this.
"""
from sparam_lint import read_touchstone, run_battery


def check(path: str) -> dict[str, bool]:
    net = read_touchstone(path)
    return {r.name: r.passed for r in run_battery(net.s, net.freq_hz, net.z0)}
