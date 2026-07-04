import json
from pathlib import Path
from typing import Any, Callable, Dict, List

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def list_skill_versions() -> List[str]:
    return sorted(
        path.name
        for path in SKILLS_DIR.iterdir()
        if path.is_dir() and (path / "SKILL.md").exists()
    )


def load_skill_content(skill_version: str) -> str:
    skill_path = SKILLS_DIR / skill_version / "SKILL.md"
    if not skill_path.exists():
        raise ValueError(f"Unknown skill version: {skill_version}")
    return skill_path.read_text()


def build_tool_schemas() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "list_available_skills",
                "description": "List available PR summary skill versions the agent can load.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "load_skill",
                "description": "Load instructions for a PR summary skill version.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_version": {
                            "type": "string",
                            "description": "Skill version id, e.g. v3_grounded",
                        }
                    },
                    "required": ["skill_version"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_pr_metadata",
                "description": "Get PR id and title.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_pr_description",
                "description": "Get the PR description text.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_changed_files",
                "description": "List files changed in the PR.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_diff_excerpt",
                "description": "Get a short diff excerpt for the PR.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "submit_summary",
                "description": "Submit the final PR summary. Call this when the summary is complete.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "The final PR summary markdown.",
                        }
                    },
                    "required": ["summary"],
                },
            },
        },
    ]


class PRToolkit:
    def __init__(self, case: Dict[str, Any], skill_version: str):
        self.case = case
        self.skill_version = skill_version
        self.skills_loaded: List[str] = []
        self.tool_calls_log: List[Dict[str, Any]] = []
        self.final_summary: str | None = None

    def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        handlers: Dict[str, Callable[[Dict[str, Any]], str]] = {
            "list_available_skills": self._list_available_skills,
            "load_skill": self._load_skill,
            "get_pr_metadata": self._get_pr_metadata,
            "get_pr_description": self._get_pr_description,
            "list_changed_files": self._list_changed_files,
            "get_diff_excerpt": self._get_diff_excerpt,
            "submit_summary": self._submit_summary,
        }
        if name not in handlers:
            return json.dumps({"error": f"Unknown tool: {name}"})

        result = handlers[name](arguments)
        self.tool_calls_log.append({"tool": name, "arguments": arguments, "result_preview": result[:300]})
        return result

    def _list_available_skills(self, _: Dict[str, Any]) -> str:
        return json.dumps({"skills": list_skill_versions()})

    def _load_skill(self, arguments: Dict[str, Any]) -> str:
        version = arguments["skill_version"]
        content = load_skill_content(version)
        if version not in self.skills_loaded:
            self.skills_loaded.append(version)
        return json.dumps({"skill_version": version, "content": content})

    def _get_pr_metadata(self, _: Dict[str, Any]) -> str:
        return json.dumps({"id": self.case["id"], "title": self.case["title"]})

    def _get_pr_description(self, _: Dict[str, Any]) -> str:
        return json.dumps({"description": self.case["description"]})

    def _list_changed_files(self, _: Dict[str, Any]) -> str:
        return json.dumps({"changed_files": self.case["changed_files"]})

    def _get_diff_excerpt(self, _: Dict[str, Any]) -> str:
        return json.dumps({"diff_excerpt": self.case["diff_excerpt"]})

    def _submit_summary(self, arguments: Dict[str, Any]) -> str:
        self.final_summary = arguments["summary"]
        return json.dumps({"status": "accepted"})
