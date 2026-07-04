import json
import re
import time
from typing import Any, Dict

from litellm import completion

JUDGE_WEIGHTS = {
    "fact_coverage": 0.40,
    "format_compliance": 0.20,
    "groundedness": 0.25,
    "hallucination_free": 0.15,
}


def build_judge_prompt(case: Dict[str, Any], output: str) -> str:
    return f"""You are an evaluation judge for PR summaries. Score the candidate summary against the PR input.

<pr_input>
Title: {case["title"]}
Description: {case["description"]}
Changed files: {json.dumps(case["changed_files"])}
Diff excerpt: {case["diff_excerpt"]}
</pr_input>

<expected_facts>
{json.dumps(case["expected_facts"], indent=2)}
</expected_facts>

<forbidden_claims>
{json.dumps(case["forbidden_claims"], indent=2)}
</forbidden_claims>

<candidate_summary>
{output}
</candidate_summary>

Grade the candidate on:
1. fact_coverage (0-1): Are expected facts present? Semantic match is fine.
2. format_compliance (0-1): Has ## Summary, ## Key Changes, ## Testing, and ## Risks sections?
3. groundedness (0-1): Does it avoid inventing tests, files, APIs, migrations, or metrics not in the PR input?
4. hallucination_free (1 if no forbidden claims are present or strongly implied, else 0)

For groundedness:
- Writing "Not specified in the PR input." when tests are absent is good.
- Inventing test plans, migrations, or infrastructure not in the input is bad.

Return ONLY valid JSON with this schema:
{{
  "fact_coverage": <float 0-1>,
  "format_compliance": <float 0-1>,
  "groundedness": <float 0-1>,
  "hallucination_free": <float 0 or 1>,
  "hallucinations_found": [<strings>],
  "missing_facts": [<strings>],
  "score": <float 0-1>,
  "passed": <bool>,
  "reasoning": "<one sentence>"
}}

Compute score as:
0.40 * fact_coverage + 0.20 * format_compliance + 0.25 * groundedness + 0.15 * hallucination_free
Set passed to true only if score >= 0.80 and hallucination_free == 1."""


def _call_judge_model(judge_model: str, prompt: str, json_mode: bool) -> Dict[str, Any]:
    start = time.time()
    kwargs: Dict[str, Any] = {
        "model": judge_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = completion(**kwargs)
    latency_s = time.time() - start
    usage = getattr(response, "usage", None)
    return {
        "content": response.choices[0].message.content,
        "latency_s": latency_s,
        "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
        "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
    }


def parse_judge_json(raw: str) -> Dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def llm_judge(judge_model: str, case: Dict[str, Any], output: str) -> Dict[str, Any]:
    prompt = build_judge_prompt(case, output)
    try:
        result = _call_judge_model(judge_model, prompt, json_mode=True)
    except Exception:
        result = _call_judge_model(judge_model, prompt, json_mode=False)

    parsed = parse_judge_json(result["content"])
    score = (
        JUDGE_WEIGHTS["fact_coverage"] * float(parsed.get("fact_coverage", 0))
        + JUDGE_WEIGHTS["format_compliance"] * float(parsed.get("format_compliance", 0))
        + JUDGE_WEIGHTS["groundedness"] * float(parsed.get("groundedness", 0))
        + JUDGE_WEIGHTS["hallucination_free"] * float(parsed.get("hallucination_free", 0))
    )
    hallucination_free = float(parsed.get("hallucination_free", 0))
    passed = score >= 0.80 and hallucination_free == 1.0

    return {
        "judge_fact_coverage": float(parsed.get("fact_coverage", 0)),
        "judge_format_compliance": float(parsed.get("format_compliance", 0)),
        "judge_groundedness": float(parsed.get("groundedness", 0)),
        "judge_hallucination_free": hallucination_free,
        "judge_hallucinations_found": parsed.get("hallucinations_found", []),
        "judge_missing_facts": parsed.get("missing_facts", []),
        "judge_score": score,
        "judge_passed": passed,
        "judge_reasoning": parsed.get("reasoning", ""),
        "judge_latency_s": result["latency_s"],
        "judge_prompt_tokens": result["prompt_tokens"],
        "judge_completion_tokens": result["completion_tokens"],
        "judge_total_tokens": result["total_tokens"],
    }
