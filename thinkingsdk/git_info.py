"""Read the branch and commit of the running checkout straight from .git (no git binary)."""

from pathlib import Path
from typing import Optional, Tuple


def find_git_dir(start_dir: Path) -> Optional[Path]:
    """The .git directory of the checkout containing start_dir; follows worktree/submodule pointer files."""
    for directory in (start_dir, *start_dir.parents):
        git_path = directory / '.git'
        if git_path.is_dir():
            return git_path
        if git_path.is_file():
            pointer = git_path.read_text().strip()
            if pointer.startswith('gitdir:'):
                return (directory / pointer[len('gitdir:'):].strip()).resolve()
    return None


def resolve_ref(git_dir: Path, ref: str) -> Optional[str]:
    """Commit sha of a ref, from its loose ref file or packed-refs (worktrees share the common dir)."""
    common_dir = git_dir
    commondir_file = git_dir / 'commondir'
    if commondir_file.is_file():
        common_dir = (git_dir / commondir_file.read_text().strip()).resolve()

    for base_dir in (git_dir, common_dir):
        ref_file = base_dir / ref
        if ref_file.is_file():
            return ref_file.read_text().strip() or None

    packed_refs = common_dir / 'packed-refs'
    if packed_refs.is_file():
        for line in packed_refs.read_text().splitlines():
            parts = line.split(' ', 1)
            if len(parts) == 2 and parts[1] == ref:
                return parts[0]
    return None


def read_git_head(start_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """(branch, commit) of the checkout containing start_dir; branch is None on a detached HEAD.

    Returns (None, None) outside a git checkout, e.g. in most container deployments.
    """
    try:
        git_dir = find_git_dir(Path(start_dir).resolve())
        if git_dir is None:
            return None, None
        head = (git_dir / 'HEAD').read_text().strip()
        if not head.startswith('ref: '):
            return None, head or None
        ref = head[len('ref: '):]
        return ref.split('refs/heads/', 1)[-1], resolve_ref(git_dir, ref)
    except OSError:
        return None, None
