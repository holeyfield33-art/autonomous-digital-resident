"""Tool registry — discoverable tools available to the Resident."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from agent.tools.artifacts import ArtifactTools
from agent.tools.filesystem import FilesystemTools
from agent.tools.shell import ShellTools
from agent.tools.web import WebTools


# JSON-serializable tool descriptions the model can use when deciding actions.
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "list_dir",
        "description": "List files and directories under the workspace (relative path).",
        "parameters": {"relative": "str, default '.'"},
    },
    {
        "name": "read_file",
        "description": "Read a text file under the workspace.",
        "parameters": {"relative": "str", "max_chars": "int, optional"},
    },
    {
        "name": "write_file",
        "description": "Write (or overwrite) a text file under the workspace.",
        "parameters": {"relative": "str", "content": "str", "overwrite": "bool, default true"},
    },
    {
        "name": "append_file",
        "description": "Append text to a file under the workspace.",
        "parameters": {"relative": "str", "content": "str"},
    },
    {
        "name": "mkdir",
        "description": "Create a directory under the workspace.",
        "parameters": {"relative": "str"},
    },
    {
        "name": "shell",
        "description": "Run an allowlisted shell command inside the workspace cwd.",
        "parameters": {"command": "str"},
    },
    {
        "name": "web_fetch",
        "description": "Fetch a public http/https URL and return text content.",
        "parameters": {"url": "str"},
    },
    {
        "name": "create_artifact",
        "description": "Create a dated durable artifact under workspace/artifacts.",
        "parameters": {
            "name": "str",
            "content": "str",
            "kind": "str, default note",
            "subdirectory": "str, optional",
        },
    },
    {
        "name": "create_project",
        "description": "Create a new project stub under workspace/projects.",
        "parameters": {"project_name": "str", "description": "str, optional"},
    },
    {
        "name": "create_experiment",
        "description": "Log a new experiment under workspace/experiments.",
        "parameters": {"title": "str", "notes": "str, optional"},
    },
]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        self._tools[name] = fn

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())

    def schemas(self) -> list[dict[str, Any]]:
        return TOOL_SCHEMAS

    def get(self, name: str) -> Callable[..., Any] | None:
        return self._tools.get(name)

    def call(self, name: str, **kwargs: Any) -> Any:
        fn = self._tools.get(name)
        if fn is None:
            return {"error": f"Unknown tool: {name}", "available": self.list_tools()}
        try:
            return fn(**kwargs)
        except TypeError as e:
            return {"error": f"Bad arguments for {name}: {e}"}
        except Exception as e:
            return {"error": str(e), "tool": name}

    def __contains__(self, name: str) -> bool:
        return name in self._tools


def build_default_registry(workspace: Path | str) -> ToolRegistry:
    fs = FilesystemTools(workspace)
    shell = ShellTools(workspace)
    web = WebTools()
    artifacts = ArtifactTools(workspace)

    reg = ToolRegistry()
    reg.register("list_dir", fs.list_dir)
    reg.register("read_file", fs.read_file)
    reg.register("write_file", fs.write_file)
    reg.register("append_file", fs.append_file)
    reg.register("mkdir", fs.mkdir)
    reg.register("exists", fs.exists)
    reg.register("shell", shell.run)
    reg.register("web_fetch", web.fetch)
    reg.register("create_artifact", artifacts.create_artifact)
    reg.register("create_project", artifacts.create_project_stub)
    reg.register("create_experiment", artifacts.create_experiment)
    return reg
