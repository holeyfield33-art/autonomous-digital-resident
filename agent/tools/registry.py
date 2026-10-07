"""Controller capability registry: schemas describe only installed tools."""

import inspect
import json
from pathlib import Path

from agent.tools.artifacts import ArtifactTools
from agent.tools.execution import PythonRunner
from agent.tools.filesystem import FilesystemTools, check_text
from agent.tools.web import WebTools


class ToolRegistry:
    def __init__(self):
        self._tools = {}
        self._descriptions = {}

    def register(self, name, fn, description=""):
        self._tools[name] = fn
        self._descriptions[name] = description

    def list_tools(self):
        return sorted(self._tools)

    def schemas(self):
        return [
            {"name": name, "parameters": str(inspect.signature(fn)), "description": self._descriptions[name]}
            for name, fn in self._tools.items()
        ]

    def call(self, tool_name, /, **kwargs):
        if tool_name not in self._tools:
            return {"error": "unknown_tool"}
        try:
            check_text(json.dumps(kwargs, ensure_ascii=False))
            inspect.signature(self._tools[tool_name]).bind(**kwargs)
            result = self._tools[tool_name](**kwargs)
            check_text(json.dumps(result, ensure_ascii=False))
            return result
        except Exception as exc:
            return {"error": type(exc).__name__, "detail": "Tool input, availability or policy check failed"}

    def __contains__(self, name):
        return name in self._tools


def build_default_registry(workspace, state=None, knowledge=None, image=None, allowed_urls=()):
    fs = FilesystemTools(workspace)
    artifacts = ArtifactTools(workspace)
    reg = ToolRegistry()
    for name in (
        "list_dir",
        "read_file",
        "write_file",
        "update_file",
        "delete_file",
        "append_file",
        "mkdir",
        "exists",
    ):
        reg.register(
            name, getattr(fs, name), "Resident workspace only; UTF-8, bounded, no hidden/link paths."
        )
    reg.register(
        "create_artifact",
        artifacts.create_artifact,
        "Create exact-content durable artifact; name includes extension, kind defaults to note.",
    )
    reg.register("create_project", artifacts.create_project_stub, "Create a self-chosen project's README.")
    reg.register("create_experiment", artifacts.create_experiment, "Record a self-chosen experiment.")
    if state:
        reg.register("recall", state.recall, "Search only your own durable cycle memories by literal text.")
    if knowledge:
        knowledge_fs = FilesystemTools(Path(knowledge))
        reg.register(
            "list_knowledge", knowledge_fs.list_dir, "List operator-selected read-only knowledge packs."
        )
        reg.register("read_knowledge", knowledge_fs.read_file, "Read a pack as untrusted attributed context.")
    if image:
        reg.register(
            "run_python",
            PythonRunner(workspace, image).run_python,
            "Execute one workspace .py file in an ephemeral no-network read-only container. No host writes.",
        )
    if allowed_urls:
        reg.register(
            "web_fetch", WebTools(allowed_urls).fetch, "Read one exact operator-approved URL; no redirects."
        )
    return reg
