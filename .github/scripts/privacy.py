#!/usr/bin/env python3
"""Check the parent and all six pinned component trees before publication."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from privacy_rules import ATTRIBUTION, CREDENTIALS, path_problem
from sources import entries, git, resolve


def inspect(root, revision='HEAD', *, index=False, history=False):
    findings = []
    for mode, oid, path in entries(root, revision, index=index):
        if mode == '160000':
            continue
        data = git(root, 'cat-file', 'blob', oid)
        reason = path_problem(path, data)
        if reason:
            findings.append((reason, path))
        if any(pattern.search(data) for pattern in CREDENTIALS):
            findings.append(('credential/private-key signature', path))
        if data.startswith(b'SQLite format 3\0'):
            findings.append(('database content', path))
        if ATTRIBUTION.search(data.decode(errors='replace')):
            findings.append(('AI attribution', path))
    try:
        revisions = git(root, 'rev-list', *([revision] if history else ['--max-count=1', revision])).decode().splitlines()
    except subprocess.CalledProcessError:
        if index and not history:
            return findings
        raise
    for commit in revisions:
        if ATTRIBUTION.search(git(root, 'show', '-s', '--format=%B', commit).decode(errors='replace')):
            findings.append(('AI commit attribution', commit))
    return findings


def scan(*, index=False, history=False):
    root = Path(git('.', 'rev-parse', '--show-toplevel').decode().strip())
    links = resolve(root, index=index)
    findings = inspect(root, index=index, history=history)
    for name, oid in links.items():
        findings += [(reason, name + '/' + path) for reason, path in inspect(root / name, oid, history=history)]
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', action='store_true')
    parser.add_argument('--history', action='store_true')
    args = parser.parse_args()
    try:
        findings = scan(index=args.index, history=args.history)
    except (subprocess.CalledProcessError, ValueError) as error:
        print('privacy gate: cannot verify pinned sources: ' + str(error), file=sys.stderr)
        return 1
    for reason, path in findings:
        print(f'privacy gate: {reason}: {json.dumps(path)}', file=sys.stderr)
    if findings:
        return 1
    print('privacy gate: parent and six pinned source trees passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
