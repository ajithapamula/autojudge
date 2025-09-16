import asyncio
from typing import List, Dict, Any
from app.utils.github_client import list_user_repos, list_org_repos
from app.agents.code_agent import score_code_quality

def _select_repos(repos: List[Dict], *, include_forks: bool, max_repos: int) -> List[Dict]:
    items = [r for r in repos if include_forks or not r.get("fork")]
    items.sort(key=lambda r: (r.get("stargazers_count",0), r.get("updated_at","")), reverse=True)
    return items[:max_repos]

async def score_profile(handle: str, kind: str = "user", max_repos: int = 20, include_forks: bool = False) -> Dict[str, Any]:
    repos = await (list_org_repos(handle) if kind=="org" else list_user_repos(handle))
    if not repos:
        return {"handle": handle, "kind": kind, "count": 0, "results": [], "summary": {"avg": 0.0, "median": 0.0, "top": []}}

    sel = _select_repos(repos, include_forks=include_forks, max_repos=max_repos)

    async def score_one(r: Dict) -> Dict[str, Any]:
        url = r.get("html_url")
        try:
            res = await score_code_quality(url)
        except Exception as e:
            res = {"score": 0, "error": str(e), "subscores": {}, "rationale": "scoring failed", "evidence": []}
        return {
            "name": r.get("name"),
            "url": url,
            "stars": r.get("stargazers_count", 0),
            "updated_at": r.get("updated_at"),
            "fork": r.get("fork", False),
            "score": res.get("score", 0),
            "subscores": res.get("subscores", {}),
            "rationale": res.get("rationale", ""),
        }

    results = await asyncio.gather(*[score_one(r) for r in sel])

    scores = sorted([x["score"] for x in results], reverse=True)
    if scores:
        avg = round(sum(scores)/len(scores), 2)
        median = round(scores[len(scores)//2] if len(scores)%2==1 else (scores[len(scores)//2-1]+scores[len(scores)//2])/2, 2)
    else:
        avg = median = 0.0

    top = sorted(results, key=lambda x: x["score"], reverse=True)[:5]

    return {
        "handle": handle,
        "kind": kind,
        "count": len(results),
        "results": results,
        "summary": {
            "avg": avg,
            "median": median,
            "top": [{"name": t["name"], "url": t["url"], "score": t["score"]} for t in top]
        }
    }
