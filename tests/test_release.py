"""Offline regressions: no GitHub calls or user repository mutations."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.github' / 'scripts'))
from test_privacy import fixture, cwd, git, NAMES
spec = importlib.util.spec_from_file_location('publisher', Path(__file__).resolve().parents[1] / '.github' / 'scripts' / 'release.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)
SHA = 'a' * 40


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.files = {'source.tar.gz': b'committed source', 'SHA256SUMS': b'checksums'}
        for name, data in self.files.items():
            (self.root / name).write_bytes(data)
        self.target = None
        self.release = None
        self.writes = []
        self.canonical_sha = SHA
        self.default_branch = 'main'
        self.latest = None

    def api(self, endpoint, method='GET', payload=None, missing=False):
        if method != 'GET':
            self.writes.append((endpoint, method, payload))
        if endpoint == 'repos/example/tool':
            return {'default_branch': self.default_branch}
        if '/git/ref/heads/' in endpoint:
            self.assertTrue(endpoint.endswith('/' + self.default_branch))
            return {'object': {'type': 'commit', 'sha': self.canonical_sha}}
        if endpoint.endswith('/releases/latest'):
            return copy.deepcopy(self.latest)
        if '/git/ref/tags/' in endpoint:
            return {'object': {'type': 'commit', 'sha': self.target}} if self.target else None
        if endpoint.endswith('/git/refs'):
            self.target = payload['sha']
            return {}
        if method == 'POST':
            self.release = dict(payload, id=7, assets=[], html_url='https://example.invalid/release', immutable=False)
        if method == 'PATCH':
            self.release.update(payload)
            if payload.get('make_latest') == 'true':
                self.latest = copy.deepcopy(self.release)
        return copy.deepcopy(self.release)

    def command(self, *args, **kwargs):
        self.assertEqual(args[:3], ('gh', 'release', 'upload'))
        self.assertNotIn('--clobber', args)
        path = Path(args[4])
        self.writes.append(('upload', path.name))
        self.release['assets'].append({'name': path.name, 'id': len(self.release['assets']),
                                      'state': 'uploaded', 'digest': 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()})
        return b''

    def publish(self, **kwargs):
        with patch.object(publisher, 'api', side_effect=self.api), patch.object(publisher, 'command', side_effect=self.command), contextlib.redirect_stdout(io.StringIO()):
            return publisher.publish('example/tool', SHA, self.root, **kwargs)

    def test_rerun_is_read_only_and_reports_server_immutability_honestly(self):
        result = self.publish()
        self.assertFalse(result['github_immutable'])
        self.assertFalse(self.release['draft'])
        self.assertEqual(self.target, SHA)
        self.writes.clear()
        self.assertEqual(self.publish(), result)
        self.assertEqual(self.writes, [])

    def test_current_default_branch_commit_becomes_latest(self):
        self.default_branch = 'master'
        self.publish()
        self.assertEqual(self.latest['tag_name'], f'build-{SHA}')

    def test_out_of_order_old_commit_does_not_replace_newer_latest(self):
        self.canonical_sha = 'b' * 40
        self.latest = {'id': 99, 'tag_name': 'build-' + self.canonical_sha}
        self.publish()
        self.assertEqual(self.latest['id'], 99)
        self.assertFalse(any(len(write) == 3 and write[2].get('make_latest') == 'true' for write in self.writes))
        self.writes.clear()
        self.publish()
        self.assertEqual(self.writes, [])

    def test_head_is_rechecked_after_slow_artifact_uploads(self):
        normal_command = self.command
        def advance_head(*args, **kwargs):
            result = normal_command(*args, **kwargs)
            self.canonical_sha = 'b' * 40
            return result
        with patch.object(publisher, 'api', side_effect=self.api), patch.object(publisher, 'command', side_effect=advance_head), contextlib.redirect_stdout(io.StringIO()):
            publisher.publish('example/tool', SHA, self.root)
        self.assertIsNone(self.latest)

    def test_existing_current_commit_release_can_promote_without_replacing_assets(self):
        self.canonical_sha = 'b' * 40
        self.publish()
        self.canonical_sha = SHA
        self.writes.clear()
        self.publish()
        self.assertEqual(self.latest['tag_name'], f'build-{SHA}')
        self.assertEqual(self.writes, [('repos/example/tool/releases/7', 'PATCH', {'make_latest': 'true'})])

    def test_parallel_publication_can_defer_latest_to_serialized_job(self):
        self.publish(update_latest=False)
        self.assertIsNone(self.latest)
        self.assertFalse(self.release['draft'])
        self.writes.clear()
        with patch.object(publisher, 'api', side_effect=self.api), contextlib.redirect_stdout(io.StringIO()):
            result = publisher.promote_latest('example/tool')
        self.assertEqual(result['status'], 'latest')
        self.assertEqual(self.latest['tag_name'], f'build-{SHA}')
        self.assertEqual(self.writes, [('repos/example/tool/releases/7', 'PATCH', {'make_latest': 'true'})])

    def test_old_trigger_promotes_new_published_head_after_pending_jobs_coalesce(self):
        self.canonical_sha = 'b' * 40
        self.target = self.canonical_sha
        self.release = {'id': 99, 'tag_name': 'build-' + self.canonical_sha,
                        'draft': False, 'html_url': 'https://example.invalid/new-release', 'assets': []}
        with patch.object(publisher, 'api', side_effect=self.api), patch.dict('os.environ', {'GITHUB_SHA': SHA}), contextlib.redirect_stdout(io.StringIO()):
            result = publisher.promote_latest('example/tool')
        self.assertEqual(result['commit'], self.canonical_sha)
        self.assertEqual(self.latest['id'], 99)

    def test_promotion_waits_for_head_release_instead_of_promoting_old_release(self):
        self.latest = {'id': 1, 'tag_name': 'v1'}
        with patch.object(publisher, 'api', side_effect=self.api), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(publisher.promote_latest('example/tool')['status'], 'awaiting_published_release')
        self.assertEqual(self.latest['id'], 1)
        self.assertEqual(self.writes, [])

    def test_promotion_refuses_changed_release_tag(self):
        self.publish(update_latest=False)
        self.target = 'c' * 40
        self.writes.clear()
        with patch.object(publisher, 'api', side_effect=self.api):
            with self.assertRaisesRegex(ValueError, 'another commit'):
                publisher.promote_latest('example/tool')
        self.assertEqual(self.writes, [])

    def test_wrong_tag_fails_before_any_write(self):
        self.target = 'b' * 40
        with self.assertRaisesRegex(ValueError, 'another commit'):
            self.publish()
        self.assertEqual(self.writes, [])

    def test_changed_asset_fails_without_replacement(self):
        self.publish()
        self.writes.clear()
        (self.root / 'source.tar.gz').write_bytes(b'different')
        with self.assertRaisesRegex(ValueError, 'refusing replacement'):
            self.publish()
        self.assertEqual(self.writes, [])

    def test_partial_draft_recovers_only_missing_assets(self):
        self.publish()
        self.release['draft'] = True
        self.release['assets'] = self.release['assets'][:1]
        self.writes.clear()
        self.publish()
        self.assertEqual(sum(item[0] == 'upload' for item in self.writes), 1)
        self.assertFalse(self.release['draft'])

    def test_published_release_missing_asset_is_never_modified(self):
        self.publish()
        self.release['assets'] = self.release['assets'][:1]
        self.writes.clear()
        with self.assertRaisesRegex(ValueError, 'refusing to modify'):
            self.publish()
        self.assertEqual(self.writes, [])

    def test_unexpected_asset_is_not_removed_or_ignored(self):
        self.publish()
        self.release['assets'].append({'name': 'unexpected.zip'})
        self.writes.clear()
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            self.publish()
        self.assertEqual(self.writes, [])

    def test_changed_tag_before_publication_leaves_draft_unpublished(self):
        normal_command = self.command
        def change_target(*args, **kwargs):
            result = normal_command(*args, **kwargs)
            self.target = 'b' * 40
            return result
        with patch.object(publisher, 'api', side_effect=self.api), patch.object(publisher, 'command', side_effect=change_target):
            with self.assertRaisesRegex(ValueError, 'changed during preparation'):
                publisher.publish('example/tool', SHA, self.root)
        self.assertTrue(self.release['draft'])
        self.assertFalse(any(len(item) > 1 and item[1] == 'PATCH' for item in self.writes))

    def test_semantic_release_requires_existing_tag(self):
        with self.assertRaisesRegex(ValueError, 'existing tag'):
            self.publish(tag='v42')
        self.assertEqual(self.writes, [])
        self.target = SHA
        self.assertEqual(self.publish(tag='v42')['tag'], 'v42')

    def test_annotated_tag_resolves_to_commit(self):
        with patch.object(publisher, 'api', side_effect=[{'object': {'type': 'tag', 'sha': 'c' * 40}}, {'object': {'type': 'commit', 'sha': SHA}}]):
            self.assertEqual(publisher.tag_commit('example/tool', 'v42'), SHA)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'source'
        self.root.mkdir()
        self.sha = fixture(self.root)

    def test_reproducible_complete_offline_source_bundle(self):
        (self.root / 'workspace-state' / 'main.py').write_text('local edits')
        (self.root / 'workspace-state' / 'AGENTS.md').write_text('private instructions')
        (self.root / 'private-tool').mkdir()
        (self.root / 'private-tool' / 'secret.txt').write_text('private file')
        outputs = [self.root.parent / 'first', self.root.parent / 'second']
        with cwd(self.root):
            for output in outputs:
                publisher.prepare(self.sha, output)
        self.assertEqual({p.name: p.read_bytes() for p in outputs[0].iterdir()},
                         {p.name: p.read_bytes() for p in outputs[1].iterdir()})
        archive = next(outputs[0].glob('*.tar.gz'))
        prefix = f'desktop-workspace-{self.sha}/'
        with tarfile.open(archive) as source:
            self.assertTrue(all(member.mtime >= 315619200 for member in source))
            for name in NAMES:
                self.assertEqual(b'print("example")\n', source.extractfile(prefix + name + '/main.py').read())
            self.assertFalse(any('/.git/' in name or 'AGENTS.md' in name or 'secret.txt' in name
                                 for name in source.getnames()))
            lock = json.load(source.extractfile(prefix + 'sources.lock.json'))
            self.assertEqual(self.sha, lock['parent_commit'])
            self.assertEqual({name: git(self.root / name, 'rev-parse', 'HEAD') for name in NAMES}, lock['repositories'])
            self.assertEqual(lock, json.loads((outputs[0] / 'sources.lock.json').read_text()))

    def test_wrong_parent_commit_is_refused(self):
        with cwd(self.root), self.assertRaisesRegex(ValueError, 'checked-out HEAD'):
            publisher.prepare('f' * 40, self.root.parent / 'output')

    def test_changed_child_head_is_refused(self):
        child = self.root / 'login-hud'
        git(child, '-c', 'core.hooksPath=/dev/null', 'commit', '--allow-empty', '-qm', 'Another source fixture')
        with cwd(self.root), self.assertRaisesRegex(ValueError, 'differs from pinned'):
            publisher.prepare(self.sha, self.root.parent / 'output')


if __name__ == '__main__':
    unittest.main()
