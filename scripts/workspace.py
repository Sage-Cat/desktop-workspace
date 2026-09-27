#!/usr/bin/env python3
"""Check the pinned desktop checkout and delegate release staging."""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import tomllib

PROJECTS = (
    "workspace-state", "gnome-winctl", "login-hud", "hide-suspend",
    "input-source-popup-guard", "gc-profiled",
)
# Matches workspace-state.deployment._source_files. Only these source paths are
# omitted; an ignored file elsewhere is not automatically safe to package.
SOURCE_EXCLUDED = {".git", "node_modules", "__pycache__", "profiles", "logs", "snapshots", "sessions", ".env"}


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise ValueError(f"Git failed in {root.name}: {result.stderr.strip()}")
    return result.stdout


def pins(root: Path) -> dict[str, str]:
    """Read the index so reviewed pin updates can be checked before committing."""
    found = {}
    for entry in git(root, "ls-files", "--stage", "-z").split("\0"):
        if not entry:
            continue
        details, name = entry.split("\t", 1)
        mode, sha, stage = details.split()
        if stage != "0":
            raise ValueError("Resolve the parent index conflicts first")
        if mode == "160000":
            found[name] = sha
    if set(found) != set(PROJECTS):
        raise ValueError("The parent index must contain exactly the six public gitlinks")
    return found


def check(root: Path) -> dict[str, str]:
    if root.is_symlink():
        raise ValueError("The workspace root must not be a symlink")
    root = root.resolve()
    if Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve() != root:
        raise ValueError("Use the parent repository root")
    modules = root / ".gitmodules"
    if modules.is_symlink():
        raise ValueError(".gitmodules must not be a symlink")
    config = configparser.ConfigParser(interpolation=None, strict=True)
    config.read_string(modules.read_text())
    expected = {f'submodule "{name}"' for name in PROJECTS}
    if set(config.sections()) != expected or config.defaults():
        raise ValueError(".gitmodules must list exactly the six public projects")
    for name in PROJECTS:
        section = config[f'submodule "{name}"']
        if dict(section) != {"path": name, "url": f"https://github.com/Sage-Cat/{name}.git"}:
            raise ValueError(f"Unexpected submodule configuration: {name}")
    if git(root, "show", ":.gitmodules") != modules.read_text():
        raise ValueError("Stage the reviewed .gitmodules before checking pins")
    result = pins(root)
    for name, sha in result.items():
        child = root / name
        if child.is_symlink() or not (child / ".git").exists():
            raise ValueError(f"Initialize the submodule first (no symlinks): {name}")
        if Path(git(child, "rev-parse", "--show-toplevel").strip()).resolve() != child:
            raise ValueError(f"Not an initialized submodule: {name}")
        if git(child, "rev-parse", "HEAD").strip() != sha:
            raise ValueError(f"Submodule does not match the staged pin: {name}")
        if any(entry.startswith("160000 ") for entry in git(child, "ls-tree", "-r", sha).splitlines()):
            raise ValueError(f"Nested submodules are not supported: {name}")
        if git(child, "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none").strip():
            raise ValueError(f"Commit or remove local changes before release staging: {name}")
    return result


def public_manifest(root: Path) -> str:
    """Keep public components, including host components within workspace-state."""
    source = root / "workspace-state/config/desktop-release.toml"
    text = source.read_text()
    parsed = tomllib.loads(text)
    chunks = re.split(r"(?m)^\[\[components\]\][ \t]*\r?$", text)
    if len(chunks) != len(parsed.get("components", [])) + 1:
        raise ValueError("Unsupported release manifest layout")
    selected = []
    chunks_kept = [chunks[0]]
    for component, chunk in zip(parsed["components"], chunks[1:]):
        path = PurePosixPath(component["source"])
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError("Unsafe component source in release manifest")
        if path.parts[0] not in PROJECTS:
            continue
        candidate = root
        for part in path.parts:
            candidate /= part
            if candidate.is_symlink():
                raise ValueError("Component sources must not contain symlinks")
        selected.append(component)
        chunks_kept.append("[[components]]" + chunk)
    filtered = "".join(chunks_kept)
    expected = dict(parsed, components=selected)
    if tomllib.loads(filtered) != expected:
        raise ValueError("Release manifest filtering changed component definitions")
    if not selected:
        raise ValueError("Release manifest contains no public components")
    return filtered


def verify_release_sources(root: Path, manifest: str, pinned: dict[str, str]) -> None:
    """Verify selected worktree bytes against Git blobs, bypassing clean filters."""
    trees = {}
    algorithms = {}
    for name, revision in pinned.items():
        entries = {}
        for entry in git(root / name, "ls-tree", "-r", "-z", revision).split("\0"):
            if entry:
                details, path = entry.split("\t", 1)
                mode, kind, oid = details.split()
                entries[path] = (mode, kind, oid)
        trees[name] = entries
        algorithms[name] = git(root / name, "rev-parse", "--show-object-format").strip()
    for component in tomllib.loads(manifest)["components"]:
        relative_source = PurePosixPath(component["source"])
        name = relative_source.parts[0]
        source = root / relative_source
        for pattern in component["files"]:
            relative_pattern = PurePosixPath(pattern)
            if relative_pattern.is_absolute() or ".." in relative_pattern.parts:
                raise ValueError("Unsafe source file pattern")
            for path in source.glob(pattern):
                if any(part in SOURCE_EXCLUDED for part in path.relative_to(source).parts):
                    continue
                if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents):
                    raise ValueError(f"Release source contains a symlink: {path.relative_to(root)}")
                if not path.is_file():
                    continue
                relative = path.relative_to(root / name).as_posix()
                tracked = trees[name].get(relative)
                if not tracked or tracked[0] not in {"100644", "100755"} or tracked[1] != "blob":
                    raise ValueError(f"Release source is not a pinned regular file: {name}/{relative}")
                contents = path.read_bytes()
                digest = hashlib.new(algorithms[name], b"blob " + str(len(contents)).encode() + b"\0" + contents).hexdigest()
                if digest != tracked[2] or bool(path.stat().st_mode & 0o111) != (tracked[0] == "100755"):
                    raise ValueError(f"Release source differs from its pinned blob: {name}/{relative}")


def delegate(root: Path, action: str, host_integration: bool = False) -> int:
    if action not in {"stage", "deploy"} or (host_integration and action != "deploy"):
        raise ValueError("Only stage and next-login deploy are supported")
    pinned = check(root)
    root = root.resolve()
    # Validate the manifest before trusting its own source selection rules.
    verify_release_sources(root, '''[[components]]
name = "workspace-state"
source = "workspace-state"
files = ["config/desktop-release.toml"]
''', pinned)
    manifest = public_manifest(root)
    verify_release_sources(root, manifest, pinned)
    # NamedTemporaryFile is owner-readable/writable only and is removed on exit.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", prefix="desktop-workspace-") as handle:
        handle.write(manifest)
        handle.flush()
        command = [str(root / "workspace-state/bin/wsctl"), "deployment",
                   "--manifest", handle.name, "--source-root", str(root), action]
        if host_integration:
            command.append("--host-integration")
        return subprocess.run(command, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="verify public modules, pins and clean checkouts")
    commands.add_parser("pins", help="print the six staged commit pins as JSON")
    commands.add_parser("stage", help="build a release without installing it")
    deploy = commands.add_parser("deploy", help="stage and schedule installation at next login")
    deploy.add_argument("--host-integration", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command in {"stage", "deploy"}:
            return delegate(args.root, args.command, getattr(args, "host_integration", False))
        result = check(args.root) if args.command == "check" else pins(args.root)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, configparser.Error) as error:
        parser.exit(1, f"workspace: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
