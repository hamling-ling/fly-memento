"""Reproduce the spaced-versus-massed retention table.

    python -m sim
    python -m sim --seeds 2 --trials 8 --quick

``--quick`` keeps spaced and massed, wild type only, and tests only the
naive and 72 h points. The full command is the one that writes the table
the README quotes.
"""

from __future__ import annotations

import argparse
import csv
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

from sim.experiment import DEFAULT_CONDITIONS, TESTS, run_experiment
from sim.figure import ORDER, write_figure

ARCHIVED_72H = {"spaced": 69.7, "massed": 44.7}
NAMES = {
    ("spaced", "WT"): "分散 WT",
    ("massed", "WT"): "集中 WT",
    ("spaced", "eps0"): "分散 εなし",
    ("massed", "eps0"): "集中 εなし",
    ("spaced", "osc_off"): "分散 振動子オフ",
    ("massed", "osc_off"): "集中 振動子オフ",
    ("1x", "WT"): "1回 WT",
}


def _parser():
    parser = argparse.ArgumentParser(description="Run the memory-bug arena protocols")
    parser.add_argument("--seeds", type=int, default=4)
    parser.add_argument("--trials", type=int, default=12)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", type=Path, default=Path("sim/out"))
    parser.add_argument("--quick", action="store_true", help="WT only, naive and 72 h")
    return parser


def _summarise(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["protocol"], row["manip"], row["test"])].append(row)
    return grouped


def _width(text: str) -> int:
    width = 0
    for char in text:
        width += 2 if unicodedata.east_asian_width(char) in ("F", "W") else 1
    return width


def _ljust(text: str, width: int) -> str:
    return text + " " * max(0, width - _width(text))


def _rjust(text: str, width: int) -> str:
    return " " * max(0, width - _width(text)) + text


def _print_table(rows):
    grouped = _summarise(rows)
    labels = [label for label in ORDER if any(row["test"] == label for row in rows)]
    print(_ljust("条件", 16) + "".join(_rjust(label, 10) for label in labels) + _rjust("ARM72", 8) + _rjust("LTM72", 8))
    keys = []
    for protocol, manip in DEFAULT_CONDITIONS:
        if any(row["protocol"] == protocol and row["manip"] == manip for row in rows):
            keys.append((protocol, manip))
    for key in keys:
        protocol, manip = key
        cells = []
        for label in labels:
            sample = grouped.get((protocol, manip, label), [])
            cells.append(f"{np_mean_pi(sample):6.1f}" if sample else "     —")
        late = grouped.get((protocol, manip, "72h"), [])
        arm = f"{np_mean_key(late, 'ARM'):6.3f}" if late else "     —"
        ltm = f"{np_mean_key(late, 'LTM'):6.3f}" if late else "     —"
        name = NAMES.get(key, f"{protocol} {manip}")
        print(_ljust(name, 16) + "".join(_rjust(cell, 10) for cell in cells) + _rjust(arm, 8) + _rjust(ltm, 8))
    print()
    print("72時間の回避スコア PI（正なら CS+ を避ける）")
    for protocol, archived in ARCHIVED_72H.items():
        sample = grouped.get((protocol, "WT", "72h"), [])
        if not sample:
            continue
        got = np_mean_pi(sample)
        print(f"  {NAMES[(protocol, 'WT')]}: この実行 {got:.0f}    研究ログ（10 seed × 40 試行） {archived:.0f}")


def np_mean_pi(sample):
    return sum(row["PI"] for row in sample) / len(sample)


def np_mean_key(sample, key):
    return sum(row[key] for row in sample) / len(sample)


def _write_csv(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "protocol",
        "manip",
        "seed",
        "test",
        "t_after_s",
        "PI",
        "n_csplus",
        "n_csminus",
        "n_none",
        "S",
        "ARM",
        "LTM",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.quick:
        conditions = [("spaced", "WT"), ("massed", "WT")]
        tests = [(4320, "72h")]
    else:
        conditions = None
        tests = TESTS
    print(
        f"seeds {args.seeds}  trials {args.trials}  "
        f"{'quick' if args.quick else 'full'}  workers {args.workers}",
        flush=True,
    )
    started = time.perf_counter()
    rows, extras = run_experiment(
        seeds=args.seeds,
        trials=args.trials,
        conditions=conditions,
        tests=tests,
        workers=args.workers,
    )
    elapsed = time.perf_counter() - started
    csv_path = _write_csv(rows, args.out / "summary.csv")
    figure_path = write_figure(rows, extras, args.out / "retention.png")
    _print_table(rows)
    print(f"csv  {csv_path}")
    print(f"figure  {figure_path}")
    print(f"wall  {elapsed:.1f} s")
    return rows


if __name__ == "__main__":
    main()
