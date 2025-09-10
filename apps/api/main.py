from fastapi import FastAPI
from packages.scoring.schemas import JudgeRequest, JudgeResponse
from apps.orchestrator.judge import run_judging

app = FastAPI(title="Autonomous Hackathon Judge")

@app.post("/score", response_model=JudgeResponse)
async def score(req: JudgeRequest):
    return await run_judging(req)
