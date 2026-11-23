"""Clone-free GitHub sync using the REST API.

* ETag   -> one cheap conditional request tells us whether the repo changed at all (304 = free).
* Tree   -> ONE request lists every file with its blob SHA (a hash of the file's content).
* SHA    -> compare against the SHAs we stored; only files whose SHA differs get re-parsed/re-embedded.
* Fetch  -> changed files come from blob requests (few changes) or a single in-memory tarball (many).
Nothing is written to disk except the index and a small state file.
"""
import base64
import io
import json
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import PurePosixPath

import httpx

from .ast_parser import parse_file
from .config import DATA_DIR, EXTENSIONS, GITHUB_TOKEN, SKIP_DIRS
from .index import Index

API = "https://api.github.com"
STATE = DATA_DIR / "api_state.json"
MAX_BLOB = 300_000          # skip huge generated files
TARBALL_THRESHOLD = 60      # above this many changed files, one tarball beats N blob requests


def _client() -> httpx.Client:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return httpx.Client(headers=headers, timeout=60, follow_redirects=True)


def _check(r: httpx.Response):
    if r.status_code in (403, 429) and r.headers.get("x-ratelimit-remaining") == "0":
        raise RuntimeError("GitHub rate limit reached (60/hour without GITHUB_TOKEN, 5000/hour with one).")
    if r.status_code == 404:
        raise RuntimeError("Repo not found, or it is private and GITHUB_TOKEN is missing or lacks access.")
    r.raise_for_status()


def _wanted(path: str, size: int = 0) -> bool:
    p = PurePosixPath(path)
    return p.suffix in EXTENSIONS and not (set(p.parts) & SKIP_DIRS) and size <= MAX_BLOB


def _fetch_blobs(c, repo, paths: dict) -> dict:
    def one(item):
        path, sha = item
        r = c.get(f"{API}/repos/{repo}/git/blobs/{sha}")
        _check(r)
        return path, base64.b64decode(r.json()["content"]).decode("utf-8", "ignore")
    with ThreadPoolExecutor(8) as ex:
        return dict(ex.map(one, paths.items()))


def _fetch_tarball(c, repo, commit_sha, wanted: set) -> dict:
    r = c.get(f"{API}/repos/{repo}/tarball/{commit_sha}")
    _check(r)
    out = {}
    with tarfile.open(fileobj=io.BytesIO(r.content), mode="r:gz") as tar:   # in memory, never on disk
        for m in tar:
            if not m.isfile():
                continue
            path = m.name.split("/", 1)[1] if "/" in m.name else m.name     # strip "owner-repo-sha/"
            if path in wanted:
                out[path] = tar.extractfile(m).read().decode("utf-8", "ignore")
    return out


def sync(repo: str, index: Index = None) -> dict:
    index = index or Index(repo)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    st = state.get(repo, {})

    with _client() as c:
        # 1. Has anything changed? A 304 answer is free and counts nothing against the rate limit.
        headers = {"If-None-Match": st["etag"]} if st.get("etag") else {}
        r = c.get(f"{API}/repos/{repo}/commits/HEAD", headers=headers)
        if r.status_code == 304:
            return {"repo": repo, "sha": st["commit"], "files": 0, "note": "up to date"}
        _check(r)
        commit = r.json()
        sha, tree_sha, etag = commit["sha"], commit["commit"]["tree"]["sha"], r.headers.get("etag")

        # 2. Whole file listing in one request, each file with its content hash.
        t = c.get(f"{API}/repos/{repo}/git/trees/{tree_sha}", params={"recursive": "1"})
        _check(t)
        tree = t.json()
        remote = {e["path"]: e["sha"] for e in tree["tree"]
                  if e["type"] == "blob" and _wanted(e["path"], e.get("size", 0))}

        # 3. Same SHA = same content = nothing to re-embed.
        old = st.get("blobs", {})
        changed = [p for p, s in remote.items() if old.get(p) != s]
        removed = [p for p in old if p not in remote]
        for p in removed:
            index.delete_file(p)

        # 4. Download only what changed.
        if len(changed) > TARBALL_THRESHOLD:
            contents = _fetch_tarball(c, repo, sha, set(changed))
        else:
            contents = _fetch_blobs(c, repo, {p: remote[p] for p in changed})
        for path, text in contents.items():
            index.delete_file(path)
            index.upsert(parse_file(repo, path, text))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state[repo] = {"etag": etag, "commit": sha, "blobs": remote}
    STATE.write_text(json.dumps(state))
    return {"repo": repo, "sha": sha, "files": len(contents), "removed": len(removed),
            "truncated": tree.get("truncated", False)}