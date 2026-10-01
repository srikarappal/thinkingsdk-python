"""The fields the ThinkingSDK server groups and routes exceptions on must survive capture.

The server hashes an exception from its type, message and innermost application frame
(file + func), and picks the repo or no repo autofix flow from repository_context. These
tests pin that contract:
  - repository_context survives even when a large event exhausts the encoding budget
  - sys.excepthook frames use the same schema as the full capture path
  - deep stacks keep the innermost frames (the raise site), not the outermost
  - branch and commit come from the checkout instead of a hardcoded "main"
"""
import json
import sys
from pathlib import Path

import pytest

from thinkingsdk.git_info import read_git_head
from thinkingsdk.instrumentation import RuntimeInstrumentation, is_in_app_path
from thinkingsdk.safety import MAX_TRACEBACK_FRAMES, encode_event, safe_traceback

COMMIT = 'a3f8c1d9e2b7f4a6c8d0e1f2a3b4c5d6e7f8a9b0'


class RecordingQueue:
    def __init__(self):
        self.events = []

    def push(self, event):
        self.events.append(event)


def raise_at_depth(depth):
    if depth == 0:
        return {}['missing_key']
    return raise_at_depth(depth - 1)


def captured_excepthook_event(depth, config=None):
    queue = RecordingQueue()
    instrumentation = RuntimeInstrumentation(queue, config or {})
    try:
        raise_at_depth(depth)
    except KeyError:
        instrumentation._capture_main_thread_exception(*sys.exc_info())
    finally:
        instrumentation.cleanup_hooks()
        sys.settrace(None)
    return queue.events[-1]


class TestRoutingKeysSurviveTruncation:
    def test_repository_context_survives_a_huge_event(self):
        event = {
            'event': 'exception',
            'breadcrumbs': [{'message': 'x', 'data': {'items': list(range(40))}} for _ in range(50)],
            'enhanced_context': {f'key_{index}': {'nested': list(range(30))} for index in range(40)},
            'repository_context': {'repo_full_name': 'acme/shop', 'branch': 'main'},
        }
        decoded = json.loads(encode_event(event))
        assert decoded['repository_context'] == {'repo_full_name': 'acme/shop', 'branch': 'main'}
        assert '<truncated>' in json.dumps(decoded)  # the bulky fields paid for it

    def test_routing_keys_are_encoded_first(self):
        decoded = json.loads(encode_event({'breadcrumbs': [], 'exception': {}, 'event': 'exception', 'ts': 1.0}))
        assert list(decoded)[:3] == ['event', 'ts', 'exception']


class TestExcepthookFrames:
    def test_frames_use_the_full_capture_schema(self):
        event = captured_excepthook_event(depth=2)
        frame = event['exception']['structured_traceback'][-1]
        assert set(frame) == {'file', 'file_path', 'line', 'func', 'code', 'in_app'}
        assert frame['func'] == 'raise_at_depth'
        assert frame['code'] == "return {}['missing_key']"
        assert frame['in_app'] is True

    def test_deep_stack_keeps_the_raise_site(self):
        event = captured_excepthook_event(depth=MAX_TRACEBACK_FRAMES + 20)
        frames = event['exception']['structured_traceback']
        assert len(frames) == MAX_TRACEBACK_FRAMES
        assert frames[-1]['code'] == "return {}['missing_key']"
        assert event['line'] == frames[-1]['line']

    def test_text_traceback_keeps_the_raise_site(self):
        try:
            raise_at_depth(MAX_TRACEBACK_FRAMES + 20)
        except KeyError:
            lines = safe_traceback(*sys.exc_info())
        assert len(lines) == MAX_TRACEBACK_FRAMES + 1
        assert 'raise_at_depth' in lines[-2] and lines[-1].startswith('KeyError')

    def test_repository_context_carries_branch_and_commit(self, tmp_path, monkeypatch):
        git_dir = tmp_path / '.git'
        (git_dir / 'refs' / 'heads').mkdir(parents=True)
        (git_dir / 'HEAD').write_text('ref: refs/heads/release\n')
        (git_dir / 'refs' / 'heads' / 'release').write_text(COMMIT + '\n')
        monkeypatch.chdir(tmp_path)

        event = captured_excepthook_event(depth=1, config={'git_repositories': ['https://github.com/acme/shop']})
        context = event['repository_context']
        assert (context['repo_full_name'], context['branch'], context['commit_hash']) == ('acme/shop', 'release', COMMIT)


class TestInAppPath:
    @pytest.mark.parametrize('file_path, expected', [
        ('/srv/app/orders.py', True),
        ('/srv/app/.venv/lib/python3.12/site-packages/requests/api.py', False),
        ('/usr/lib/python3.12/json/decoder.py', False),
        ('<frozen importlib._bootstrap>', False),
    ])
    def test_classification(self, file_path, expected):
        assert is_in_app_path(file_path) is expected


class TestReadGitHead:
    def make_repo(self, root: Path, head: str) -> Path:
        git_dir = root / '.git'
        (git_dir / 'refs' / 'heads').mkdir(parents=True)
        (git_dir / 'HEAD').write_text(head + '\n')
        return git_dir

    def test_branch_with_loose_ref_from_a_subdirectory(self, tmp_path):
        git_dir = self.make_repo(tmp_path, 'ref: refs/heads/feature/login')
        (git_dir / 'refs' / 'heads' / 'feature').mkdir()
        (git_dir / 'refs' / 'heads' / 'feature' / 'login').write_text(COMMIT)
        (tmp_path / 'src').mkdir()
        assert read_git_head(str(tmp_path / 'src')) == ('feature/login', COMMIT)

    def test_branch_with_packed_ref(self, tmp_path):
        git_dir = self.make_repo(tmp_path, 'ref: refs/heads/master')
        (git_dir / 'packed-refs').write_text(f'# pack-refs with: peeled\n{COMMIT} refs/heads/master\n')
        assert read_git_head(str(tmp_path)) == ('master', COMMIT)

    def test_detached_head(self, tmp_path):
        self.make_repo(tmp_path, COMMIT)
        assert read_git_head(str(tmp_path)) == (None, COMMIT)

    def test_worktree_pointer_file(self, tmp_path):
        main_git_dir = self.make_repo(tmp_path / 'main', 'ref: refs/heads/master')
        (main_git_dir / 'refs' / 'heads' / 'hotfix').write_text(COMMIT)
        worktree_git_dir = main_git_dir / 'worktrees' / 'hotfix'
        worktree_git_dir.mkdir(parents=True)
        (worktree_git_dir / 'HEAD').write_text('ref: refs/heads/hotfix\n')
        (worktree_git_dir / 'commondir').write_text('../..\n')
        worktree = tmp_path / 'hotfix'
        worktree.mkdir()
        (worktree / '.git').write_text(f'gitdir: {worktree_git_dir}\n')
        assert read_git_head(str(worktree)) == ('hotfix', COMMIT)

    def test_outside_a_checkout(self, tmp_path):
        assert read_git_head(str(tmp_path)) == (None, None)
