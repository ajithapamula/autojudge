import httpx, re
from langchain_openai import ChatOpenAI
from app.utils.github_client import get_file_content, list_repo_files

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

PITCH_SYSTEM = (
    "You are a hackathon judge. Analyze the pitch text for clarity, "
    "problem/solution fit, storytelling, and technical depth. "
    "Return a numeric score (0-100) and 3-5 bullet feedback lines."
)
PITCH_USER_TMPL = """Pitch:
{content}

Please respond in this format:
Score: <number 0-100>
Feedback:
- ...
- ...
- ...
"""

async def _read_readme(repo_url: str) -> str:
    files = []
    try:
        files = await list_repo_files(repo_url)
    except Exception:
        pass
    for p in ("README.md", "Readme.md", "readme.md", "README", "README.rst"):
        if any(f.endswith(p) for f in files):
            txt = await get_file_content(repo_url, p)
            if txt:
                return txt
    return ""

async def score_pitch_quality(pitch_url_or_repo: str):
    """
    If input looks like a URL, fetch it.
    Otherwise, treat as repo and analyze README as the pitch.
    """
    content = ""
    if pitch_url_or_repo.lower().startswith(("http://", "https://")):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(pitch_url_or_repo)
                content = r.text[:6000]
        except Exception as e:
            return {"score": 0, "subscores": {}, "rationale": f"fetch failed: {e}", "evidence": [pitch_url_or_repo]}
    else:
        # assume repo identifier; use README as pitch
        content = await _read_readme(pitch_url_or_repo)
        if not content:
            return {"score": 0, "subscores": {}, "rationale": "No README found for pitch.", "evidence": []}

    try:
        messages = [
            {"role": "system", "content": PITCH_SYSTEM},
            {"role": "user", "content": PITCH_USER_TMPL.format(content=content)},
        ]
        res = await llm.ainvoke(messages)
        rationale = res.content.strip()
        m = re.search(r"Score:\s*(\d{1,3})", rationale, re.IGNORECASE)
        score = int(m.group(1)) if m else 75
        score = max(0, min(100, score))
        return {"score": score, "subscores": {}, "rationale": rationale, "evidence": []}
    except Exception as e:
        return {"score": 0, "subscores": {}, "rationale": f"LLM failed: {e}", "evidence": []}
