"""Resolve only the six public repositories pinned by the parent tree."""
from pathlib import Path
import subprocess

NAMES = ('workspace-state', 'gnome-winctl', 'login-hud', 'hide-suspend',
         'input-source-popup-guard', 'gc-profiled')


def git(root, *args, data=None):
    return subprocess.run(['git', '-C', str(root), *args], input=data,
                          capture_output=True, check=True).stdout


def entries(root, revision='HEAD', *, index=False):
    args = ('ls-files', '--stage', '-z') if index else ('ls-tree', '-r', '-z', revision)
    result = []
    for record in git(root, *args).split(b'\0'):
        if not record:
            continue
        metadata, path = record.split(b'\t', 1)
        mode, middle, last = metadata.decode().split()
        if index:
            if last != '0':
                raise ValueError('unmerged index entry')
            oid = middle
        else:
            oid = last
        result.append((mode, oid, path.decode()))
    return result


def resolve(root, revision='HEAD', *, index=False):
    root = Path(root).resolve()
    records = entries(root, revision, index=index)
    links = {path: oid for mode, oid, path in records if mode == '160000'}
    if set(links) != set(NAMES):
        raise ValueError('parent must pin exactly the six approved public repositories')
    modules = [oid for mode, oid, path in records if path == '.gitmodules' and mode == '100644']
    if len(modules) != 1:
        raise ValueError('missing regular .gitmodules file')
    configuration = git(root, 'config', '--null', '--blob', modules[0], '--list')
    actual = dict(item.decode().split('\n', 1) for item in configuration.split(b'\0') if item)
    expected = {}
    for name in NAMES:
        expected[f'submodule.{name}.path'] = name
        expected[f'submodule.{name}.url'] = f'https://github.com/Sage-Cat/{name}.git'
    if actual != expected:
        raise ValueError('unsupported submodule configuration')
    for name, oid in links.items():
        child = root / name
        if child.is_symlink() or not (child / '.git').exists():
            raise ValueError(f'uninitialized submodule: {name}')
        if git(child, 'rev-parse', '--show-toplevel').decode().strip() != str(child):
            raise ValueError(f'invalid submodule checkout: {name}')
        if git(child, 'rev-parse', 'HEAD').decode().strip() != oid:
            raise ValueError(f'checkout differs from pinned commit: {name}')
        if any(mode == '160000' for mode, _, _ in entries(child, oid)):
            raise ValueError(f'nested submodules are unsupported: {name}')
    return links
