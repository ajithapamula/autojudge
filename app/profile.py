import os
import json
import asyncio
from typing import Dict, Any, List
from app.utils.mcp_tools import MCPTool
from app.agents.code_agent import score_code_quality

list_user = MCPTool(
    name="github_list_user",
    description="List user repos via MCP GitHub server",
    cmd=os.getenv("MCP_GITHUB_CMD", "npx"),
    spawn_args=os.getenv("MCP_GITHUB_ARGS", "@modelcontextprotocol/server-github"),
    tool_name=os.getenv("MCP_GITHUB_LIST_USER_TOOL", "github.list_user_repos"),
)

list_org = MCPTool(
    name="github_list_org",
    description="List org repos via MCP GitHub server",
    cmd=os.getenv("MCP_GITHUB_CMD", "npx"),
    spawn_args=os.getenv("MCP_GITHUB_ARGS", "@modelcontextprotocol/server-github"),
    tool_name=os.getenv("MCP_GITHUB_LIST_ORG_TOOL", "github.list_org_repos"),
)

async def _parse_repos(raw: str) -> List[Dict[str, Any]]:
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "repos" in data:
            return data["repos"]
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []

def _select(repos: List[Dict[str, Any]], include_forks: bool, max_repos: int) -> List[Dict[str, Any]]:
    items = [r for r in repos if include_forks or not r.get("fork")]
    items.sort(key=lambda r: (r.get("stargazers_count", 0), r.get("updated_at", "")), reverse=True)
    return items[:max_repos]

async def score_profile_mcp(handle: str, kind: str = "user", max_repos: int = 20, include_forks: bool = False) -> Dict[str, Any]:
    raw = await (list_org.arun(handle) if kind == "org" else list_user.arun(handle))
    repos = await _parse_repos(raw)
    sel = _select(repos, include_forks, max_repos)

    async def one(r: Dict[str, Any]):
        url = r.get("html_url") or f"https://github.com/{r.get('full_name')}"
        res = await score_code_quality(url)
        return {
            "name": r.get("name"),
            "url": url,
            "score": res.get("score", 0),
            "stars": r.get("stargazers_count", 0),
            "updated_at": r.get("updated_at"),
            "fork": r.get("fork", False),
        }

    results = await asyncio.gather(*[one(r) for r in sel])
    scores = sorted([x["score"] for x in results], reverse=True)
    if scores:
        avg = round(sum(scores) / len(scores), 2)
        median = round(scores[len(scores)//2] if len(scores)%2==1 else (scores[len(scores)//2-1]+scores[len(scores)//2]) / 2, 2)
    else:
        avg = median = 0.0
    top = sorted(results, key=lambda x: x["score"], reverse=True)[:5]

    return {"handle": handle, "kind": kind, "count": len(results), "results": results, "summary": {"avg": avg, "median": median, "top": top}}
