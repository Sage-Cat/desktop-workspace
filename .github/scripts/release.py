#!/usr/bin/env python3
"""Build committed artifacts and publish append-only releases using repository GH_TOKEN."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import quote
import tarfile

from sources import git, resolve
from privacy import scan


def command(*args, data=None):
    return subprocess.run(args, input=data, capture_output=True, check=True).stdout


def api(endpoint, method='GET', payload=None, missing=False):
    args = ['gh', 'api', endpoint, '--method', method]
    if payload is not None:
        args += ['--input', '-']
    try:
        raw = command(*args, data=json.dumps(payload).encode() if payload is not None else None)
    except subprocess.CalledProcessError as error:
        if missing and b'(HTTP 404)' in error.stderr:
            return None
        raise
    return json.loads(raw) if raw else None


def checked_sha(value):
    if not re.fullmatch(r'[0-9a-f]{40}', value):
        raise ValueError('expected full lowercase commit SHA')
    return value


def prepare(sha, output):
    checked_sha(sha)
    root = Path(command('git', 'rev-parse', '--show-toplevel').decode().strip())
    if command('git', 'rev-parse', 'HEAD').decode().strip() != sha:
        raise ValueError('artifact commit must equal checked-out HEAD')
    links = resolve(root, sha)
    if scan(history=True):
        raise ValueError('privacy gate refused committed source trees')
    config = json.loads(command('git', 'show', f'{sha}:.github/release.json'))
    name = config['name']
    if not re.fullmatch(r'[a-z0-9-]+', name):
        raise ValueError('invalid package name')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('artifact directory must be empty')
    prefix = f'{name}-{sha}/'
    lock = json.dumps({'parent_commit': sha, 'repositories': links}, sort_keys=True, indent=2).encode() + b'\n'
    # Keep reproducibility without pre-1980 dates that break ZIP builders.
    timestamp = max(315619200, int(git(root, 'show', '-s', '--format=%ct', sha)))
    buffer = io.BytesIO()
    names = set()
    with tarfile.open(fileobj=buffer, mode='w', format=tarfile.PAX_FORMAT) as archive:
        sources = [(root, sha, prefix)] + [(root / child, oid, prefix + child + '/')
                                            for child, oid in sorted(links.items())]
        for source_root, oid, source_prefix in sources:
            source = git(source_root, 'archive', '--format=tar', '--prefix=' + source_prefix, oid)
            with tarfile.open(fileobj=io.BytesIO(source), mode='r:') as original:
                for member in original:
                    if member.name.rstrip('/') == prefix.rstrip('/') + '/sources.lock.json':
                        raise ValueError('reserved source provenance filename')
                    if member.name in names:
                        if member.isdir():
                            continue
                        raise ValueError('duplicate source archive entry')
                    names.add(member.name)
                    member.uid = member.gid = 0
                    member.mtime = timestamp
                    member.uname = member.gname = ''
                    member.pax_headers = {}
                    archive.addfile(member, original.extractfile(member) if member.isfile() else None)
        info = tarfile.TarInfo(prefix + 'sources.lock.json')
        info.mode = 0o644
        info.mtime = timestamp
        info.size = len(lock)
        archive.addfile(info, io.BytesIO(lock))
    compressed = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=compressed, mode='wb', compresslevel=0, mtime=0) as archive:
        archive.write(buffer.getvalue())
    (output / f'{name}-{sha}.tar.gz').write_bytes(compressed.getvalue())
    (output / 'sources.lock.json').write_bytes(lock)
    sums = ''.join(f'{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.name}\n'
                   for file in sorted(output.iterdir()))
    (output / 'SHA256SUMS').write_text(sums)


def tag_commit(repo, tag):
    ref = api(f'repos/{repo}/git/ref/tags/{tag}', missing=True)
    if ref is None:
        return None
    obj = ref['object']
    for _ in range(8):
        if obj['type'] == 'commit':
            return obj['sha']
        if obj['type'] != 'tag':
            break
        obj = api(f'repos/{repo}/git/tags/{obj["sha"]}')['object']
    raise ValueError('release tag does not resolve to a commit')


def verify_assets(repo, release, files):
    existing = {asset['name']: asset for asset in release['assets']}
    if len(existing) != len(release['assets']) or set(existing) - set(files):
        raise ValueError('release contains unexpected or duplicate assets')
    for name, asset in existing.items():
        expected = 'sha256:' + hashlib.sha256(files[name].read_bytes()).hexdigest()
        digest = asset.get('digest')
        if not digest:
            raw = command('gh', 'api', f'repos/{repo}/releases/assets/{asset["id"]}',
                          '-H', 'Accept: application/octet-stream')
            digest = 'sha256:' + hashlib.sha256(raw).hexdigest()
        if asset.get('state') != 'uploaded' or digest != expected:
            raise ValueError(f'existing asset differs: {name}; refusing replacement')
    return sorted(set(files) - set(existing))


def promote_current_commit(repo, sha, release):
    """Only the current default-branch commit may advance the Latest pointer."""
    latest = api(f'repos/{repo}/releases/latest', missing=True)
    if latest and latest['id'] == release['id']:
        return release
    branch = api(f'repos/{repo}')['default_branch']
    head = api(f'repos/{repo}/git/ref/heads/{quote(branch, safe="")}')['object']
    # Query immediately before promotion, after every potentially slow upload.
    if head['type'] == 'commit' and head['sha'] == sha:
        return api(f'repos/{repo}/releases/{release["id"]}', 'PATCH', {'make_latest': 'true'})
    return release


def promote_latest(repo):
    """Promote the current published branch head, regardless of triggering run."""
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('invalid GitHub repository')
    branch = api(f'repos/{repo}')['default_branch']
    head = api(f'repos/{repo}/git/ref/heads/{quote(branch, safe="")}')['object']
    if head['type'] != 'commit':
        raise ValueError('default branch does not reference a commit')
    sha = checked_sha(head['sha'])
    tag = f'build-{sha}'
    release = api(f'repos/{repo}/releases/tags/{tag}', missing=True)
    result = {'commit': sha, 'tag': tag, 'status': 'awaiting_published_release'}
    if release and not release['draft']:
        if tag_commit(repo, tag) != sha or release['tag_name'] != tag:
            raise ValueError('current branch release tag targets another commit')
        release = promote_current_commit(repo, sha, release)
        latest = api(f'repos/{repo}/releases/latest', missing=True)
        result.update(status='latest' if latest and latest['id'] == release['id'] else 'head_changed',
                      url=release['html_url'])
    print(json.dumps(result))
    return result


def publish(repo, sha, output, tag=None, *, update_latest=True):
    checked_sha(sha)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('invalid GitHub repository')
    tag = tag or f'build-{sha}'
    if tag != f'build-{sha}' and not re.fullmatch(r'v[0-9][A-Za-z0-9._-]*', tag):
        raise ValueError('expected commit-addressed or semantic version tag')
    files = {file.name: file for file in Path(output).iterdir() if file.is_file()}
    if 'SHA256SUMS' not in files or len(files) < 2:
        raise ValueError('release artifacts are missing')
    target = tag_commit(repo, tag)
    if target is None:
        if not tag.startswith('build-'):
            raise ValueError('semantic release requires an existing tag')
        api(f'repos/{repo}/git/refs', 'POST', {'ref': f'refs/tags/{tag}', 'sha': sha})
    elif target != sha:
        raise ValueError('existing release tag targets another commit; refusing to move it')
    endpoint = f'repos/{repo}/releases/tags/{tag}'
    release = api(endpoint, missing=True)
    if release is None:
        release = api(f'repos/{repo}/releases', 'POST', {
            'tag_name': tag, 'target_commitish': sha, 'name': f'{repo.split("/")[1]} {tag}',
            'body': f'Checked source commit: `{sha}`.\n\nArtifacts and SHA256SUMS are append-only; reruns verify existing bytes.',
            'draft': True, 'prerelease': False, 'make_latest': 'false' if tag.startswith('build-') else 'true'})
    missing = verify_assets(repo, release, files)
    if missing and not release['draft']:
        raise ValueError('published release lacks expected assets; refusing to modify it')
    for name in missing:
        # No --clobber: concurrent uploads fail safely and can be retried.
        command('gh', 'release', 'upload', tag, str(files[name]), '--repo', repo)
    release = api(f'repos/{repo}/releases/{release["id"]}')
    if verify_assets(repo, release, files) or tag_commit(repo, tag) != sha:
        raise ValueError('release changed during preparation')
    if release['draft']:
        release = api(f'repos/{repo}/releases/{release["id"]}', 'PATCH', {'draft': False, 'make_latest': 'false' if tag.startswith('build-') else 'true'})
    if update_latest and tag.startswith('build-'):
        release = promote_current_commit(repo, sha, release)
    result = {'tag': tag, 'commit': sha, 'url': release['html_url'],
              'append_only_verified': True, 'github_immutable': bool(release.get('immutable', False))}
    print(json.dumps(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'publish', 'promote'])
    parser.add_argument('--sha', default=os.environ.get('GITHUB_SHA'))
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY'))
    parser.add_argument('--output', default='release-dist')
    parser.add_argument('--tag')
    parser.add_argument('--skip-promotion', action='store_true', help='publish assets; leave Latest for the serialized promotion job')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.sha, args.output)
    elif args.action == 'promote':
        promote_latest(args.repo)
    else:
        publish(args.repo, args.sha, args.output, args.tag, update_latest=not args.skip_promotion)


if __name__ == '__main__':
    main()
