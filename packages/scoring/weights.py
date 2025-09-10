from typing import List
from .schemas import AgentResult

def weighted_total(subscores):
    s = 0.0; W = 0.0
    for ss in subscores:
        s += ss.score * ss.weight
        W += ss.weight
    return 100.0 * (s / max(W, 1e-6))

_DEF_BANDS = [
  (90, "Outstanding: production-ready, polished."),
  (75, "Strong: minor gaps."),
  (60, "Promising: works, needs refinement."),
  (0,  "Early: incomplete."),
]

def to_verdict(results: List[AgentResult], final_score: float) -> str:
    for thr, msg in _DEF_BANDS:
        if final_score >= thr:
            parts = [f"{r.agent}={r.total:.1f}" for r in results]
            return f"{' | '.join(parts)} → Final {final_score:.1f}. {msg}"
    return f"Final {final_score:.1f}."
