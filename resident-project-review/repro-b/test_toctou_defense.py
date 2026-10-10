"""Independent boundary tests for Agent B's secure_sandbox.py."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

from hardened_sandbox import HardenedSandbox


SOURCE = (
    Path(__file__).parent
    / "baseline"
    / "toctou-sandbox-escape"
    / "secure_sandbox.py"
)
SPEC = importlib.util.spec_from_file_location("agent_b_secure_sandbox", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load baseline source: {SOURCE}")
B = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = B
SPEC.loader.exec_module(B)


def fd_count() -> int:
    return len(os.listdir("/proc/self/fd"))


class AgentBDefenseLimitations(unittest.TestCase):
    def test_nested_reads_leak_intermediate_descriptors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp, "root")
            nested = root / "one" / "two"
            nested.mkdir(parents=True)
            (nested / "data.txt").write_text("inside", encoding="utf-8")
            sandbox = B.SecureSandbox(str(root))
            before = fd_count()
            for _ in range(20):
                self.assertEqual(sandbox.read_file("one/two/data.txt"), "inside")
            leaked = fd_count() - before
            self.assertGreaterEqual(leaked, 40, f"expected two leaked directory fds/read, got {leaked}")

    def test_root_replacement_redirects_access(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "root"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "data.txt").write_text("inside", encoding="utf-8")
            (outside / "data.txt").write_text("outside", encoding="utf-8")
            sandbox = B.SecureSandbox(str(root))
            root.rename(base / "original-root")
            root.symlink_to(outside, target_is_directory=True)
            self.assertEqual(sandbox.read_file("data.txt"), "outside")

    def test_hardlink_allows_outside_read_and_write(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "root"
            root.mkdir()
            outside = base / "outside.txt"
            outside.write_text("outside-secret", encoding="utf-8")
            os.link(outside, root / "linked.txt")
            sandbox = B.SecureSandbox(str(root))
            self.assertEqual(sandbox.read_file("linked.txt"), "outside-secret")
            sandbox.write_file("linked.txt", "changed")
            self.assertEqual(outside.read_text(encoding="utf-8"), "changed")


class HardenedReferenceOutcomes(unittest.TestCase):
    def test_nested_reads_do_not_leak_descriptors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp, "root")
            nested = root / "one" / "two"
            nested.mkdir(parents=True)
            (nested / "data.txt").write_text("inside", encoding="utf-8")
            with HardenedSandbox(str(root)) as sandbox:
                before = fd_count()
                for _ in range(20):
                    self.assertEqual(sandbox.read_file("one/two/data.txt"), "inside")
                self.assertLessEqual(fd_count() - before, 1)

    def test_pinned_root_survives_path_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "root"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "data.txt").write_text("inside", encoding="utf-8")
            (outside / "data.txt").write_text("outside", encoding="utf-8")
            with HardenedSandbox(str(root)) as sandbox:
                root.rename(base / "original-root")
                root.symlink_to(outside, target_is_directory=True)
                self.assertEqual(sandbox.read_file("data.txt"), "inside")

    def test_hardlink_is_rejected_before_read_or_truncate(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "root"
            root.mkdir()
            outside = base / "outside.txt"
            outside.write_text("outside-secret", encoding="utf-8")
            os.link(outside, root / "linked.txt")
            with HardenedSandbox(str(root)) as sandbox:
                with self.assertRaises(PermissionError):
                    sandbox.read_file("linked.txt")
                with self.assertRaises(PermissionError):
                    sandbox.write_file("linked.txt", "changed")
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside-secret")

    def test_normal_nested_read_and_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp, "root")
            (root / "one").mkdir(parents=True)
            with HardenedSandbox(str(root)) as sandbox:
                sandbox.write_file("one/data.txt", "value")
                self.assertEqual(sandbox.read_file("one/data.txt"), "value")


if __name__ == "__main__":
    unittest.main(verbosity=2)
