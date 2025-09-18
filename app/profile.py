# app/profile.py
from __future__ import annotations

import asyncio
from typing import Dict, Any, List, Optional

import httpx

from app.agents.code_agent import score_code_quality
from app.utils.github_client import _headers  # reuse your GitHub auth headers


async def _fetch_repos(handle: str, kind: str = "user") -> List[Dict[str, Any]]:
    """
    Fetch public repos for a user or org via GitHub REST.
    Returns the raw repo objects (we only use a few fields).
    """
    base = "https://api.github.com"
    path = f"/users/{handle}/repos" if kind == "user" else f"/orgs/{handle}/repos"
    repos: List[Dict[str, Any]] = []

    # Grab up to 300 repos in 3 pages (100 per page)
    async with httpx.AsyncClient(timeout=15) as client:
        for page in (1, 2, 3):
            r = await client.get(
                f"{base}{path}",
                params={"per_page": 100, "page": page, "sort": "updated"},
                headers=_headers(),
            )
            if r.status_code != 200:
                # bubble up a helpful message
                msg = r.json().get("message") if r.headers.get("content-type", "").startswith("application/json") else r.text
                raise RuntimeError(f"GitHub API error {r.status_code}: {msg}")
            batch = r.json()
            if not isinstance(batch, list) or not batch:
                break
            repos.extend(batch)
            if len(batch) < 100:
                break
    return repos


def _repo_display(rec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": rec.get("name"),
        "url": rec.get("html_url"),
        "stars": rec.get("stargazers_count", 0),
        "updated_at": rec.get("updated_at"),
        "fork": bool(rec.get("fork")),
    }


def _median(nums: List[float]) -> float:
    if not nums:
        return 0.0
    xs = sorted(nums)
    n = len(xs)
    mid = n // 2
    if n % 2 == 1:
        return float(xs[mid])
    return round((xs[mid - 1] + xs[mid]) / 2.0, 2)


async def score_profile(
    handle: str,
    kind: str = "user",
    max_repos: int = 5,
    include_forks: bool = False,
) -> Dict[str, Any]:
    """
    Fetch the user's/org's repos, select the most recently updated,
    run the code quality scorer on each, and aggregate.
    """
    # 1) fetch repos
    all_repos = await _fetch_repos(handle, kind)
    # 2) filter forks if requested
    if not include_forks:
        all_repos = [r for r in all_repos if not r.get("fork")]
    # 3) sort by updated_at desc and take top N
    all_repos.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
    chosen = all_repos[: max(1, max_repos)]

    # 4) score concurrently
    async def _score_one(rec: Dict[str, Any]) -> Dict[str, Any]:
        display = _repo_display(rec)
        repo_url = display["url"]
        try:
            sc = await score_code_quality(repo_url)
            return {
                **display,
                "score": sc.get("score", 0),
                "subscores": sc.get("subscores", {}),
                "rationale": sc.get("rationale", ""),
            }
        except Exception as e:
            # keep the list robust even if a repo errors
            return {
                **display,
                "score": 0,
                "subscores": {},
                "rationale": f"scoring error: {type(e).__name__}: {e}",
            }

    results = await asyncio.gather(*[_score_one(r) for r in chosen])

    # 5) summary stats
    scores = [float(r.get("score") or 0) for r in results if isinstance(r.get("score"), (int, float))]
    avg = round(sum(scores) / len(scores), 2) if scores else 0.0
    med = _median(scores)

    # normalize output shape your frontend already expects
    return {
        "handle": handle,
        "kind": kind,
        "count": len(results),
        "results": results,
        "summary": {
            "avg": avg,
            "median": med,
            "top": sorted(
                [{"name": r["name"], "url": r["url"], "score": r["score"]} for r in results],
                key=lambda x: x["score"],
                reverse=True,
            ),
        },
    }
