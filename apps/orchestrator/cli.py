import asyncio, json, sys
from packages.scoring.schemas import JudgeRequest
from .judge import run_judging

if __name__ == "__main__":
    req = JudgeRequest(
        project_id="demo1",
        repo_url=sys.argv[1] if len(sys.argv) > 1 else "https://github.com/pallets/flask",
        figma_file_key=None,
        pitch_url=None,
    )
    resp = asyncio.run(run_judging(req))
    print(json.dumps(resp.model_dump(), indent=2))
