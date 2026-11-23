"""Measures how often the right file appears in the top results.
Run from the project root after indexing pallets/click:  python eval_retrieval.py
Add your own questions to CASES (the set holds every file that would be a correct answer)."""
from rubberduck.index import Index
from rubberduck.retrieve import retrieve

REPO = "pallets/click"
K = 8

CASES = [
    ("How are command line options parsed?", {"src/click/parser.py"}),
    ("Where is the progress bar implemented?", {"src/click/termui.py", "src/click/_termui_impl.py"}),
    ("How does shell completion work?", {"src/click/shell_completion.py"}),
    ("How is help text formatted?", {"src/click/formatting.py"}),
    ("How does the CliRunner test commands?", {"src/click/testing.py"}),
    ("How do I prompt the user for input?", {"src/click/termui.py"}),
    ("Where are usage errors defined?", {"src/click/exceptions.py"}),
    ("How does the Choice type validate values?", {"src/click/types.py"}),
    ("How is the group decorator implemented?", {"src/click/decorators.py"}),
    ("How does echo print output?", {"src/click/utils.py"}),
    ("How are Context objects created and used?", {"src/click/core.py"}),
    ("How are file arguments and lazy files handled?", {"src/click/types.py", "src/click/utils.py"}),
]


def norm(path: str) -> str:
    return path.replace("\\", "/")


def main():
    index = Index(REPO)
    index._refresh()
    modes = {
        "vector search only": lambda q: [index.chunks[i].path for i in index.vector_search(q, K)],
        "keyword search only (BM25)": lambda q: [index.chunks[i].path for i in index.bm25_search(q, K)],
        "hybrid (vector + BM25)": lambda q: [c.path for c in retrieve(index, q, k=K, expand=False)],
        "hybrid + call graph": lambda q: [c.path for c in retrieve(index, q, k=K, expand=True)],
    }
    print(f"{len(index.chunks)} chunks indexed, {len(CASES)} test questions, top {K} results\n")
    for name, fn in modes.items():
        hits = sum(bool({norm(p) for p in fn(q)} & ok) for q, ok in CASES)
        print(f"{name:28s} {hits}/{len(CASES)}  ({100 * hits / len(CASES):.0f}%)")
    # The call graph adds up to K//2 extra results, so its row may include a few more results than the others.


if __name__ == "__main__":
    main()