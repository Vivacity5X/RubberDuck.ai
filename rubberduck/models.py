from dataclasses import dataclass, field


@dataclass
class Chunk:
    """One semantic unit of code (function / method / class / module), enriched with NL context."""
    id: str
    repo: str
    path: str
    kind: str                 # module | class | function | method
    name: str
    qualname: str
    signature: str
    docstring: str
    comments: list = field(default_factory=list)
    code: str = ""
    start: int = 0
    end: int = 0
    calls: list = field(default_factory=list)     # names this chunk calls (graph edges)
    imports: list = field(default_factory=list)

    def embed_text(self) -> str:
        """Natural-language-first text: what it is + what it says + the code itself."""
        parts = [f"{self.kind} {self.qualname} in {self.path}", self.signature]
        if self.docstring:
            parts.append(self.docstring)
        if self.comments:
            parts.append("Comments: " + " ".join(self.comments))
        if self.calls:
            parts.append("Calls: " + ", ".join(self.calls[:15]))
        parts.append(self.code)
        return "\n".join(parts)

    def cite(self) -> str:
        return f"{self.path}:{self.start}-{self.end}"
