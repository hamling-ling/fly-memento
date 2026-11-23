"""Headless check that a faster compression keeps the compression-1 outcome.

    python -m sim.scale_check
    python -m sim.scale_check --seeds 2 --trials 8 --skip-arena

Traces are the still-colour operator schedule (deterministic). The arena
half is spaced and massed, wild type, at 1 h / 24 h / 72 h. Body pace is
scaled with compression so the path length matches compression 1; the
remaining difference is integration and the coarser noise draw.
"""

from __future__ import annotations

import argparse
from collections import defaultdict

from sim.experiment import run_experiment, scripted_retention

COMPRESSIONS = (1.0, 2.0, 3.0, 5.0)
HORIZONS = (0.0, 60.0, 1440.0, 4320.0)
LABELS = {0.0: "end", 60.0: "1h", 1440.0: "24h", 4320.0: "72h"}


def trace_table(seed=1):
    rows = []
    for protocol in ("spaced", "massed"):
        base = {
            (row["horizon"]): row
            for row in scripted_retention(seed, protocol, 1.0, HORIZONS)
        }
        for compression in COMPRESSIONS:
            got = scripted_retention(seed, protocol, compression, HORIZONS)
            for row in got:
                ref = base[row["horizon"]]
                rows.append(
                    {
                        "protocol": protocol,
                        "compression": compression,
                        "label": LABELS[row["horizon"]],
                        "LTM": row["LTM"],
                        "ARM": row["ARM"],
                        "S": row["S"],
                        "phi": row["phi"],
                        "shocks": row["shocks"],
                        "dLTM": row["LTM"] - ref["LTM"],
                        "dARM": row["ARM"] - ref["ARM"],
                        "dS": row["S"] - ref["S"],
                        "dLTM_on": row["LTM_on"] - ref["LTM_on"],
                        "dARM_on": row["ARM_on"] - ref["ARM_on"],
                    }
                )
    return rows


def arena_table(seeds, trials, workers):
    tests = [(60, "1h"), (1440, "24h"), (4320, "72h")]
    grouped = defaultdict(list)
    for compression in COMPRESSIONS:
        print(f"arena compression {compression:g}", flush=True)
        rows, _extras = run_experiment(
            seeds=seeds,
            trials=trials,
            conditions=[("spaced", "WT"), ("massed", "WT")],
            tests=tests,
            workers=workers,
            compression=compression,
        )
        for row in rows:
            if row["test"] == "naive":
                continue
            grouped[(compression, row["protocol"], row["test"])].append(row)
    summary = []
    for compression in COMPRESSIONS:
        for protocol in ("spaced", "massed"):
            for _t, label in tests:
                sample = grouped[(compression, protocol, label)]
                ref = grouped[(1.0, protocol, label)]
                pi = sum(row["PI"] for row in sample) / len(sample)
                ref_pi = sum(row["PI"] for row in ref) / len(ref)
                ltm = sum(row["LTM"] for row in sample) / len(sample)
                ref_ltm = sum(row["LTM"] for row in ref) / len(ref)
                arm = sum(row["ARM"] for row in sample) / len(sample)
                ref_arm = sum(row["ARM"] for row in ref) / len(ref)
                summary.append(
                    {
                        "compression": compression,
                        "protocol": protocol,
                        "label": label,
                        "PI": pi,
                        "dPI": pi - ref_pi,
                        "LTM": ltm,
                        "dLTM": ltm - ref_ltm,
                        "ARM": arm,
                        "dARM": arm - ref_arm,
                    }
                )
    return summary


def _print_traces(rows):
    print(
        f"{'proto':<8}{'C':>4}{'when':>6}{'LTM':>9}{'dLTM':>9}{'ARM':>9}{'dARM':>9}"
        f"{'S':>9}{'phi':>7}{'shocks':>8}{'dLTMon':>9}"
    )
    for row in rows:
        print(
            f"{row['protocol']:<8}{row['compression']:4.0f}{row['label']:>6}"
            f"{row['LTM']:9.4f}{row['dLTM']:9.4f}{row['ARM']:9.4f}{row['dARM']:9.4f}"
            f"{row['S']:9.4f}{row['phi']:7.3f}{row['shocks']:8d}{row['dLTM_on']:9.4f}"
        )


def _print_arena(rows):
    print(f"{'proto':<8}{'C':>4}{'when':>6}{'PI':>8}{'dPI':>8}{'LTM':>9}{'dLTM':>9}{'ARM':>9}{'dARM':>9}")
    for row in rows:
        print(
            f"{row['protocol']:<8}{row['compression']:4.0f}{row['label']:>6}"
            f"{row['PI']:8.1f}{row['dPI']:8.1f}{row['LTM']:9.4f}{row['dLTM']:9.4f}"
            f"{row['ARM']:9.4f}{row['dARM']:9.4f}"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare compressions 1, 2, 3 and 5")
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--trials", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--skip-arena", action="store_true")
    parser.add_argument("--skip-traces", action="store_true")
    args = parser.parse_args(argv)
    if not args.skip_traces:
        print("scripted traces, seed 1", flush=True)
        _print_traces(trace_table())
    if not args.skip_arena:
        print(
            f"arena seeds {args.seeds} trials {args.trials} workers {args.workers}",
            flush=True,
        )
        _print_arena(arena_table(args.seeds, args.trials, args.workers))


if __name__ == "__main__":
    main()
