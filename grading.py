from typing import Dict, Any


def deterministic_grade(case: Dict[str, Any], output: str) -> Dict[str, Any]:
    text = output.lower()
    expected = case["expected_facts"]
    forbidden = case["forbidden_claims"]

    matched_facts = [fact for fact in expected if fact.lower() in text]
    hallucinations = [claim for claim in forbidden if claim.lower() in text]

    required_sections = ["## summary", "## key changes", "## testing", "## risks"]
    sections_present = [section for section in required_sections if section in text]

    fact_recall = len(matched_facts) / len(expected)
    format_score = len(sections_present) / len(required_sections)
    hallucination_free = 1.0 if len(hallucinations) == 0 else 0.0

    score = (0.55 * fact_recall) + (0.25 * format_score) + (0.20 * hallucination_free)

    return {
        "matched_facts": matched_facts,
        "missing_facts": [fact for fact in expected if fact not in matched_facts],
        "hallucinations": hallucinations,
        "fact_recall": fact_recall,
        "format_score": format_score,
        "hallucination_free": hallucination_free,
        "score": score,
        "passed": score >= 0.80 and len(hallucinations) == 0,
    }
