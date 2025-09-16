from typing import Dict, Any, List
import json
from app.utils.github_client import list_repo_files, get_file_content

def _readme_points(text: str) -> int:
    if not text:
        return 0
    pts = 0
    low = text.lower()
    if any(k in low for k in ("install", "setup", "quick start")): pts += 8
    if any(k in low for k in ("usage", "example")): pts += 6
    if "contribut" in low: pts += 4
    if "license" in low: pts += 2
    return min(20, max(5, pts))

async def score_code_quality(repo_url: str) -> Dict[str, Any]:
    try:
        files: List[str] = await list_repo_files(repo_url)
    except Exception as e:
        return {"score": 0, "subscores": {}, "rationale": f"GitHub API error: {e}", "evidence": []}

    readme_text = ""
    try:
        # common capitalizations
        for p in ("README.md", "Readme.md", "readme.md", "README", "README.rst"):
            if any(f.endswith(p) for f in files):
                readme_text = await get_file_content(repo_url, p)
                if readme_text:
                    break
    except Exception:
        pass

    def has_readme():   return any(f.lower().endswith("readme.md") or f == "README" for f in files)
    def has_tests():    return any("test" in f.lower() for f in files)
    def has_ci():       return any(f.startswith(".github/workflows/") for f in files)
    def has_license():  return any(f.lower() in ("license","license.md","licence","licence.md") for f in files)

    documentation = max(_readme_points(readme_text), 20 if has_readme() else 5)
    testing = 20 if has_tests() else 0
    ci_cd = 15 if has_ci() else 0
    license_pts = 10 if has_license() else 0
    structure = 5

    score = min(100, documentation + testing + ci_cd + license_pts + structure)
    return {
        "score": score,
        "subscores": {
            "documentation": documentation,
            "testing": testing,
            "ci_cd": ci_cd,
            "license": license_pts,
            "structure": structure,
        },
        "rationale": "Heuristics from repo files: README/tests/CI/license/structure.",
        "evidence": files[:15],
    }
