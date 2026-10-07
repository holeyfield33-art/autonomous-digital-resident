"""Artifacts retain exact content, hashes and collision-free names."""

import re
import uuid
from datetime import datetime, timezone

from agent.tools.filesystem import FilesystemTools


def slug(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value):
        raise ValueError("Use a short alphanumeric filename")
    return value


class ArtifactTools:
    def __init__(self, workspace):
        self.fs = FilesystemTools(workspace)

    def create_artifact(self, name, content, kind="note", subdirectory=""):
        if kind not in {"note", "code", "research", "experiment", "writing", "tool"}:
            raise ValueError("Unknown artifact kind")
        prefix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
        directory = "artifacts" + ("/" + slug(subdirectory) if subdirectory else "")
        return {**self.fs.write_file(f"{directory}/{prefix}_{slug(name)}", content), "kind": kind}

    def create_project_stub(self, project_name, description=""):
        return self.fs.write_file(
            f"projects/{slug(project_name)}/README.md", f"# {project_name}\n\n{description}\n"
        )

    def create_experiment(self, title, notes=""):
        return self.create_artifact(slug(title) + ".md", notes, kind="experiment", subdirectory="experiments")
