from collections import defaultdict

import networkx as nx


def build_graph(chunks) -> nx.DiGraph:
    """Edges: caller -> callee, resolved by name (same-file matches win)."""
    chunks = list(chunks)
    g, by_name = nx.DiGraph(), defaultdict(list)
    for c in chunks:
        g.add_node(c.id)
        if c.kind != "module":
            by_name[c.name].append(c)
    for c in chunks:
        for callee in c.calls:
            targets = by_name.get(callee, [])
            same_file = [t for t in targets if t.path == c.path]
            for t in (same_file or targets)[:3]:
                if t.id != c.id:
                    g.add_edge(c.id, t.id)
    return g
