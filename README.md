# RubberDuck.ai 🦆
Code-aware RAG: AST-based chunking + NL enrichment + hybrid retrieval + call-graph expansion + live GitHub sync.

## Run
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=...   # GITHUB_TOKEN for private repos
    python -m rubberduck index owner/repo
    python -m rubberduck ask owner/repo "Where is tax applied to invoices?"
    python -m rubberduck suggest owner/repo "add retry with backoff to the payment client"
    python -m rubberduck document owner/repo "Invoice.total"
    uvicorn rubberduck.server:app --port 8000      # REST API + /webhook/github

## Pipeline
1. models.py      Chunk = code + signature + docstring + comments + calls + imports
2. ast_parser.py  AST -> function/class/module chunks (add languages via PARSERS)
3. graph.py       caller->callee symbol graph
4. index.py       Chroma vectors + BM25 (identifier-splitting tokenizer)
5. retrieve.py    RRF fusion of vector+BM25, then 1-hop graph expansion
6. generate.py    ask / suggest / document prompts with file:line citations
7. sync.py        git clone/pull; re-index only files changed in the diff
8. server.py      FastAPI + HMAC-verified GitHub push webhook
