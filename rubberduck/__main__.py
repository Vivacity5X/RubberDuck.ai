import argparse

from . import generate
from .index import Index
from .retrieve import retrieve
from .sync_api import sync

p = argparse.ArgumentParser(prog="rubberduck")
p.add_argument("cmd", choices=["index", "ask", "suggest", "document"])
p.add_argument("repo", help="owner/name")
p.add_argument("query", nargs="?", default="")
a = p.parse_args()

if a.cmd == "index":
    print(sync(a.repo))
else:
    chunks = retrieve(Index(a.repo), a.query)
    print(generate.run(a.cmd, a.query, chunks))
    print("\nSources:", *[c.cite() for c in chunks], sep="\n  ")
