import os, requests
from packages.scoring.schemas import AgentResult, SubScore, JudgeRequest
from packages.scoring.weights import weighted_total

FIGMA_TOKEN = os.getenv("FIGMA_TOKEN", "DUMMY")

async def run_design_agent(req: JudgeRequest) -> AgentResult:
    subs = []
    if not req.figma_file_key:
        for k, w in [("IA",0.08),("Visual",0.07),("Interaction",0.07),("A11y",0.05),("Readiness",0.03)]:
            subs.append(SubScore(criterion=k, score=2.5, weight=w, rationale="No Figma; default midpoint."))
        return AgentResult(agent="design", subscores=subs, total=round(weighted_total(subs),2), notes="No Figma")

    headers = {"X-Figma-Token": FIGMA_TOKEN}
    r = requests.get(f"https://api.figma.com/v1/files/{req.figma_file_key}", headers=headers, timeout=30)
    data = r.json()

    pages = len(data.get("document", {}).get("children", []))
    components = len(data.get("components", {}))
    styles = len(data.get("styles", {}))

    subs.append(SubScore(criterion="Information Architecture", score=min(5, 1+pages/3), weight=0.08, rationale=f"pages={pages}"))
    subs.append(SubScore(criterion="Visual Design Quality",   score=min(5, 1+styles/10), weight=0.07, rationale=f"styles={styles}"))
    subs.append(SubScore(criterion="Interaction Quality",     score=min(5, 1+components/20), weight=0.07, rationale=f"components={components}"))
    subs.append(SubScore(criterion="Accessibility",           score=3.0, weight=0.05, rationale="Default heuristic"))
    subs.append(SubScore(criterion="Design-to-Build Readiness", score=3.5, weight=0.03, rationale="Component counts imply readiness"))

    return AgentResult(agent="design", subscores=subs, total=round(weighted_total(subs),2), notes="Figma heuristics")
