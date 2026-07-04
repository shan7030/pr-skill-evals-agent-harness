import argparse
import json
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

def load_jsonl(path: Path) -> pd.DataFrame:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return pd.DataFrame(rows)

def summarize(df: pd.DataFrame) -> pd.DataFrame:
    agg = {
        "n": ("case_id", "count"),
        "success_rate": ("passed", "mean"),
        "avg_score": ("score", "mean"),
        "fact_recall": ("fact_recall", "mean"),
        "format_score": ("format_score", "mean"),
        "hallucination_free": ("hallucination_free", "mean"),
        "avg_latency_s": ("latency_s", "mean"),
        "avg_tokens": ("total_tokens", "mean"),
    }

    if "judge_score" in df.columns:
        agg.update({
            "judge_success_rate": ("judge_passed", "mean"),
            "avg_judge_score": ("judge_score", "mean"),
            "judge_fact_coverage": ("judge_fact_coverage", "mean"),
            "judge_format_compliance": ("judge_format_compliance", "mean"),
            "judge_groundedness": ("judge_groundedness", "mean"),
            "judge_hallucination_free": ("judge_hallucination_free", "mean"),
            "combined_success_rate": ("combined_passed", "mean"),
            "avg_combined_score": ("combined_score", "mean"),
        })

    summary = df.groupby("skill_version").agg(**agg).reset_index()

    pct_cols = [
        "success_rate", "avg_score", "fact_recall", "format_score", "hallucination_free",
        "judge_success_rate", "avg_judge_score", "judge_fact_coverage", "judge_format_compliance",
        "judge_groundedness", "judge_hallucination_free", "combined_success_rate", "avg_combined_score",
    ]
    for col in pct_cols:
        if col in summary.columns:
            summary[col] = summary[col] * 100

    if "hallucination_free" in summary.columns:
        summary["hallucination_rate"] = 100 - summary["hallucination_free"]
    if "judge_hallucination_free" in summary.columns:
        summary["judge_hallucination_rate"] = 100 - summary["judge_hallucination_free"]

    return summary

def line_plot(summary: pd.DataFrame, y: str, title: str, ylabel: str, out: Path) -> None:
    if y not in summary.columns:
        return
    plt.figure(figsize=(8, 5))
    plt.plot(summary["skill_version"], summary[y], marker="o")
    plt.title(title)
    plt.xlabel("Skill Version")
    plt.ylabel(ylabel)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(out, dpi=200)
    plt.close()

def grouped_bar(summary: pd.DataFrame, out: Path, metrics: list[str], title: str) -> None:
    available = [metric for metric in metrics if metric in summary.columns]
    if not available:
        return
    x = list(range(len(summary)))
    width = 0.8 / len(available)
    plt.figure(figsize=(9, 5))
    for i, metric in enumerate(available):
        offsets = [v + (i - (len(available) - 1) / 2) * width for v in x]
        plt.bar(offsets, summary[metric], width=width, label=metric.replace("_", " ").title())
    plt.title(title)
    plt.xlabel("Skill Version")
    plt.ylabel("Score (%)")
    plt.xticks(x, summary["skill_version"], rotation=20, ha="right")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out, dpi=200)
    plt.close()

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    df = load_jsonl(args.results)
    summary = summarize(df)
    summary.to_csv(args.outdir / "summary_metrics.csv", index=False)

    line_plot(summary, "success_rate", "Deterministic Success Rate Across Skill Versions", "Success Rate (%)", args.outdir / "success_rate.png")
    line_plot(summary, "avg_score", "Deterministic Average Score Across Skill Versions", "Average Score (%)", args.outdir / "avg_score.png")
    line_plot(summary, "hallucination_rate", "Deterministic Hallucination Rate Across Skill Versions", "Hallucination Rate (%)", args.outdir / "hallucination_rate.png")
    grouped_bar(summary, args.outdir / "rubric_scores.png", ["fact_recall", "format_score", "hallucination_free"], "Deterministic Rubric Scores Across Skill Versions")

    if "avg_judge_score" in summary.columns:
        line_plot(summary, "judge_success_rate", "LLM Judge Success Rate Across Skill Versions", "Success Rate (%)", args.outdir / "judge_success_rate.png")
        line_plot(summary, "avg_judge_score", "LLM Judge Average Score Across Skill Versions", "Average Score (%)", args.outdir / "judge_avg_score.png")
        line_plot(summary, "judge_hallucination_rate", "LLM Judge Hallucination Rate Across Skill Versions", "Hallucination Rate (%)", args.outdir / "judge_hallucination_rate.png")
        line_plot(summary, "combined_success_rate", "Combined Success Rate Across Skill Versions", "Success Rate (%)", args.outdir / "combined_success_rate.png")
        line_plot(summary, "avg_combined_score", "Combined Average Score Across Skill Versions", "Average Score (%)", args.outdir / "combined_avg_score.png")
        grouped_bar(
            summary,
            args.outdir / "judge_rubric_scores.png",
            ["judge_fact_coverage", "judge_format_compliance", "judge_groundedness", "judge_hallucination_free"],
            "LLM Judge Rubric Scores Across Skill Versions",
        )

    print(summary.to_string(index=False))
    print(f"\nWrote metrics and plots to {args.outdir}")

if __name__ == "__main__":
    main()
