import re


def tokenize_code(text: str) -> list:
    """Split identifiers so BM25 matches 'getUserName' / 'get_user_name' with 'user name'."""
    words = re.findall(r"[A-Za-z0-9]+", text)
    out = []
    for w in words:
        parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", w)
        out.extend(p.lower() for p in parts)
    return out
