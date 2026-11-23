"""AST-based chunking. Python uses the stdlib `ast`; add other languages (e.g. tree-sitter)
by registering a function with the same signature in PARSERS."""
import ast
import hashlib
import io
import tokenize

from .models import Chunk


def _comments_by_line(source: str) -> dict:
    out = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                out[tok.start[0]] = tok.string.lstrip("# ").strip()
    except (tokenize.TokenError, IndentationError):
        pass
    return out


def _call_names(node) -> list:
    names = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            if name and name not in names:
                names.append(name)
    return names


def _signature(node) -> str:
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(ast.unparse(b) for b in node.bases)
        return f"class {node.name}({bases})" if bases else f"class {node.name}"
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{prefix} {node.name}({ast.unparse(node.args)}){ret}"


def _make_id(repo, path, qualname, start) -> str:
    return hashlib.sha1(f"{repo}:{path}:{qualname}:{start}".encode()).hexdigest()[:16]


def parse_python(repo: str, path: str, source: str) -> list:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    comments = _comments_by_line(source)
    imports = []
    for n in tree.body:
        if isinstance(n, ast.Import):
            imports += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            imports.append(n.module or "")

    def comments_in(start, end):
        return [t for ln, t in sorted(comments.items()) if start <= ln <= end]

    chunks = [Chunk(
        id=_make_id(repo, path, "<module>", 1), repo=repo, path=path, kind="module",
        name=path.rsplit("/", 1)[-1].removesuffix(".py"), qualname=path,
        signature=f"module {path}", docstring=ast.get_docstring(tree) or "",
        comments=comments_in(1, 5), code="\n".join(f"import {i}" for i in imports[:30]),
        start=1, end=len(lines), imports=imports)]

    def visit(body, parents):
        for node in body:
            if isinstance(node, ast.ClassDef):
                qual = ".".join(parents + [node.name])
                methods = [m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
                chunks.append(Chunk(
                    id=_make_id(repo, path, qual, node.lineno), repo=repo, path=path, kind="class",
                    name=node.name, qualname=qual, signature=_signature(node),
                    docstring=ast.get_docstring(node) or "",
                    comments=comments_in(node.lineno, node.lineno + 3),
                    code=f"{_signature(node)}:\n    # methods: {', '.join(methods)}",
                    start=node.lineno, end=node.end_lineno, imports=imports))
                visit(node.body, parents + [node.name])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = ".".join(parents + [node.name])
                chunks.append(Chunk(
                    id=_make_id(repo, path, qual, node.lineno), repo=repo, path=path,
                    kind="method" if parents else "function", name=node.name, qualname=qual,
                    signature=_signature(node), docstring=ast.get_docstring(node) or "",
                    comments=comments_in(node.lineno, node.end_lineno),
                    code="\n".join(lines[node.lineno - 1:node.end_lineno]),
                    start=node.lineno, end=node.end_lineno,
                    calls=_call_names(node), imports=imports))

    visit(tree.body, [])
    return chunks


PARSERS = {".py": parse_python}


def parse_file(repo: str, path: str, source: str) -> list:
    ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
    parser = PARSERS.get(ext)
    return parser(repo, path, source) if parser else []
