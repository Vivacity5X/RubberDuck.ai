import hashlib
import hmac
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import generate
from .config import WEBHOOK_SECRET
from .index import Index
from .retrieve import retrieve
from .sync_api import sync

app = FastAPI(title="RubberDuck.ai")
STATIC = Path(__file__).parent / "static"
_indexes: dict = {}          # one cached Index per repo, so requests don't reload it every time


def get_index(repo: str) -> Index:
    if repo not in _indexes:
        _indexes[repo] = Index(repo)
    return _indexes[repo]


class Query(BaseModel):
    repo: str            # "owner/name"
    query: str
    code: str = ""
    k: int = 8


@app.get("/")
def ui():
    return FileResponse(STATIC / "index.html")


@app.post("/index")
def index_repo(repo: str):
    return sync(repo, get_index(repo))


def _answer(mode: str, q: Query):
    index = get_index(q.repo)
    chunks = retrieve(index, q.query + ("\n" + q.code if q.code else ""), k=q.k)
    if not chunks:
        raise HTTPException(404, f"Nothing indexed for {q.repo}. Click 'Index repo' first.")
    return {"answer": generate.run(mode, q.query, chunks, q.code), "sources": [c.cite() for c in chunks]}


@app.post("/ask")
def ask(q: Query): return _answer("ask", q)


@app.post("/suggest")
def suggest(q: Query): return _answer("suggest", q)


@app.post("/document")
def document(q: Query): return _answer("document", q)


def _resync(repo: str):
    sync(repo, get_index(repo))


@app.post("/webhook/github")
async def webhook(request: Request, tasks: BackgroundTasks,
                  x_hub_signature_256: str = Header(default=""), x_github_event: str = Header(default="")):
    body = await request.body()
    if WEBHOOK_SECRET:
        sig = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, x_hub_signature_256):
            raise HTTPException(401, "bad signature")
    if x_github_event == "push":
        tasks.add_task(_resync, (await request.json())["repository"]["full_name"])
    return {"ok": True}