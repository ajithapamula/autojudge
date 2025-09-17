# app/agents/judge_agent.py
from __future__ import annotations

from typing import Dict, Any, Optional, List
import os
import json

from langchain_openai import ChatOpenAI
from app.prompt import JUDGE_PROMPT

# ---------------- Weights (env override supported) ----------------
DEFAULT_WEIGHTS_STR = os.getenv("JUDGE_WEIGHTS", "code:0.6,design:0.2,pitch:0.2")
DEFAULT_WEIGHTS: Dict[str, float] = {}
for item in DEFAULT_WEIGHTS_STR.split(","):
    if ":" in item:
        k, v = item.split(":", 1)
        try:
            DEFAULT_WEIGHTS[k.strip()] = float(v)
        except Exception:
            pass

# ---------------- Optional LLM client ----------------
_llm: Optional[ChatOpenAI] = None
if os.getenv("OPENAI_API_KEY"):
    try:
        _llm = ChatOpenAI(
            model=os.getenv("JUDGE_MODEL", "gpt-4o-mini"),
            temperature=0,
        )
    except Exception:
        _llm = None


# ---------------- Helpers ----------------
def _normalize_weights(available: Dict[str, Any], weights: Dict[str, float]) -> Dict[str, float]:
    w = {k: max(0.0, float((weights or {}).get(k, 0.0))) for k in available.keys()}
    s = sum(w.values())
    if s <= 0:
        n = max(1, len(available))
        return {k: 1.0 / n for k in available.keys()}
    return {k: v / s for k, v in w.items()}


def _verdict(score: float) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 55:
        return "Average"
    return "Needs Work"


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def _merge_unique(dst: List[str], src: List[str], limit: int | None = None) -> List[str]:
    seen = {s.strip() for s in dst}
    for s in src:
        t = str(s).strip()
        if t and t not in seen:
            dst.append(t)
            seen.add(t)
            if limit and len(dst) >= limit:
                break
    return dst


def _heuristic_feedback(present: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Build repo-specific feedback from agent subscores/rationales.
    This runs when the LLM is unavailable or returns nothing useful.
    """
    code = present.get("code") or {}
    design = present.get("design") or {}
    pitch = present.get("pitch") or {}

    subs = (code.get("subscores") or {}) | {}
    doc_score = int(subs.get("documentation") or 0)
    test_score = int(subs.get("testing") or 0)
    ci_score = int(subs.get("ci_cd") or 0)
    lic_score = int(subs.get("license") or 0)
    struct_score = int(subs.get("structure") or 0)

    dsubs = (design.get("subscores") or {}) | {}
    visuals = int(dsubs.get("visuals") or 0)
    a11y = int(dsubs.get("accessibility") or 0)
    dd = int(dsubs.get("docs") or 0)

    code_improvements: List[str] = []
    readme_improvements: List[str] = []
    mistakes: List[str] = []
    quick_wins: List[str] = []

    # ---- code / repo hygiene
    if test_score <= 40:
        _merge_unique(code_improvements, [
            "Add a minimal pytest suite covering critical paths; target ≥60% coverage to start.",
            "Create factories/fixtures for DB and API layers to avoid brittle tests.",
        ])
        _merge_unique(quick_wins, [
            "Add `pytest -q` smoke test and run it in CI.",
        ])

    if ci_score <= 40:
        _merge_unique(code_improvements, [
            "Introduce CI with GitHub Actions: lint (ruff/flake8), type-check (mypy), tests, and cache pip.",
        ])
        _merge_unique(quick_wins, [
            "Drop `.github/workflows/ci.yml` with a simple Python matrix (3.10–3.12).",
        ])
        mistakes.append("CI workflow not detected or failing.")

    if lic_score <= 0:
        mistakes.append("License file missing; add a standard LICENSE (MIT/Apache-2.0).")
        _merge_unique(quick_wins, ["Add `LICENSE` at repo root."])

    if struct_score <= 40:
        _merge_unique(code_improvements, [
            "Refactor large modules into cohesive packages; keep I/O and business logic separate.",
            "Add type hints (PEP 484) for public functions; run `mypy --strict` on core modules.",
        ])

    # ---- docs / README / pitch overlap
    if doc_score <= 40 or dd <= 40 or (pitch.get("score") or 0) <= 40:
        _merge_unique(readme_improvements, [
            "Write a Quickstart with exact commands: `git clone`, `python -m venv`, `pip install -r requirements.txt`, and `uvicorn app.main:app --reload`.",
            "Add an architecture diagram (request flow + components) and a feature checklist.",
            "Include screenshots/GIFs of the UI or cURL demos of key endpoints.",
            "Document configuration via `.env.example`, and explain necessary API keys/tokens.",
        ])
        _merge_unique(quick_wins, [
            "Add status badges (build, coverage, license) to README header.",
            "Link to your live demo or a recorded Loom walkthrough.",
        ])

    # ---- design / accessibility hints
    if visuals <= 40:
        _merge_unique(readme_improvements, [
            "Add UI screenshots with light/dark theme examples; annotate key flows.",
        ])
    if a11y <= 40:
        _merge_unique(code_improvements, [
            "Adopt basic a11y: semantic HTML, aria-labels, focus states, and keyboard navigation.",
        ])

    # Deduplicate and trim
    return {
        "code_improvements": code_improvements[:10],
        "readme_improvements": readme_improvements[:10],
        "mistakes": list(dict.fromkeys(mistakes))[:10],
        "quick_wins": quick_wins[:10],
    }


# ---------------- Main entry ----------------
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
        return {
            "final_score": 0.0,
            "verdict": "Needs Work",
            "parts": [],
            "feedback": _heuristic_feedback({}),  # minimal, generic
        }

    # weights + deterministic final score
    w = _normalize_weights(present, weights or DEFAULT_WEIGHTS)

    final = 0.0
    parts = []
    for k, rep in present.items():
        wk = w.get(k, 0.0)
        final += rep["score"] * wk
        parts.append({"agent": k, "score": rep["score"], "weight": round(wk * 100, 2)})
    final = round(final, 2)
    verdict = _verdict(final)

    # -------- LLM feedback (optional, best-effort) --------
    llm_feedback: Optional[Dict[str, List[str]]] = None
    if _llm:
        try:
            sys_msg = {"role": "system", "content": JUDGE_PROMPT.strip()}
            user_msg = {
                "role": "user",
                "content": (
                    "You are given agent reports for code/design/pitch and weights.\n"
                    "Return STRICT JSON with this schema ONLY (no prose):\n"
                    "{\n"
                    '  "final_score": number,  // you may ignore; server keeps its own\n'
                    '  "verdict": string,      // optional; server keeps its own\n'
                    '  "feedback": {\n'
                    '    "code_improvements": string[],\n'
                    '    "readme_improvements": string[],\n'
                    '    "mistakes": string[],\n'
                    '    "quick_wins": string[]\n'
                    "  }\n"
                    "}\n\n"
                    f"Reports JSON:\n{_safe_json(present)}\n\n"
                    f"Weights JSON:\n{_safe_json(w)}\n"
                ),
            }

            # Ask model for JSON and parse manually (more robust across versions)
            resp = await _llm.ainvoke([sys_msg, user_msg])
            text = (resp.content or "").strip()

            # Allow ```json ...``` fences
            if "```" in text:
                s = text.find("```")
                e = text.rfind("```")
                if s != -1 and e != -1 and e > s:
                    text = text[s + 3:e]
                    if text.startswith("json"):
                        text = text[4:].strip()

            parsed = json.loads(text)
            fb = (parsed or {}).get("feedback") or {}
            # normalize lists
            llm_feedback = {
                "code_improvements": [str(x) for x in fb.get("code_improvements", [])][:10],
                "readme_improvements": [str(x) for x in fb.get("readme_improvements", [])][:10],
                "mistakes": [str(x) for x in fb.get("mistakes", [])][:10],
                "quick_wins": [str(x) for x in fb.get("quick_wins", [])][:10],
            }
            # if model returned completely empty, consider it a failure
            if not any(llm_feedback.values()):
                llm_feedback = None
        except Exception:
            llm_feedback = None

    # Fallback to heuristics or merge (LLM first, then heuristics fill gaps)
    heur = _heuristic_feedback(present)
    if llm_feedback:
        feedback = {
            "code_improvements": _merge_unique(llm_feedback["code_improvements"][:], heur["code_improvements"], 10),
            "readme_improvements": _merge_unique(llm_feedback["readme_improvements"][:], heur["readme_improvements"], 10),
            "mistakes": _merge_unique(llm_feedback["mistakes"][:], heur["mistakes"], 10),
            "quick_wins": _merge_unique(llm_feedback["quick_wins"][:], heur["quick_wins"], 10),
        }
    else:
        feedback = heur

    return {
        "final_score": final,
        "verdict": verdict,
        "parts": parts,
        "feedback": feedback,
    }
