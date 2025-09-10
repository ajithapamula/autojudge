import requests
from packages.scoring.schemas import AgentResult, SubScore, JudgeRequest
from packages.scoring.weights import weighted_total

async def run_pitch_agent(req: JudgeRequest) -> AgentResult:
    subs = []
    if not req.pitch_url:
        for k,w in [("Problem",0.08),("Solution",0.07),("Evidence",0.07),("Delivery",0.05),("Originality",0.03)]:
            subs.append(SubScore(criterion=k, score=2.5, weight=w, rationale="No pitch; midpoint default."))
        return AgentResult(agent="pitch", subscores=subs, total=round(weighted_total(subs),2), notes="No pitch")

    resp = requests.get(req.pitch_url, timeout=30)
    size_kb = len(resp.content)/1024

    subs.append(SubScore(criterion="Problem Clarity",     score=min(5,1+size_kb/300), weight=0.08, rationale=f"size_kb≈{size_kb:.0f}"))
    subs.append(SubScore(criterion="Solution Narrative",  score=min(5,1+size_kb/300), weight=0.07, rationale="Proxy until parser added"))
    subs.append(SubScore(criterion="Evidence & Feasibility", score=3.0, weight=0.07, rationale="Default until parsing"))
    subs.append(SubScore(criterion="Delivery & Structure",   score=3.0, weight=0.05, rationale="Default"))
    subs.append(SubScore(criterion="Originality",            score=3.0, weight=0.03, rationale="Default"))

    return AgentResult(agent="pitch", subscores=subs, total=round(weighted_total(subs),2), notes="Heuristics only")
