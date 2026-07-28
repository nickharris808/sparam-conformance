#!/usr/bin/env python3
"""Flatten the manifest into a tabular index the Hub dataset viewer can render.

The corpus itself is Touchstone text, which no dataset viewer parses, so a
reader landing on the Hub page would otherwise see nothing at all. This emits
one row per case -- labels, expected failures, digest -- so the contents are
browsable in the page without downloading anything.

The .sNp files remain the data; this is a view of the manifest, generated from
it, never edited by hand.
"""
from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"


def build() -> list[dict]:
    m = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for c in m["cases"]:
        expect = c["expect"]
        rows.append({
            "name": c["name"],
            "file": c["file"],
            "n_ports": c["n_ports"],
            "z0_ohm": c["z0_ohm"],
            "physically_realizable": c["physical"],
            "expected_to_pass_all_laws": c["expect_all_pass"],
            "expected_failures": sorted(k for k, v in expect.items() if not v),
            "tags": c.get("tags", []),
            "note": c.get("note", ""),
            "sha256": c.get("sha256", ""),
        })
    return rows


def main() -> int:
    rows = build()
    out = DATA / "index.jsonl"
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    print(f"{out.relative_to(HERE)}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
