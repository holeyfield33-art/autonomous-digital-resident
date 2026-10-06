"""Artifact helpers — structured way to leave durable work products."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ArtifactTools:
    def __init__(self, workspace: Path | str) -> None:
        self.workspace = Path(workspace).resolve()
        self.artifacts_dir = self.workspace / "artifacts"
        self.projects_dir = self.workspace / "projects"
        self.experiments_dir = self.workspace / "experiments"
        for d in (self.artifacts_dir, self.projects_dir, self.experiments_dir):
            d.mkdir(parents=True, exist_ok=True)

    def create_artifact(
        self,
        name: str,
        content: str,
        kind: str = "note",
        subdirectory: str = "",
    ) -> dict[str, Any]:
        """Write a dated artifact under workspace/artifacts."""
        safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        rel = Path("artifacts") / subdirectory / f"{ts}_{safe_name}"
        path = self.workspace / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        header = f"# Artifact: {name}\n# kind: {kind}\n# created: {ts}\n\n"
        path.write_text(header + content, encoding="utf-8")
        return {"path": str(rel), "kind": kind, "status": "created"}

    def create_project_stub(self, project_name: str, description: str = "") -> dict[str, Any]:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_name)
        root = self.projects_dir / safe
        root.mkdir(parents=True, exist_ok=True)
        readme = root / "README.md"
        if not readme.exists():
            readme.write_text(
                f"# {project_name}\n\n{description}\n\n_Started by Autonomous Digital Resident._\n",
                encoding="utf-8",
            )
        return {"path": f"projects/{safe}", "status": "ready"}

    def create_experiment(self, title: str, notes: str = "") -> dict[str, Any]:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:60]
        path = self.experiments_dir / f"{ts}_{safe}.md"
        path.write_text(
            f"# Experiment: {title}\n\nCreated: {ts}\n\n{notes}\n",
            encoding="utf-8",
        )
        return {"path": f"experiments/{path.name}", "status": "created"}
