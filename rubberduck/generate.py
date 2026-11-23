from openai import OpenAI

from .config import LLM_MODEL, XAI_API_KEY

SYSTEM = ("You are RubberDuck.ai, a senior engineer who knows this codebase. Ground every answer in the "
          "provided context and cite files as [path:start-end]. Only state behavior you can see in the "
          "code shown; never infer behavior from test names. If the requested target is not in the "
          "context, say so. For suggestions, check that every name you use is already imported in the "
          "file you edit, and add the import if it isn't.")

TASKS = {
    "ask": "Answer the question about the codebase.",
    "suggest": "Propose a code change for the request. Match the repo's style, reuse existing helpers "
               "from the context, and show a minimal diff or snippet plus a short rationale.",
    "document": "Write documentation for the target: purpose, parameters, returns, side effects, "
                "a usage example derived from real call sites in the context, and Python docstring text.",
}


def build_context(chunks) -> str:
    return "\n\n".join(f"### {c.cite()}  ({c.kind} {c.qualname})\n```python\n{c.code}\n```"
                       + (f"\nDocstring: {c.docstring}" if c.docstring else "") for c in chunks)


def run(mode: str, query: str, chunks, code: str = "") -> str:
    client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.groq.com/openai/v1")
    user = (f"Task: {TASKS[mode]}\n\n<context>\n{build_context(chunks)}\n</context>\n\n"
            + (f"<current_code>\n{code}\n</current_code>\n\n" if code else "") + f"Request: {query}")
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}])
    except Exception as e:
        body = getattr(getattr(e, "response", None), "text", "")
        raise SystemExit(f"xAI API error: {e}\n{body}\n(model={LLM_MODEL}, key set={bool(XAI_API_KEY)})")
    return resp.choices[0].message.content