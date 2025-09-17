# app/agents/revise_agent.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
import os
import json

try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None  # type: ignore

_llm: Optional[Any] = None
if ChatOpenAI and os.getenv("OPENAI_API_KEY"):
    try:
        _llm = ChatOpenAI(model=os.getenv("REVISE_MODEL", "gpt-4o-mini"), temperature=0)
    except Exception:
        _llm = None


def _safe(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def _collect_critiques(thread: List[Dict[str, Any]]) -> str:
    return "\n".join(
        f"- {m.get('role')}: {m.get('content','')}"
        for m in (thread or [])
        if m.get("type") == "critique"
    )


async def apply_revisions(reports: Dict[str, Any], thread: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """
    Return optional rationale updates per role, e.g.:
    { "code": {"rationale": "...", "notes": "what changed"}, ... }
    """
    out: Dict[str, Dict[str, str]] = {}
    crit = _collect_critiques(thread)

    if not _llm:
        # Heuristic: if there are critiques, append a short “addressed” note.
        for role, rep in reports.items():
            if not isinstance(rep, dict):
                continue
            base = (rep.get("rationale") or "").strip()
            if not crit:
                continue
            rationale = (base + "\n\n(Revision note) Addressed peer critiques: " + crit[:300]).strip()
            out[role] = {"rationale": rationale, "notes": "Heuristic revision applied."}
        return out

    for role, rep in reports.items():
        if not isinstance(rep, dict):
            continue
        prompt = f"""You are the {role} agent. Improve your rationale based on peer critiques below.

Original rationale:
{rep.get('rationale','')}

Peer critiques:
{crit or '(none)'}

Return STRICT JSON with optional fields:
{{"rationale": "...","notes": "what changed"}}"""
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
            r = {}
            if isinstance(data.get("rationale"), str) and data["rationale"].strip():
                r["rationale"] = data["rationale"].strip()
            if isinstance(data.get("notes"), str) and data["notes"].strip():
                r["notes"] = data["notes"].strip()
            if r:
                out[role] = r
        except Exception:
            # ignore on failure
            pass
    return out
