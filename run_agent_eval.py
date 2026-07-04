import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from agent.runner import run_pr_summary_agent
from agent.tools import list_skill_versions
from grading import deterministic_grade

load_dotenv(Path(__file__).resolve().parent / ".env")


def load_dataset(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PR summary agent eval with tools and skills")
    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--skill-versions",
        nargs="*",
        default=None,
        help="Skill versions to evaluate (default: all under skills/)",
    )
    args = parser.parse_args()

    skill_versions = args.skill_versions or list_skill_versions()
    dataset = load_dataset(args.dataset)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    with args.out.open("w") as f:
        for version in skill_versions:
            for case in dataset:
                result = run_pr_summary_agent(args.model, case, version)
                grade = deterministic_grade(case, result["output"])
                row: Dict[str, Any] = {
                    "case_id": case["id"],
                    "skill_version": version,
                    "model": args.model,
                    "eval_mode": "agent",
                    **result,
                    **grade,
                }
                f.write(json.dumps(row) + "\n")
                print(
                    f"{version} {case['id']} score={grade['score']:.2f} "
                    f"tools={result['tool_calls_count']} passed={grade['passed']}"
                )

    print(f"\nWrote agent results to {args.out}")


if __name__ == "__main__":
    main()
