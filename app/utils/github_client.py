import os, re, base64
from typing import List, Dict, Any, Tuple, Optional
import httpx

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def _headers() -> Dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "autojudge/1.0"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h

def _parse_repo_url(repo_input: str) -> Tuple[str, str]:
    """
    Accepts:
      - owner/repo
      - https://github.com/owner/repo
      - http://github.com/owner/repo
      - www.github.com/owner/repo
      - git@github.com:owner/repo.git
      - any of the above with trailing slash or .git
    """
    s = repo_input.strip()
    s = re.sub(r'^git@github\.com:', '', s, flags=re.I)
    s = re.sub(r'^(https?://)?(www\.)?github\.com/', '', s, flags=re.I)
    s = s.strip().strip('/')
    if s.lower().endswith('.git'):
        s = s[:-4]
    parts = s.split('/')
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError("Invalid repo. Use 'owner/repo' or a GitHub URL.")
    return parts[0], parts[1]

async def _default_branch(owner: str, repo: str, client: httpx.AsyncClient) -> Optional[str]:
    r = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=_headers())
    if r.status_code == 404:
        raise httpx.HTTPStatusError("Repo not found", request=r.request, response=r)
    r.raise_for_status()
    return r.json().get("default_branch")

async def get_repo_metadata(owner: str, repo: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=_headers())
        r.raise_for_status()
        return r.json()

async def list_repo_files(repo_input: str) -> List[str]:
    owner, repo = _parse_repo_url(repo_input)
    async with httpx.AsyncClient(timeout=30) as client:
        # find default branch
        branch = await _default_branch(owner, repo, client) or "main"
        # try by branch name
        r = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
            headers=_headers(),
        )
        if r.status_code == 404:
            # resolve sha from branches API
            b = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}",
                headers=_headers(),
            )
            b.raise_for_status()
            sha = b.json().get("commit", {}).get("sha")
            if sha:
                r = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/git/trees/{sha}?recursive=1",
                    headers=_headers(),
                )
        if r.status_code in (403, 429):
            msg = "GitHub rate limit. Set GITHUB_TOKEN env var for higher limits."
            raise RuntimeError(msg)
        r.raise_for_status()
        tree = r.json().get("tree", [])
        return [t["path"] for t in tree if t.get("type") == "blob"]

async def get_file_content(repo_input: str, path: str) -> str:
    owner, repo = _parse_repo_url(repo_input)
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
            headers=_headers(),
        )
        if r.status_code == 404:
            return ""
        if r.status_code in (403, 429):
            raise RuntimeError("GitHub rate limit. Set GITHUB_TOKEN to avoid 0 scores.")
        r.raise_for_status()
        j = r.json()
        if isinstance(j, dict) and j.get("encoding") == "base64":
            return base64.b64decode(j.get("content", "")).decode("utf-8", errors="ignore")
        if isinstance(j, dict) and isinstance(j.get("content"), str):
            return j["content"]
        return ""

async def list_user_repos(handle: str) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"https://api.github.com/users/{handle}/repos?per_page=100&type=owner&sort=updated",
            headers=_headers(),
        )
        if r.status_code in (403, 429):
            raise RuntimeError("GitHub rate limit. Set GITHUB_TOKEN.")
        r.raise_for_status()
        return r.json()

async def list_org_repos(handle: str) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"https://api.github.com/orgs/{handle}/repos?per_page=100&type=public&sort=updated",
            headers=_headers(),
        )
        if r.status_code in (403, 429):
            raise RuntimeError("GitHub rate limit. Set GITHUB_TOKEN.")
        r.raise_for_status()
        return r.json()
