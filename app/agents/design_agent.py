from typing import Dict, Any, List
from app.utils.github_client import list_repo_files, get_file_content

IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
UI_HINTS = [
    "react", "next", "vue", "svelte", "angular", "tailwind", "chakra", "material ui", "bootstrap",
    "flutter", "dart", "android", "kotlin", "swiftui", "swift", "jetpack compose",
]
A11Y_HINTS = ["aria-", "alt=", "keyboard", "screen reader", "contrast", "a11y", "accessibility"]
DESIGN_DOC_HINTS = ["ui/ux", "ux", "user experience", "design system", "wireframe", "prototype", "mockup"]

def _score_visuals(files: List[str]) -> int:
    n = sum(1 for f in files if f.lower().endswith(IMG_EXT))
    if n == 0: return 0
    if n <= 2: return 15
    if n <= 5: return 25
    return 35

def _score_structure(files: List[str], readme: str) -> int:
    text = (readme or "").lower()
    pts = 0
    joined = " ".join(files).lower()
    if any(k in joined for k in ("package.json", "src/", "public/", "tailwind.config.js", ".css", ".html")):
        pts += 10
    if any(k in joined for k in ("lib/main.dart", "pubspec.yaml", "android/", "ios/")):
        pts += 10
    if any(h in text for h in UI_HINTS):
        pts += 5
    return min(25, pts)

def _score_accessibility(readme: str) -> int:
    low = (readme or "").lower()
    hits = sum(h in low for h in A11Y_HINTS)
    return [0, 8, 14, 20][min(3, hits)]

def _score_docs(readme: str) -> int:
    low = (readme or "").lower()
    pts = 0
    if "installation" in low or "setup" in low or "quick start" in low:
        pts += 6
    if "usage" in low or "demo" in low or "screenshots" in low:
        pts += 6
    if any(h in low for h in DESIGN_DOC_HINTS):
        pts += 8
    return min(20, pts)

async def score_design_quality(repo_url: str) -> Dict[str, Any]:
    try:
        files = await list_repo_files(repo_url)
    except Exception as e:
        return {"score": 0, "subscores": {}, "rationale": f"GitHub API error: {e}", "evidence": []}

    readme = ""
    for p in ("README.md", "Readme.md", "readme.md", "README", "README.rst"):
        if any(f.endswith(p) for f in files):
            readme = await get_file_content(repo_url, p) or ""
            if readme:
                break

    visuals = _score_visuals(files)
    structure = _score_structure(files, readme)
    accessibility = _score_accessibility(readme)
    docs = _score_docs(readme)

    score = min(100, visuals + structure + accessibility + docs)
    rationale = (
        "Heuristic UI/UX signals from repo: "
        f"{sum(1 for f in files if f.lower().endswith(IMG_EXT))} images/screens; "
        f"structure hints; accessibility mentions; README docs."
    )

    evidence = []
    for f in files:
        lf = f.lower()
        if lf.endswith(IMG_EXT) or any(k in lf for k in ("src/", "public/", "lib/", "android/", "ios/", ".css", ".html", "tailwind.config.js")):
            evidence.append(f)
        if len(evidence) >= 10:
            break

    return {
        "score": score,
        "subscores": {"visuals": visuals, "structure": structure, "accessibility": accessibility, "docs": docs},
        "rationale": rationale,
        "evidence": evidence,
    }
