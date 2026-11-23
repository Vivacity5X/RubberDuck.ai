import json
import subprocess
from pathlib import Path

from .ast_parser import parse_file
from .config import DATA_DIR, EXTENSIONS, GITHUB_TOKEN, REPOS_DIR, SKIP_DIRS
from .index import Index

STATE = DATA_DIR / "state.json"


def _git(cwd, *args) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _url(repo: str) -> str:
    auth = f"{GITHUB_TOKEN}@" if GITHUB_TOKEN else ""
    return f"https://{auth}github.com/{repo}.git"


def _wanted(rel: str) -> bool:
    p = Path(rel)
    return p.suffix in EXTENSIONS and not (set(p.parts) & SKIP_DIRS)


def sync(repo: str, index: Index = None) -> dict:
    """Clone or pull `owner/name`; index everything the first time, only the diff afterwards."""
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPOS_DIR / repo.replace("/", "__")
    if path.exists():
        _git(path, "fetch", "--depth", "50", "origin")
        _git(path, "reset", "--hard", "origin/HEAD")
    else:
        subprocess.run(["git", "clone", "--depth", "50", _url(repo), str(path)], check=True)
    new_sha = _git(path, "rev-parse", "HEAD")
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    old_sha = state.get(repo)
    index = index or Index(repo)

    if old_sha and old_sha != new_sha:
        out = _git(path, "diff", "--name-only", old_sha, new_sha)   # may fail if history was rewritten
        changed = [f for f in out.splitlines() if _wanted(f)]
    elif old_sha == new_sha:
        return {"repo": repo, "sha": new_sha, "files": 0, "note": "up to date"}
    else:
        changed = [str(p.relative_to(path)) for p in path.rglob("*") if p.is_file() and _wanted(str(p.relative_to(path)))]

    for rel in changed:
        index.delete_file(rel)                       # drop stale chunks (also handles deleted files)
        f = path / rel
        if f.exists():
            index.upsert(parse_file(repo, rel, f.read_text(errors="ignore")))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state[repo] = new_sha
    STATE.write_text(json.dumps(state))
    return {"repo": repo, "sha": new_sha, "files": len(changed)}
