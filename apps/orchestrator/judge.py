import asyncio
from packages.scoring.schemas import JudgeRequest, JudgeResponse
from apps.agents.code_agent.runner import run_code_agent
from apps.agents.design_agent.runner import run_design_agent
from apps.agents.pitch_agent.runner import run_pitch_agent
from packages.scoring.weights import to_verdict

async def run_judging(req: JudgeRequest) -> JudgeResponse:
    code_task = run_code_agent(req)
    design_task = run_design_agent(req)
    pitch_task = run_pitch_agent(req)

    code, design, pitch = await asyncio.gather(code_task, design_task, pitch_task)
    agent_results = [code, design, pitch]

    final = sum([r.total * req.weights[r.agent] for r in agent_results])
    verdict = to_verdict(agent_results, final)

    return JudgeResponse(
        project_id=req.project_id,
        agent_results=agent_results,
        final_score=round(final, 2),
        ranking_features={r.agent: r.total for r in agent_results},
        verdict=verdict,
    )
