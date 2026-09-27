"""Publication checks use disposable repositories and synthetic contents."""
import contextlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.github' / 'scripts'))
import privacy
from sources import NAMES


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE).decode().strip()


def commit(root):
    git(root, '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'Add source fixture')
    return git(root, 'rev-parse', 'HEAD')


def fixture(root):
    git(root, 'init', '-q')
    for name in NAMES:
        child = root / name
        child.mkdir()
        git(child, 'init', '-q')
        (child / 'main.py').write_text('print("example")\n')
        git(child, 'add', 'main.py')
        commit(child)
    (root / '.gitmodules').write_text(''.join(
        f'[submodule "{name}"]\n\tpath = {name}\n\turl = https://github.com/Sage-Cat/{name}.git\n'
        for name in NAMES))
    (root / '.github').mkdir()
    (root / '.github' / 'release.json').write_text('{"name":"desktop-workspace"}\n')
    (root / 'README.md').write_text('Example workspace\n')
    git(root, 'add', '.gitmodules', '.github/release.json', 'README.md', *NAMES)
    return commit(root)


@contextlib.contextmanager
def cwd(root):
    previous = Path.cwd()
    os.chdir(root)
    try:
        yield
    finally:
        os.chdir(previous)


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sha = fixture(self.root)

    def scan(self, **kwargs):
        with cwd(self.root):
            return privacy.scan(**kwargs)

    def test_approved_pins_and_untracked_private_files(self):
        (self.root / 'workspace-state' / 'AGENTS.md').write_text('private instructions')
        self.assertEqual([], self.scan(history=True))
        self.assertEqual([], self.scan(index=True))

    def test_child_private_file_is_rejected(self):
        child = self.root / 'workspace-state'
        (child / 'AGENTS.md').write_text('private instructions')
        git(child, 'add', '-f', 'AGENTS.md')
        commit(child)
        git(self.root, 'add', 'workspace-state')
        commit(self.root)
        self.assertTrue(any(path == 'workspace-state/AGENTS.md' for _, path in self.scan()))

    def test_child_disguised_secret_and_attribution_are_rejected(self):
        child = self.root / 'login-hud'
        (child / 'example.txt').write_text('ghp_' + 'x' * 40 + '\n' + 'Generated ' + 'by ' + 'Open' + 'AI' + '\n')
        git(child, 'add', 'example.txt')
        commit(child)
        git(self.root, 'add', 'login-hud')
        commit(self.root)
        findings = self.scan()
        self.assertTrue(any(reason == 'credential/private-key signature' for reason, _ in findings))
        self.assertTrue(any(reason == 'AI attribution' for reason, _ in findings))

    def test_parent_staged_private_file_is_rejected(self):
        (self.root / 'AGENTS.md').write_text('private instructions')
        git(self.root, 'add', '-f', 'AGENTS.md')
        self.assertTrue(any(path == 'AGENTS.md' for _, path in self.scan(index=True)))

    def test_mismatched_checkout_is_rejected(self):
        child = self.root / 'login-hud'
        (child / 'main.py').write_text('print("different")\n')
        git(child, 'add', 'main.py')
        commit(child)
        with self.assertRaisesRegex(ValueError, 'differs from pinned'):
            self.scan()

    def test_uninitialized_checkout_is_rejected(self):
        (self.root / 'login-hud' / '.git').rename(self.root / 'hidden-git')
        with self.assertRaisesRegex(ValueError, 'uninitialized'):
            self.scan()

    def test_additional_pin_is_rejected(self):
        git(self.root, 'update-index', '--add', '--cacheinfo', '160000,' + self.sha + ',extra-tool')
        with self.assertRaisesRegex(ValueError, 'exactly the six'):
            self.scan(index=True)

    def test_changed_url_is_rejected(self):
        path = self.root / '.gitmodules'
        path.write_text(path.read_text().replace('Sage-Cat/', 'other-owner/'))
        git(self.root, 'add', '.gitmodules')
        with self.assertRaisesRegex(ValueError, 'unsupported submodule'):
            self.scan(index=True)


if __name__ == '__main__':
    unittest.main()
