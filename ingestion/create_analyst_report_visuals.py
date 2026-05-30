"""Create analyst report visualisations from exported CSV data."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.audit_gtfsr_snapshot_coverage import build_coverage_report  # noqa: E402
from ingestion.utils import ensure_dir, setup_logging  # noqa: E402


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    return rows[0], rows[1:]


def _exploratory_prefix(rating: str) -> str:
    if rating in {"insufficient", "exploratory"}:
        return "Exploratory only — limited snapshot coverage\n"
    return ""


def _plot_top_sa2(data_dir: Path, figures_dir: Path, rating: str) -> None:
    import matplotlib.pyplot as plt

    header, rows = _read_csv(data_dir / "top_recurring_high_impact_sa2s.csv")
    idx_name = header.index("sa2_name")
    idx_score = header.index("avg_equity_impact_score")
    rows = rows[:10]
    labels = [r[idx_name][:28] for r in rows]
    values = [float(r[idx_score]) for r in rows]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(labels[::-1], values[::-1], color="#2a9d8f")
    ax.set_xlabel("Average equity impact score (v1 proxy)")
    ax.set_title(_exploratory_prefix(rating) + "Top SA2 areas by average equity impact score")
    fig.tight_layout()
    fig.savefig(figures_dir / "01_top_recurring_high_impact_sa2s.png", dpi=150)
    plt.close(fig)


def _plot_seifa(data_dir: Path, figures_dir: Path, rating: str) -> None:
    import matplotlib.pyplot as plt

    header, rows = _read_csv(data_dir / "seifa_decile_vs_disruption.csv")
    idx_decile = header.index("irsd_decile")
    idx_impact = header.index("avg_equity_impact_score")
    idx_delay = header.index("avg_delay_observation_rate")
    deciles = [float(r[idx_decile]) for r in rows]
    impact = [float(r[idx_impact]) for r in rows]
    delay = [float(r[idx_delay]) * 100 for r in rows]
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax1.bar(deciles, impact, width=0.4, label="Avg equity impact", color="#457b9d")
    ax2 = ax1.twinx()
    ax2.plot(deciles, delay, color="#e76f51", marker="o", label="Avg delay rate (%)")
    ax1.set_xlabel("IRSD decile (1 = most disadvantaged)")
    ax1.set_ylabel("Average equity impact score")
    ax2.set_ylabel("Average delay observation rate (%)")
    ax1.set_title(_exploratory_prefix(rating) + "SEIFA decile vs disruption equity metrics")
    fig.tight_layout()
    fig.savefig(figures_dir / "02_seifa_decile_vs_disruption.png", dpi=150)
    plt.close(fig)


def _plot_hourly(data_dir: Path, figures_dir: Path, rating: str) -> None:
    import matplotlib.pyplot as plt

    header, rows = _read_csv(data_dir / "hourly_disruption_pattern.csv")
    idx_hour = header.index("snapshot_hour")
    idx_impact = header.index("avg_equity_impact_score")
    hours = [int(float(r[idx_hour])) for r in rows]
    impact = [float(r[idx_impact]) for r in rows]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(hours, impact, marker="o", color="#264653")
    ax.set_xlabel("Snapshot hour")
    ax.set_ylabel("Average equity impact score")
    ax.set_title(_exploratory_prefix(rating) + "Hourly disruption equity impact pattern")
    fig.tight_layout()
    fig.savefig(figures_dir / "03_hourly_disruption_pattern.png", dpi=150)
    plt.close(fig)


def _plot_routes(data_dir: Path, figures_dir: Path, rating: str) -> None:
    import matplotlib.pyplot as plt

    path = data_dir / "route_contribution_to_high_impact_areas.csv"
    if not path.exists() or path.stat().st_size == 0:
        return
    header, rows = _read_csv(path)
    if not rows:
        return
    idx_route = header.index("route_id")
    idx_count = header.index("delayed_observations_in_high_impact_sa2")
    rows = rows[:10]
    labels = [r[idx_route] for r in rows]
    values = [float(r[idx_count]) for r in rows]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(labels[::-1], values[::-1], color="#f4a261")
    ax.set_xlabel("Delayed observations in high-impact SA2 areas")
    ax.set_title(_exploratory_prefix(rating) + "Route contribution to high-impact SA2 exposure")
    fig.tight_layout()
    fig.savefig(figures_dir / "04_route_contribution_to_high_impact_areas.png", dpi=150)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create analyst report figures.")
    parser.add_argument("--data-dir", default="docs/analyst_report/data")
    parser.add_argument("--figures-dir", default="docs/analyst_report/figures")
    args = parser.parse_args()
    logger = setup_logging()
    data_dir = Path(args.data_dir)
    figures_dir = ensure_dir(Path(args.figures_dir))
    rating = build_coverage_report(Path("data/processed"))["data_sufficiency_rating"]
    required = [
        "top_recurring_high_impact_sa2s.csv",
        "seifa_decile_vs_disruption.csv",
        "hourly_disruption_pattern.csv",
    ]
    missing = [name for name in required if not (data_dir / name).exists()]
    if missing:
        logger.error("Missing export files: %s. Run export_analyst_report_outputs.py first.", missing)
        return 1
    _plot_top_sa2(data_dir, figures_dir, rating)
    _plot_seifa(data_dir, figures_dir, rating)
    _plot_hourly(data_dir, figures_dir, rating)
    _plot_routes(data_dir, figures_dir, rating)
    logger.info("Wrote figures to %s (rating=%s)", figures_dir, rating)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
