"""Controller capability registry: schemas describe only installed tools; failures come back as data."""

import difflib
import inspect
import json
from pathlib import Path

from agent.tools.artifacts import ArtifactTools
from agent.tools.execution import PythonRunner
from agent.tools.filesystem import FilesystemTools, check_text

# Names models commonly reach for, mapped to the installed tool that does the job.
TOOL_ALIASES = {
    "rm": "delete", "remove": "delete", "remove_file": "delete", "delete_file": "delete",
    "delete_path": "delete", "remove_path": "delete", "rmdir": "delete", "remove_dir": "delete",
    "delete_dir": "delete", "unlink": "delete",
    "mv": "move", "rename": "move", "move_file": "move", "rename_file": "move",
    "cp": "copy", "copy_file": "copy",
    "ls": "list_dir", "list_files": "list_dir", "list_directory": "list_dir",
    "cat": "read_file", "open_file": "read_file",
    "create_file": "write_file", "mkdirs": "mkdir", "make_dir": "mkdir", "create_dir": "mkdir",
    "grep": "search_text", "search_files": "search_text", "find": "find_files", "glob": "find_files",
    "bash": "shell", "sh": "shell", "run_shell": "shell", "run_shell_command": "shell",
    "run_command": "shell", "exec": "shell", "execute": "shell", "terminal": "shell",
    "run_python": "python", "python_exec": "python", "execute_python": "python", "run_code": "python",
    "search": "web_search", "google": "web_search", "fetch": "web_fetch", "fetch_url": "web_fetch",
    "browse": "web_fetch", "http_get": "web_fetch",
    "recall": "search_memory", "memory_search": "search_memory", "status": "system_status",
}
# Argument names models commonly use for the canonical parameter.
ARG_ALIASES = {
    "path": ("relative", "file", "file_path", "filepath", "filename", "dir", "directory", "folder", "relative_path"),
    "content": ("text", "data", "contents", "body"),
    "source": ("src", "from", "from_path", "source_path", "old_path"),
    "destination": ("dst", "dest", "to", "to_path", "target", "new_path", "destination_path"),
    "command": ("cmd", "script"),
    "code": ("source_code", "python", "program"),
    "query": ("q", "search", "term", "pattern_text"),
    "old_text": ("old", "old_string", "find", "search_text"),
    "new_text": ("new", "new_string", "replace", "replacement"),
}
TYPE_NAMES = {str: "string", int: "integer", bool: "boolean", float: "number", dict: "object", list: "array"}


def _coerce(value, annotation):
    if annotation is bool and isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if annotation is int and isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    if annotation is int and isinstance(value, float) and value.is_integer():
        return int(value)
    return value


class ToolRegistry:
    def __init__(self, workspace=None):
        self._tools, self._descriptions, self._examples = {}, {}, {}
        self._workspace = str(Path(workspace).resolve()) if workspace else None

    def register(self, name, fn, description="", example=None):
        self._tools[name] = fn
        doc = (inspect.getdoc(fn) or "").strip()
        self._descriptions[name] = description or doc
        if example is not None:
            self._examples[name] = example

    def list_tools(self):
        return sorted(self._tools)

    def _parameters(self, fn):
        params = {}
        for p in inspect.signature(fn).parameters.values():
            spec = {"type": TYPE_NAMES.get(p.annotation, "string")}
            if p.default is inspect.Parameter.empty:
                spec["required"] = True
            else:
                spec["default"] = p.default
            params[p.name] = spec
        return params

    def usage(self, name):
        fn = self._tools[name]
        parts = []
        for pname, spec in self._parameters(fn).items():
            parts.append(pname if spec.get("required") else f"{pname}={json.dumps(spec['default'])}")
        return f"{name}({', '.join(parts)})"

    def schemas(self):
        out = []
        for name, fn in self._tools.items():
            item = {"name": name, "usage": self.usage(name), "description": self._descriptions[name]}
            if name in self._examples:
                item["example"] = self._examples[name]
            out.append(item)
        return out

    def resolve(self, name):
        if name in self._tools:
            return name
        alias = TOOL_ALIASES.get(name)
        return alias if alias in self._tools else None

    def _normalize(self, name, kwargs):
        signature = inspect.signature(self._tools[name])
        params = signature.parameters
        fixed = {}
        for key, value in kwargs.items():
            if key not in params:
                for canonical, aliases in ARG_ALIASES.items():
                    if key in aliases and canonical in params and canonical not in kwargs:
                        key = canonical
                        break
            if key in params:
                value = _coerce(value, params[key].annotation)
            fixed[key] = value
        return fixed

    def _clean(self, message):
        if self._workspace:
            message = message.replace(self._workspace + "\\", "").replace(self._workspace, "/workspace")
        return message[:600]

    def call(self, tool_name, /, **kwargs):
        name = self.resolve(tool_name)
        if name is None:
            close = difflib.get_close_matches(tool_name, list(self._tools), n=3, cutoff=0.5)
            return {
                "error": "unknown_tool",
                "message": f"No tool named {tool_name!r}." + (f" Did you mean {close}?" if close else ""),
                "available_tools": self.list_tools(),
            }
        try:
            kwargs = self._normalize(name, kwargs)
            try:
                inspect.signature(self._tools[name]).bind(**kwargs)
            except TypeError as exc:
                raise TypeError(f"{exc}. Correct usage: {self.usage(name)}") from None
            result = self._tools[name](**kwargs)
            if name != tool_name and isinstance(result, dict):
                result = {**result, "note": f"{tool_name!r} is not a tool; ran {name!r} instead"}
            return result
        except Exception as exc:
            return {
                "error": type(exc).__name__,
                "message": self._clean(str(exc)) or type(exc).__name__,
                "usage": self.usage(name),
            }

    def __contains__(self, name):
        return name in self._tools


def build_default_registry(
    workspace, state=None, knowledge=None, image=None, web=None, sandbox=None, introspection=None
):
    fs = FilesystemTools(workspace)
    artifacts = ArtifactTools(workspace)
    reg = ToolRegistry(workspace)
    examples = {
        "read_file": {"path": "consciousness/index.md"},
        "write_file": {"path": "notes/idea.md", "content": "# Idea\n...", "overwrite": False},
        "edit_file": {"path": "notes/idea.md", "old_text": "old line", "new_text": "new line"},
        "move": {"source": "old_name.txt", "destination": "archive/old_name.txt"},
        "delete": {"path": "scratch", "recursive": True},
        "search_text": {"query": "timestamp", "path": ".", "file_glob": "*.py"},
        "find_files": {"pattern": "*.md"},
    }
    for name in (
        "list_dir", "read_file", "write_file", "edit_file", "append_file", "update_file",
        "move", "copy", "delete", "mkdir", "exists", "file_info", "find_files", "search_text",
    ):
        reg.register(name, getattr(fs, name), example=examples.get(name))
    reg.register(
        "create_artifact",
        artifacts.create_artifact,
        "Create a timestamped, never-overwritten file under artifacts/. name includes extension.",
    )
    reg.register("create_project", artifacts.create_project_stub, "Create projects/<name>/README.md.")
    reg.register("create_experiment", artifacts.create_experiment, "Record an experiment note under artifacts/.")
    if state:
        reg.register("search_memory", state.search_memory, example={"query": "timestamp logger"})
        reg.register("cycle_history", state.cycle_history)
        reg.register("get_cycle", state.get_cycle, example={"cycle": 120})
    if introspection:
        reg.register("system_status", introspection)
    if knowledge:
        knowledge_fs = FilesystemTools(Path(knowledge))
        reg.register("list_knowledge", knowledge_fs.list_dir, "List operator-provided read-only knowledge packs.")
        reg.register("read_knowledge", knowledge_fs.read_file, "Read a knowledge pack (untrusted reference text).")
    if web:
        reg.register("web_search", web.search, example={"query": "latest research on agent memory"})
        reg.register("web_fetch", web.fetch, example={"url": "https://example.com/article"})
    if sandbox:
        reg.register("shell", sandbox.shell, example={"command": "python3 script.py", "cwd": "."})
        reg.register("python", sandbox.python, example={"code": "import math\nprint(math.pi)"})
    elif image:
        reg.register(
            "python",
            PythonRunner(workspace, image).run_python,
            "Execute one workspace .py file (path) in an ephemeral no-network container.",
        )
    return reg


__all__ = ["ToolRegistry", "build_default_registry", "check_text"]
