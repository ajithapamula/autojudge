# app/agents/critique_agent.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
import os
import json

try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None  # type: ignore

# optional LLM
_llm: Optional[Any] = None
if ChatOpenAI and os.getenv("OPENAI_API_KEY"):
    try:
        _llm = ChatOpenAI(model=os.getenv("CRITIQUE_MODEL", "gpt-4o-mini"), temperature=0)
    except Exception:
        _llm = None


def _safe(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def _heuristic_critique(role: str, reports: Dict[str, Any]) -> str:
    """Fallback critique if no LLM: highlight obvious gaps from subscores."""
    others = [r for k, r in reports.items() if k != role and isinstance(r, dict)]
    points: List[str] = []
    for r in others:
        subs = r.get("subscores") or {}
        if (subs.get("testing") or 0) <= 0:
            points.append("Lack of tests reduces confidence in stability.")
        if (subs.get("ci_cd") or 0) <= 0:
            points.append("Missing CI; regressions may slip in.")
        if (subs.get("documentation") or 0) < 15:
            points.append("Docs/README look thin; onboarding may be hard.")
        if (subs.get("accessibility") or 0) <= 0:
            points.append("Accessibility not addressed.")
    if not points:
        points = ["No major blockers spotted. Consider adding concrete metrics and examples."]
    return f"[{role} critique] " + " ".join(points[:3])


async def make_critiques(reports: Dict[str, Any], thread: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    critiques: List[Dict[str, Any]] = []
    roles = ["code", "design", "pitch"]

    if not _llm:
        # Heuristic, no network call
        for role in roles:
            critiques.append({"role": role, "type": "critique", "content": _heuristic_critique(role, reports)})
        return critiques

    # LLM-based brief critique for each role
    for role in roles:
        others = {k: v for k, v in reports.items() if k != role}
        prompt = (
            "You are the {role} reviewer in a small agent team.\n"
            "Read the other agents' reports and write <=120 words critique focusing on issues that affect {role}-quality.\n"
            "Return STRICT JSON: {\"critique\": \"...\", \"question\": \"...\"}\n\n"
            f"Other reports JSON:\n{_safe(others)}\n"
        ).format(role=role)
        try:
            resp = await _llm.ainvoke(prompt)
            text = (resp.content or "").strip()
            if "```" in text:
                s, e = text.find("```"), text.rfind("```")
                if s != -1 and e != -1 and e > s:
                    text = text[s + 3:e]
                    if text.startswith("json"):
                        text = text[4:].strip()
            data = json.loads(text)
            msg = data.get("critique") or _heuristic_critique(role, reports)
        except Exception:
            msg = _heuristic_critique(role, reports)
        critiques.append({"role": role, "type": "critique", "content": msg})
    return critiques
