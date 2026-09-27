"""Isolated Git fixtures; never stage or schedule the host desktop."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("workspace", Path(__file__).resolve().parents[1] / "scripts/workspace.py")
workspace = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workspace)


class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git(self.root, "init", "-q")
        modules = []
        for name in workspace.PROJECTS:
            child = self.root / name
            child.mkdir()
            self.git(child, "init", "-q")
            (child / "source.txt").write_text("source\n")
            (child / ".gitignore").write_text("local-private/\n")
            self.git(child, "add", "source.txt", ".gitignore")
            self.git(child, "-c", "commit.gpgsign=false", "commit", "-qm", "Initial fixture")
            sha = self.git(child, "rev-parse", "HEAD").strip()
            self.git(self.root, "update-index", "--add", "--cacheinfo", f"160000,{sha},{name}")
            modules.append(f'[submodule "{name}"]\n path = {name}\n url = https://github.com/Sage-Cat/{name}.git\n')
        (self.root / ".gitmodules").write_text("\n".join(modules))
        self.git(self.root, "add", ".gitmodules")

    @staticmethod
    def git(root, *args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True, stderr=subprocess.PIPE)

    def test_clean_checkout_and_ignored_private_files(self):
        local = self.root / "workspace-state/local-private"
        local.mkdir()
        (local / "settings").write_text("private fixture")
        self.assertEqual(set(workspace.check(self.root)), set(workspace.PROJECTS))

    def test_missing_gitlink(self):
        self.git(self.root, "update-index", "--force-remove", "gc-profiled")
        with self.assertRaisesRegex(ValueError, "exactly the six"):
            workspace.check(self.root)

    def test_uninitialized_submodule(self):
        child = self.root / "hide-suspend"
        (child / ".git").rename(child / "hidden-git")
        with self.assertRaisesRegex(ValueError, "Initialize"):
            workspace.check(self.root)

    def test_wrong_pin(self):
        child = self.root / "login-hud"
        self.git(child, "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "Another revision")
        with self.assertRaisesRegex(ValueError, "staged pin"):
            workspace.check(self.root)

    def test_modified_and_untracked_files_block_checks(self):
        child = self.root / "gnome-winctl"
        for filename in ("source.txt", "new-file"):
            with self.subTest(filename=filename):
                file = child / filename
                original = file.read_text() if file.exists() else None
                file.write_text("local work\n")
                with self.assertRaisesRegex(ValueError, "local changes"):
                    workspace.check(self.root)
                if original is None:
                    file.unlink()
                else:
                    file.write_text(original)

    def test_symlink_submodule(self):
        child = self.root / "gc-profiled"
        other = self.root / "other"
        child.rename(other)
        child.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "no symlinks"):
            workspace.check(self.root)

    def test_unknown_or_private_submodule(self):
        modules = self.root / ".gitmodules"
        modules.write_text(modules.read_text() + '\n[submodule "private-tool"]\n path = private-tool\n url = https://example.invalid/private.git\n')
        with self.assertRaisesRegex(ValueError, "exactly the six"):
            workspace.check(self.root)

    def test_changed_remote_rejected(self):
        modules = self.root / ".gitmodules"
        modules.write_text(modules.read_text().replace("https://github.com/Sage-Cat/login-hud.git", "https://example.invalid/login-hud.git"))
        with self.assertRaisesRegex(ValueError, "configuration: login-hud"):
            workspace.check(self.root)

    def test_staged_metadata_must_match_reviewed_file(self):
        modules = self.root / ".gitmodules"
        original = modules.read_text()
        modules.write_text(original.replace("https://github.com/Sage-Cat/login-hud.git", "https://example.invalid/login-hud.git"))
        self.git(self.root, "add", ".gitmodules")
        modules.write_text(original)
        with self.assertRaisesRegex(ValueError, "Stage the reviewed"):
            workspace.check(self.root)

    def release_manifest(self, pattern="**/*.py"):
        return f'[[components]]\nname = "workspace-state"\nsource = "workspace-state"\nfiles = ["{pattern}"]\n'

    def test_ignored_source_matching_release_glob_rejected(self):
        private = self.root / "workspace-state/local-private"
        private.mkdir()
        (private / "local.py").write_text("private fixture\n")
        pinned = workspace.check(self.root)
        with self.assertRaisesRegex(ValueError, "not a pinned regular file"):
            workspace.verify_release_sources(self.root, self.release_manifest(), pinned)

    def test_pinned_source_bytes_and_executable_mode_checked(self):
        child = self.root / "workspace-state"
        file = child / "source.txt"
        pinned = workspace.check(self.root)
        manifest = self.release_manifest("source.txt")
        workspace.verify_release_sources(self.root, manifest, pinned)
        self.git(child, "update-index", "--assume-unchanged", "source.txt")
        file.write_text("unreported local data\n")
        workspace.check(self.root)
        with self.assertRaisesRegex(ValueError, "differs from its pinned blob"):
            workspace.verify_release_sources(self.root, manifest, pinned)
        file.write_text("source\n")
        file.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "differs from its pinned blob"):
            workspace.verify_release_sources(self.root, manifest, pinned)

    def test_cache_glob_matches_are_excluded(self):
        child = self.root / "workspace-state"
        cache = child / "local-private/__pycache__"
        cache.mkdir(parents=True)
        (cache / "generated.py").write_text("cache fixture\n")
        workspace.verify_release_sources(self.root, self.release_manifest(), workspace.check(self.root))

    def test_nested_submodule_rejected(self):
        child = self.root / "workspace-state"
        sha = self.git(child, "rev-parse", "HEAD").strip()
        self.git(child, "update-index", "--add", "--cacheinfo", f"160000,{sha},nested")
        self.git(child, "-c", "commit.gpgsign=false", "commit", "-qm", "Add nested fixture")
        sha = self.git(child, "rev-parse", "HEAD").strip()
        self.git(self.root, "update-index", "--cacheinfo", f"160000,{sha},workspace-state")
        with self.assertRaisesRegex(ValueError, "Nested submodules"):
            workspace.check(self.root)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "workspace-state/config/desktop-release.toml"
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text('''schema_version = 1
[[components]]
name = "coordinator"
source = "workspace-state"
files = ["src/*.py"]
[[components]]
name = "unlisted-local-tool"
source = "unlisted-local-tool"
files = ["*.py"]
[[components]]
name = "host-integration"
source = "workspace-state/host-integration"
files = ["bin/*"]
''')

    def test_private_components_excluded_and_internal_components_preserved(self):
        result = tomllib.loads(workspace.public_manifest(self.root))
        self.assertEqual([c["name"] for c in result["components"]], ["coordinator", "host-integration"])

    def test_traversal_and_symlink_sources_rejected(self):
        original = self.manifest.read_text()
        self.manifest.write_text(original.replace('source = "workspace-state/host-integration"', 'source = "workspace-state/../outside"'))
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            workspace.public_manifest(self.root)
        self.manifest.write_text(original)
        (self.root / "workspace-state/host-integration").symlink_to(self.root)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            workspace.public_manifest(self.root)

    def test_delegate_explicit_source_root_private_manifest_and_next_login(self):
        captured = []

        def fake_run(command, **kwargs):
            captured.append(command)
            manifest = Path(command[command.index("--manifest") + 1])
            self.assertEqual(manifest.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("unlisted-local-tool", manifest.read_text())
            self.assertEqual(command[command.index("--source-root") + 1], str(self.root))
            return subprocess.CompletedProcess(command, 0)

        with patch.object(workspace, "check") as checker, patch.object(workspace, "verify_release_sources") as verifier, patch.object(workspace.subprocess, "run", side_effect=fake_run):
            self.assertEqual(workspace.delegate(self.root, "deploy", True), 0)
            checker.assert_called_once_with(self.root)
            self.assertEqual(verifier.call_count, 2)
            self.assertIn('files = ["config/desktop-release.toml"]', verifier.call_args_list[0].args[1])
        self.assertEqual(captured[0][-2:], ["deploy", "--host-integration"])
        self.assertFalse(Path(captured[0][3]).exists())

    def test_failed_check_prevents_deployment(self):
        with patch.object(workspace, "check", side_effect=ValueError("dirty")), patch.object(workspace.subprocess, "run") as runner:
            with self.assertRaisesRegex(ValueError, "dirty"):
                workspace.delegate(self.root, "stage")
            runner.assert_not_called()

    def test_immediate_install_is_not_supported(self):
        with self.assertRaisesRegex(ValueError, "next-login"):
            workspace.delegate(self.root, "install")


if __name__ == "__main__":
    unittest.main()
