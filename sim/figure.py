"""Retention figure for one ``python -m sim`` run."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from brain.constants import DEFAULT_COMPRESSION

# COI means from the archived 10 seed × 40 trial table (docs/results).
ARCHIVED = {
    "spaced": {"naive": -3.5, "1h": 90.0, "3h": 88.1, "24h": 85.1, "72h": 69.7},
    "massed": {"naive": -3.5, "1h": 96.2, "3h": 96.2, "24h": 89.0, "72h": 44.7},
}
ORDER = ["naive", "1h", "3h", "24h", "72h"]
LABELS = ["naive", "1 h", "3 h", "24 h", "72 h"]


def _mean_sem(rows, protocol, manip):
    grouped = defaultdict(list)
    for row in rows:
        if row["protocol"] == protocol and row["manip"] == manip:
            grouped[row["test"]].append(row["PI"])
    means, sems = [], []
    for label in ORDER:
        values = grouped.get(label, [])
        if not values:
            means.append(np.nan)
            sems.append(0.0)
            continue
        means.append(float(np.mean(values)))
        sems.append(float(np.std(values, ddof=1) / np.sqrt(len(values))) if len(values) > 1 else 0.0)
    return means, sems


def write_figure(rows, extras, path: Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(14.2, 4.4))

    ax = axes[0]
    ax.set_aspect("equal")
    ax.set_xlim(-0.55, 0.55)
    ax.set_ylim(-0.55, 0.55)
    ax.plot([-0.15, 0.15], [0.38, 0.38], color="k", lw=3)
    ax.plot(0.0, 0.35, "o", color="red", ms=10, mec="k")
    spaced = extras.get(("spaced", "WT"), {})
    train = spaced.get("train") or []
    if train and len(train[0]):
        path_xy = train[0]
        ax.plot(path_xy[:, 1], path_xy[:, 2], color="C0", lw=1.2)
        hits = path_xy[path_xy[:, 6] > 0]
        if len(hits):
            ax.plot(hits[:, 1], hits[:, 2], "rx", ms=5)
    later = spaced.get("h72") or []
    if later and len(later[0][1]):
        ax.plot(later[0][1][:, 1], later[0][1][:, 2], color="C3", lw=1.2, label="72 h")
    ax.set_title("spaced seed 0: train / 72 h")
    ax.set_xticks([])
    ax.set_yticks([])

    ax = axes[1]
    x = np.arange(len(ORDER))
    for protocol, color in (("spaced", "C2"), ("massed", "C1")):
        means, sems = _mean_sem(rows, protocol, "WT")
        ax.errorbar(x, means, yerr=sems, fmt="o-", color=color, capsize=3, label=f"{protocol} this run")
        archived = [ARCHIVED[protocol][label] for label in ORDER]
        ax.plot(x, archived, ls="--", color=color, alpha=0.7, label=f"{protocol} archived")
    ax.axhline(0, color="k", lw=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(LABELS)
    ax.set_ylabel("PI (avoid CS+)")
    ax.set_title(f"Retention, COI, compression = {DEFAULT_COMPRESSION:g}")
    ax.legend(fontsize=8)

    ax = axes[2]
    manips = ["WT", "eps0", "osc_off"]
    width = 0.35
    for index, protocol in enumerate(("spaced", "massed")):
        means = []
        sems = []
        for manip in manips:
            grouped = [row["PI"] for row in rows if row["protocol"] == protocol and row["manip"] == manip and row["test"] == "72h"]
            means.append(float(np.mean(grouped)) if grouped else np.nan)
            sems.append(float(np.std(grouped, ddof=1) / np.sqrt(len(grouped))) if len(grouped) > 1 else 0.0)
        ax.bar(np.arange(len(manips)) + (index - 0.5) * width, means, width, yerr=sems, capsize=3, label=protocol)
    ax.axhline(0, color="k", lw=0.5)
    ax.set_xticks(range(len(manips)))
    ax.set_xticklabels(["WT", "eps off", "oscillator off"])
    ax.set_ylabel("PI at 72 h")
    ax.set_title("Ablations at 72 h")
    ax.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path
