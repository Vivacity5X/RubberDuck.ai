from collections import defaultdict

def retrieve(index, query: str, k: int = 8, expand: bool = True) -> list:
    index._refresh()
    q = query.strip().lower()
    exact = [c.id for c in index.chunks.values() if c.qualname.lower() == q]

    scores = defaultdict(float)
    for ranked in (index.vector_search(query, 20), index.bm25_search(query, 20)):
        for rank, cid in enumerate(ranked):
            scores[cid] += 1.0 / (60 + rank)
    fused = [cid for cid, _ in sorted(scores.items(), key=lambda x: -x[1])]
    top = (exact + [c for c in fused if c not in exact])[:k]

    if expand and index.graph is not None:
        extra = []
        for cid in top[:3]:
            for nb in list(index.graph.successors(cid)) + list(index.graph.predecessors(cid)):
                if nb not in top and nb not in extra:
                    extra.append(nb)
        top += extra[: max(2, k // 2)]
    return [index.chunks[c] for c in top if c in index.chunks]