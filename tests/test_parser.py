from rubberduck.ast_parser import parse_python
from rubberduck.text import tokenize_code

SRC = '''"""Billing helpers."""
import stripe

class Invoice:
    """An invoice."""
    def total(self, tax: float = 0.1) -> float:
        # apply tax last so discounts compound correctly
        return apply_tax(self.subtotal(), tax)

    def subtotal(self):
        return sum(i.price for i in self.items)

def apply_tax(amount, rate):
    """Add tax."""
    return amount * (1 + rate)
'''


def test_chunks():
    cs = {c.qualname: c for c in parse_python("o/r", "billing.py", SRC)}
    assert set(cs) == {"billing.py", "Invoice", "Invoice.total", "Invoice.subtotal", "apply_tax"}
    t = cs["Invoice.total"]
    assert t.kind == "method" and "apply_tax" in t.calls and "subtotal" in t.calls
    assert t.comments == ["apply tax last so discounts compound correctly"]
    assert t.signature == "def total(self, tax: float=0.1) -> float"


def test_graph_and_tokens():
    from rubberduck.graph import build_graph
    cs = parse_python("o/r", "billing.py", SRC)
    g = build_graph(cs)
    by = {c.qualname: c.id for c in cs}
    assert g.has_edge(by["Invoice.total"], by["apply_tax"])
    assert tokenize_code("getUserName HTTPServer snake_case") == ["get", "user", "name", "http", "server", "snake", "case"]
