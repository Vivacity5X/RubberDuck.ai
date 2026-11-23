import os
from pathlib import Path

DATA_DIR = Path(os.getenv("RUBBERDUCK_DATA", ".rubberduck"))
REPOS_DIR = DATA_DIR / "repos"
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
LLM_MODEL = os.getenv("LLM_MODEL", "grok-4.3")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")            # needed for private repos
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build", ".tox"}
EXTENSIONS = {".py"}   # add languages by registering a parser in ast_parser.PARSERS
