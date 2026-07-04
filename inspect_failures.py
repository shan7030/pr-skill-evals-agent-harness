import argparse
import json
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--use-judge", action="store_true", help="Show judge failures instead of deterministic failures")
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.results.read_text().splitlines()]
    passed_key = "judge_passed" if args.use_judge else "passed"
    failures = [row for row in rows if not row.get(passed_key, row.get("passed", False))]

    for row in failures:
        score = row.get("judge_score", row["score"]) if args.use_judge else row["score"]
        print(f"\n{row['skill_version']} / {row['case_id']} / score={score:.2f}")

        if args.use_judge and "judge_reasoning" in row:
            print(f"Judge reasoning: {row['judge_reasoning']}")
            if row.get("judge_missing_facts"):
                print("Judge missing facts:")
                for fact in row["judge_missing_facts"]:
                    print(f"  - {fact}")
            if row.get("judge_hallucinations_found"):
                print("Judge hallucinations:")
                for claim in row["judge_hallucinations_found"]:
                    print(f"  - {claim}")
        else:
            if row.get("missing_facts"):
                print("Missing facts:")
                for fact in row["missing_facts"]:
                    print(f"  - {fact}")
            if row.get("hallucinations"):
                print("Hallucinations:")
                for claim in row["hallucinations"]:
                    print(f"  - {claim}")

        print("\nOutput:")
        print(row["output"][:1200])

if __name__ == "__main__":
    main()
