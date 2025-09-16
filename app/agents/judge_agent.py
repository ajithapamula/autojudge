# app/agents/judge_agent.py
from typing import Dict, Any, Optional
import os
from langchain_openai import ChatOpenAI
from app.prompt import JUDGE_PROMPT

DEFAULT_WEIGHTS_STR = os.getenv("JUDGE_WEIGHTS", "code:0.6,design:0.2,pitch:0.2")
DEFAULT_WEIGHTS: Dict[str, float] = {}
for item in DEFAULT_WEIGHTS_STR.split(","):
    if ":" in item:
        k, v = item.split(":", 1)
        try:
            DEFAULT_WEIGHTS[k.strip()] = float(v)
        except Exception:
            pass

_llm: Optional[ChatOpenAI] = None
if os.getenv("OPENAI_API_KEY"):
    try:
        _llm = ChatOpenAI(model=os.getenv("JUDGE_MODEL", "gpt-4o-mini"), temperature=0)
    except Exception:
        _llm = None

def _normalize_weights(available: Dict[str, Any], weights: Dict[str, float]) -> Dict[str, float]:
    w = {k: max(0.0, float(weights.get(k, 0.0))) for k in available.keys()}
    s = sum(w.values())
    if s <= 0:
        n = max(1, len(available))
        return {k: 1.0 / n for k in available.keys()}
    return {k: v / s for k, v in w.items()}

def _verdict(score: float) -> str:
    if score >= 85: return "Excellent"
    if score >= 70: return "Good"
    if score >= 55: return "Average"
    return "Needs Work"

async def judge_finalize(agents: Dict[str, Any], weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    # keep only valid reports
    present: Dict[str, Any] = {}
    for key in ("code", "design", "pitch"):
        rep = agents.get(key)
        if isinstance(rep, dict) and isinstance(rep.get("score"), (int, float)):
            present[key] = {
                "score": float(rep["score"]),
                "subscores": rep.get("subscores", {}),
                "rationale": rep.get("rationale", ""),
                "evidence": rep.get("evidence", []),
            }
    if not present:
        return {"final_score": 0.0, "verdict": "Needs Work", "parts": [], "feedback": ["No valid agent reports were provided."]}

    w = _normalize_weights(present, weights or DEFAULT_WEIGHTS)

    # weighted score
    final = 0.0
    parts = []
    for k, rep in present.items():
        wk = w.get(k, 0.0)
        final += rep["score"] * wk
        parts.append({"agent": k, "score": rep["score"], "weight": round(wk * 100, 2)})
    final = round(final, 2)
    verdict = _verdict(final)

    # optional LLM feedback using your JUDGE_PROMPT
    feedback = None
    if _llm:
        try:
            sys_msg = {
                "role": "system",
                "content": JUDGE_PROMPT.strip(),
            }
            user_msg = {
                "role": "user",
                "content": f"Reports:\n{present}\n\nWeights:\n{w}\n\nReturn JSON with keys: final_score, verdict, feedback (list[str]).",
            }
            # We only want feedback; we keep our deterministic score & verdict
            data = await _llm.with_structured_output(schema=dict).ainvoke([sys_msg, user_msg])
            if isinstance(data, dict) and isinstance(data.get("feedback"), list):
                feedback = [str(x) for x in data["feedback"]][:5]
        except Exception:
            feedback = None

    if not feedback:
        feedback = [
            "Clarify problem, solution, and a quickstart in README.",
            "Add automated tests and a basic CI workflow.",
            "Include concrete metrics (users, latency, accuracy, or benchmarks).",
        ]

    return {"final_score": final, "verdict": verdict, "parts": parts, "feedback": feedback}
