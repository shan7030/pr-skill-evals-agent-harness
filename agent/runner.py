import json
import time
from typing import Any, Dict, List

from litellm import completion

from agent.tools import PRToolkit, build_tool_schemas

MAX_TURNS = 12

SYSTEM_PROMPT = """You are a PR summary agent.

Workflow:
1. Call load_skill with the assigned skill version before writing anything.
2. Use PR tools to gather title, description, changed files, and diff excerpt.
3. Follow the loaded skill instructions exactly.
4. Call submit_summary with the final markdown summary.

Do not guess PR details. Always fetch them with tools first.
Do not respond with the final summary in plain text — use submit_summary."""


def _parse_tool_arguments(raw: str | None) -> Dict[str, Any]:
    if not raw:
        return {}
    return json.loads(raw)


def run_pr_summary_agent(model: str, case: Dict[str, Any], skill_version: str) -> Dict[str, Any]:
    toolkit = PRToolkit(case, skill_version)
    tools = build_tool_schemas()
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Summarize PR {case['id']} using skill version `{skill_version}`.\n"
                "Load the skill, gather PR details with tools, then submit the summary."
            ),
        },
    ]

    start = time.time()
    total_prompt_tokens = 0
    total_completion_tokens = 0
    turns = 0

    while turns < MAX_TURNS:
        turns += 1
        response = completion(
            model=model,
            messages=messages,
            tools=tools,
            temperature=0,
        )
        usage = getattr(response, "usage", None)
        if usage:
            total_prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
            total_completion_tokens += getattr(usage, "completion_tokens", 0) or 0

        message = response.choices[0].message
        assistant_message: Dict[str, Any] = {
            "role": "assistant",
            "content": message.content or "",
        }
        if message.tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in message.tool_calls
            ]
        messages.append(assistant_message)

        if not message.tool_calls:
            break

        for call in message.tool_calls:
            name = call.function.name
            arguments = _parse_tool_arguments(call.function.arguments)
            result = toolkit.execute(name, arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                }
            )

        if toolkit.final_summary is not None:
            break

    latency_s = time.time() - start
    output = toolkit.final_summary or (message.content or "")

    return {
        "output": output,
        "latency_s": latency_s,
        "prompt_tokens": total_prompt_tokens or None,
        "completion_tokens": total_completion_tokens or None,
        "total_tokens": (total_prompt_tokens + total_completion_tokens) or None,
        "agent_turns": turns,
        "tool_calls_count": len(toolkit.tool_calls_log),
        "skills_loaded": toolkit.skills_loaded,
        "tool_calls_log": toolkit.tool_calls_log,
    }
