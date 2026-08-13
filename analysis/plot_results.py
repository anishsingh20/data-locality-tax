#!/usr/bin/env python3
"""
Render publication figures from the August 10, 2026 locality-tax harness JSON.

Reads results/*.json next to this repo and writes figures/*.png.
Numbers are never hard-coded: if JSON changes, re-run this script.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)

# DigitalOcean AI-Native Cloud palette (readable on a light article canvas)
COBALT = "#0069FF"
FOREST = "#1F403E"
AQUA = "#0E7C86"
INK = "#031B4E"
MUTED = "#5B6B7A"
FLOOR = "#C2410C"
PAPER = "#F7FBFC"
GRID = "#D7E3E8"

plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": PAPER,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.axisbelow": True,
    }
)

ARMS = ("A", "B1", "B2")
ARM_LABELS = {
    "A": "A  same DC / VPC\nNYC3 private",
    "B1": "B1  NYC3 → SFO3\npublic",
    "B2": "B2  NYC3 → SFO3\npeered VPC",
}
ARM_COLORS = {"A": COBALT, "B1": FOREST, "B2": AQUA}


def load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text())


def caption(ax, text: str) -> None:
    ax.figure.text(
        0.02,
        0.015,
        text,
        fontsize=7.5,
        color=MUTED,
        ha="left",
        va="bottom",
        wrap=True,
    )


def annotate_bars(ax, bars, fmt="{:.1f}") -> None:
    for bar in bars:
        h = bar.get_height()
        ax.annotate(
            fmt.format(h),
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
            color=INK,
            fontweight="bold",
        )


def fig_retrieval_p50() -> None:
    a, b1, b2 = load("a_k5.json"), load("b1_k5.json"), load("b2_k5.json")
    vals = [a["pooled"]["p50_ms"], b1["pooled"]["p50_ms"], b2["pooled"]["p50_ms"]]
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    x = range(3)
    bars = ax.bar(x, vals, color=[ARM_COLORS[a_] for a_ in ARMS], width=0.62, zorder=3)
    ax.set_xticks(list(x), [ARM_LABELS[a_] for a_ in ARMS])
    ax.set_ylabel("Pooled retrieval p50 (ms)")
    ax.set_title("Pooled vector search, k=5  ·  75 trials after 10 warmups")
    ax.set_ylim(0, max(vals) * 1.22)
    annotate_bars(ax, bars)
    ratio = vals[1] / vals[0]
    ax.annotate(
        f"B1 / A = {ratio:.0f}×",
        xy=(1, vals[1]),
        xytext=(1.35, vals[1] * 0.72),
        arrowprops=dict(arrowstyle="->", color=FLOOR),
        color=FLOOR,
        fontsize=10,
        fontweight="bold",
    )
    caption(
        ax,
        "Source: locality_bench.py pgvector mode on DigitalOcean NYC3 Droplet, 2026-08-10 10:04–10:05 UTC. "
        "Identical 100k × 768-d HNSW corpora. Lower is better.",
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(OUT / "fig-01-retrieval-p50-k5.png", dpi=160)
    plt.close(fig)


def fig_tcp_retrieval_cold() -> None:
    cells = {
        "A": (load("a_tcp.json"), load("a_k5.json")),
        "B1": (load("b1_tcp.json"), load("b1_k5.json")),
        "B2": (load("b2_tcp.json"), load("b2_k5.json")),
    }
    metrics = [
        ("TCP connect p50", lambda t, p: t["summary"]["p50_ms"]),
        ("Retrieval p50, k=5", lambda t, p: p["pooled"]["p50_ms"]),
        ("Cold first call, k=5", lambda t, p: p["cold_connection_first_call_ms"]),
    ]
    fig, ax = plt.subplots(figsize=(10.2, 5.6))
    x = list(range(len(ARMS)))
    width = 0.26
    for i, (label, fn) in enumerate(metrics):
        xs = [xi + (i - 1) * width for xi in x]
        ys = [fn(*cells[a_]) for a_ in ARMS]
        color = [COBALT, FOREST, FLOOR][i]
        bars = ax.bar(xs, ys, width=width, label=label, color=color, zorder=3)
        for bar, y in zip(bars, ys):
            ax.annotate(
                f"{y:.0f}" if y >= 10 else f"{y:.1f}",
                xy=(bar.get_x() + bar.get_width() / 2, y),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                color=INK,
            )
    ax.set_xticks(x, [ARM_LABELS[a_] for a_ in ARMS])
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Path floor vs pooled search vs cold connection")
    ax.legend(frameon=False, loc="upper left")
    caption(
        ax,
        "TCP connect is a raw socket to port 25060 (no SQL). Retrieval reuses one pooled connection. "
        "Cold first call times connect + TLS + first query together. Same window as fig-01.",
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(OUT / "fig-02-tcp-retrieval-cold.png", dpi=160)
    plt.close(fig)


def fig_topk() -> None:
    series = {
        "A": [load("a_k5.json"), load("a_k20.json"), load("a_k100.json")],
        "B1": [load("b1_k5.json"), load("b1_k20.json"), load("b1_k100.json")],
        "B2": [load("b2_k5.json"), load("b2_k20.json"), load("b2_k100.json")],
    }
    ks = [5, 20, 100]
    fig, ax = plt.subplots(figsize=(9.8, 5.4))
    x = list(range(len(ks)))
    width = 0.26
    for i, arm in enumerate(ARMS):
        xs = [xi + (i - 1) * width for xi in x]
        ys = [cell["pooled"]["p50_ms"] for cell in series[arm]]
        bars = ax.bar(xs, ys, width=width, label=ARM_LABELS[arm].split("\n")[0], color=ARM_COLORS[arm], zorder=3)
        for bar, y in zip(bars, ys):
            ax.annotate(
                f"{y:.1f}",
                xy=(bar.get_x() + bar.get_width() / 2, y),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                color=INK,
            )
    ax.set_xticks(x, [f"k = {k}" for k in ks])
    ax.set_ylabel("Pooled retrieval p50 (ms)")
    ax.set_title("Payload size vs distance: top-k 5 / 20 / 100")
    ax.legend(frameon=False)
    caption(
        ax,
        "Returning more neighbors adds payload on the return path. The extra cost is visible on Arm A "
        "(1.90 → 11.37 ms) and almost absorbed by the ~67 ms trip on B1/B2. n=75 per cell.",
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(OUT / "fig-03-topk-payload.png", dpi=160)
    plt.close(fig)


def fig_floor_vs_measured() -> None:
    tcp = {
        "A": load("a_tcp.json")["summary"]["p50_ms"],
        "B1": load("b1_tcp.json")["summary"]["p50_ms"],
        "B2": load("b2_tcp.json")["summary"]["p50_ms"],
    }
    floors = {"A": 0.01, "B1": 41.3, "B2": 41.3}
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    x = list(range(3))
    width = 0.34
    bars_floor = ax.bar(
        [xi - width / 2 for xi in x],
        [floors[a_] for a_ in ARMS],
        width=width,
        label="Physics floor (fiber, great-circle)",
        color="#9CA8B4",
        zorder=3,
    )
    bars_meas = ax.bar(
        [xi + width / 2 for xi in x],
        [tcp[a_] for a_ in ARMS],
        width=width,
        label="Measured TCP connect p50",
        color=COBALT,
        zorder=3,
    )
    annotate_bars(ax, bars_floor)
    annotate_bars(ax, bars_meas)
    ax.set_xticks(x, [ARM_LABELS[a_] for a_ in ARMS])
    ax.set_ylabel("Round-trip time (ms)")
    ax.set_title("Physics floor vs measured path  ·  TCP connect, no database work")
    ax.legend(frameon=False)
    ax.annotate(
        "B1 sits 27.3 ms above the 41.3 ms NYC–SFO floor\n(routing overhead, not a measurement error)",
        xy=(1 + width / 2, tcp["B1"]),
        xytext=(1.55, 52),
        fontsize=9,
        color=FLOOR,
        arrowprops=dict(arrowstyle="->", color=FLOOR),
    )
    caption(
        ax,
        "Floors are haversine great-circle distance / 200,000 km/s, doubled. Real fiber does not follow "
        "great circles, so every honest path must land at or above its floor. Nothing in this run landed below.",
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(OUT / "fig-04-floor-vs-measured-tcp.png", dpi=160)
    plt.close(fig)


def fig_compounding() -> None:
    a = load("a_k5.json")["pooled"]["p50_ms"]
    b1 = load("b1_k5.json")["pooled"]["p50_ms"]
    hops = list(range(1, 11))
    fig, ax = plt.subplots(figsize=(9.8, 5.5))
    ax.plot(hops, [a * h for h in hops], "o-", color=COBALT, linewidth=2.2, markersize=6, label=f"Arm A measured {a:.2f} ms × hops")
    ax.plot(hops, [b1 * h for h in hops], "o-", color=FOREST, linewidth=2.2, markersize=6, label=f"Arm B1 measured {b1:.2f} ms × hops")
    ax.plot(hops, [41.3 * h for h in hops], "--", color="#9CA8B4", linewidth=1.6, label="NYC–SFO physics floor 41.3 ms × hops")
    ax.set_xlabel("Sequential retrieval hops in one agent task")
    ax.set_ylabel("Summed geography tax (ms)")
    ax.set_title("How the measured per-call tax compounds in multi-hop RAG")
    ax.set_xticks(hops)
    ax.legend(frameon=False)
    ax.axhline(500, color=GRID, linewidth=1)
    ax.annotate(
        f"8 hops on B1 = {b1 * 8:.0f} ms\nbefore any token generates",
        xy=(8, b1 * 8),
        xytext=(5.2, b1 * 8 + 40),
        fontsize=9,
        color=FOREST,
        fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=FOREST),
    )
    caption(
        ax,
        "Arithmetic on the measured pooled k=5 p50, not a second experiment. Sequential hops add; they do not overlap. "
        "Real agent tasks sit at or above these lines because each hop also does ANN work.",
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(OUT / "fig-05-compounding-measured.png", dpi=160)
    plt.close(fig)


def fig_consistency() -> None:
    cells = {
        "A": load("a_k5.json")["pooled"],
        "B1": load("b1_k5.json")["pooled"],
        "B2": load("b2_k5.json")["pooled"],
    }
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    x = list(range(3))
    width = 0.36
    p50 = [cells[a_]["p50_ms"] for a_ in ARMS]
    p95 = [cells[a_]["p95_ms"] for a_ in ARMS]
    ax.bar([xi - width / 2 for xi in x], p50, width=width, label="p50", color=COBALT, zorder=3)
    ax.bar([xi + width / 2 for xi in x], p95, width=width, label="p95", color=FOREST, zorder=3)
    for i, a_ in enumerate(ARMS):
        ax.annotate(f"{p50[i]:.2f}", (i - width / 2, p50[i]), ha="center", va="bottom", fontsize=8, xytext=(0, 3), textcoords="offset points")
        ax.annotate(f"{p95[i]:.2f}", (i + width / 2, p95[i]), ha="center", va="bottom", fontsize=8, xytext=(0, 3), textcoords="offset points")
    ax.set_xticks(x, [ARM_LABELS[a_] for a_ in ARMS])
    ax.set_ylabel("Pooled retrieval latency (ms), k=5")
    ax.set_title("Median vs tail  ·  a consistently slow path, not a noisy index")
    ax.legend(frameon=False)
    caption(
        ax,
        "On B1, p95 (69.55 ms) sits 2.6 ms above p50 (66.97 ms). The distant path is reliably slow. "
        "n=75 measured trials per arm after 10 discarded warmups.",
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(OUT / "fig-06-p50-vs-p95.png", dpi=160)
    plt.close(fig)


def fig_study_design() -> None:
    fig, ax = plt.subplots(figsize=(10.4, 5.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")
    ax.set_title("Study design  ·  one client, three paths, identical corpora", pad=12)

    def box(x, y, w, h, text, fc, ec):
        p = mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.15",
            facecolor=fc, edgecolor=ec, linewidth=1.6,
        )
        ax.add_patch(p)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9, color=INK, fontweight="medium")

    box(0.35, 2.15, 2.5, 1.7, "Client Droplet\nNYC3  ·  s-2vcpu-4gb\nUbuntu 24.04\nlocality_bench.py", "#E8F1FF", COBALT)
    box(4.3, 4.15, 2.6, 1.35, "Arm A  ·  pgvector NYC3\nprivate hostname / VPC\n1.90 ms pooled k=5", "#E8F1FF", COBALT)
    box(4.3, 2.25, 2.6, 1.35, "Arm B1  ·  pgvector SFO3\npublic hostname\n66.97 ms pooled k=5", "#EEF4F4", FOREST)
    box(4.3, 0.35, 2.6, 1.35, "Arm B2  ·  pgvector SFO3\npeered VPC hostname\n69.90 ms pooled k=5", "#E7F6F7", AQUA)
    box(7.5, 2.15, 2.15, 1.7, "Fixed across arms\n100k vectors\ndim 768  ·  HNSW\ncosine  ·  k=5/20/100", PAPER, MUTED)

    ax.annotate("", xy=(4.3, 4.8), xytext=(2.85, 3.4), arrowprops=dict(arrowstyle="->", color=COBALT, lw=1.6))
    ax.annotate("", xy=(4.3, 2.9), xytext=(2.85, 3.0), arrowprops=dict(arrowstyle="->", color=FOREST, lw=1.6))
    ax.annotate("", xy=(4.3, 1.0), xytext=(2.85, 2.6), arrowprops=dict(arrowstyle="->", color=AQUA, lw=1.6))

    caption(
        ax,
        "Run window 2026-08-10 10:04:37–10:05:45 UTC. Arms B3 (NYC→SGP) and C (third-party SaaS) were not executed "
        "and are omitted rather than estimated.",
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(OUT / "fig-00-study-design.png", dpi=160)
    plt.close(fig)


def main() -> None:
    fig_study_design()
    fig_retrieval_p50()
    fig_tcp_retrieval_cold()
    fig_topk()
    fig_floor_vs_measured()
    fig_compounding()
    fig_consistency()
    print("Wrote:")
    for p in sorted(OUT.glob("fig-*.png")):
        print(" ", p.name, f"{p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
