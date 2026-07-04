import argparse
import json
import time
from pathlib import Path
from typing import Dict, Any, List

from dotenv import load_dotenv
from litellm import completion

from grading import deterministic_grade

load_dotenv(Path(__file__).resolve().parent / ".env")

SKILL_VERSIONS = {
    "v1_baseline": """
You summarize GitHub pull requests.
Write a useful PR summary.
""",
    "v2_format": """
You summarize GitHub pull requests.

Always use exactly this format:

## Summary
- ...

## Key Changes
- ...

## Testing
- ...

## Risks
- ...

Rules:
- Never leave the Testing or Risks sections empty.
- In Testing, recommend concrete verification steps such as unit tests, integration tests, or regression tests the reviewer should run.
- In Risks, mention breaking changes, database migrations, or deployment impact when the PR touches APIs, auth, billing, or exports.
- Paraphrase in your own words; do not copy short phrases verbatim from the PR input.
""",
    "v3_grounded": """
You summarize GitHub pull requests.

Always use exactly this format:

## Summary
- ...

## Key Changes
- ...

## Testing
- ...

## Risks
- ...

Rules:
- Use only information present in the PR input.
- Do not invent tests, files, APIs, migrations, metrics, or breaking changes.
- If tests are not mentioned, write: "Not specified in the PR input."
""",
    "v4_review_ready": """
You summarize GitHub pull requests for engineering reviewers.

Always use exactly this format:

## Summary
- ...

## Key Changes
- ...

## Testing
- ...

## Risks
- ...

Rules:
- Use only information present in the PR input.
- Do not invent tests, files, APIs, migrations, metrics, or breaking changes.
- If tests are not mentioned, write: "Not specified in the PR input."
- Mention breaking changes only if explicitly present.
- If risks are unclear, infer only conservative risks from changed files and diff.
- Keep it short enough for a reviewer to scan in under 30 seconds.
"""
}


def load_dataset(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text())


def build_prompt(skill_text: str, case: Dict[str, Any]) -> str:
    return f"""
You have access to the following skill. Treat it like a reusable agent capability.

<skill>
{skill_text}
</skill>

Now apply the skill to this PR.

<pr>
Title: {case["title"]}

Description:
{case["description"]}

Changed files:
{json.dumps(case["changed_files"], indent=2)}

Diff excerpt:
{case["diff_excerpt"]}
</pr>
"""


def call_model(model: str, prompt: str) -> Dict[str, Any]:
    start = time.time()
    response = completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    latency_s = time.time() - start
    usage = getattr(response, "usage", None)
    return {
        "output": response.choices[0].message.content,
        "latency_s": latency_s,
        "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
        "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    with args.out.open("w") as f:
        for version, skill_text in SKILL_VERSIONS.items():
            for case in dataset:
                prompt = build_prompt(skill_text, case)
                model_result = call_model(args.model, prompt)
                grade = deterministic_grade(case, model_result["output"])
                row = {
                    "case_id": case["id"],
                    "skill_version": version,
                    "model": args.model,
                    **model_result,
                    **grade,
                }
                f.write(json.dumps(row) + "\n")
                print(f"{version} {case['id']} score={grade['score']:.2f} passed={grade['passed']}")

    print(f"\nWrote results to {args.out}")


if __name__ == "__main__":
    main()
