import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from llm_judge import llm_judge

load_dotenv(Path(__file__).resolve().parent / ".env")


def load_dataset(path: Path) -> Dict[str, Dict[str, Any]]:
    return {case["id"]: case for case in json.loads(path.read_text())}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Score existing eval results with an LLM judge")
    parser.add_argument("--results", type=Path, required=True, help="Input results.jsonl from eval run")
    parser.add_argument("--dataset", type=Path, required=True, help="Dataset used for the eval run")
    parser.add_argument("--out", type=Path, required=True, help="Output judged results.jsonl")
    parser.add_argument("--judge-model", required=True, help="Model to use as judge")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    rows = load_jsonl(args.results)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    with args.out.open("w") as f:
        for row in rows:
            case = dataset[row["case_id"]]
            judge = llm_judge(args.judge_model, case, row["output"])
            judged = {**row, **judge}
            judged["combined_score"] = (row["score"] + judge["judge_score"]) / 2
            judged["combined_passed"] = row["passed"] and judge["judge_passed"]
            f.write(json.dumps(judged) + "\n")
            print(
                f"{row['skill_version']} {row['case_id']} "
                f"det={row['score']:.2f} judge={judge['judge_score']:.2f} "
                f"passed={judged['combined_passed']}"
            )

    print(f"\nWrote judged results to {args.out}")


if __name__ == "__main__":
    main()
