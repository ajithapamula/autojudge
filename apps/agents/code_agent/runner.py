import subprocess, tempfile, json, os, shutil
from typing import List
from packages.scoring.schemas import AgentResult, SubScore, JudgeRequest
from packages.scoring.weights import weighted_total

TOOLS = {
    "ruff": ["ruff", "check", "--output-format", "json"],
    "radon": ["radon", "cc", "-s", "-j", "."],
    "bandit": ["bandit", "-r", ".", "-f", "json"],
}

async def run_code_agent(req: JudgeRequest) -> AgentResult:
    tmp = tempfile.mkdtemp()
    try:
        subprocess.run(["git", "clone", "--depth", "1", req.repo_url, tmp], check=True)
        # run tools with cwd=tmp (avoid global chdir)
        results = {}
        for name, cmd in TOOLS.items():
            try:
                out = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=tmp)
                results[name] = out.stdout
            except Exception as e:
                results[name] = str(e)

        subs: List[SubScore] = []

        # Repo Hygiene
        present = [os.path.exists(os.path.join(tmp, p)) for p in ["README.md", "LICENSE", "requirements.txt", "pyproject.toml"]]
        hygiene = (sum(present) / 4) * 5
        subs.append(SubScore(criterion="Repo Hygiene", score=hygiene, weight=0.10, rationale=f"Files present: {present}"))

        # Code Quality (ruff + radon)
        ruff_errs = 0
        try:
            ruff_json = json.loads(results.get("ruff", "[]"))
            # ruff JSON is a list of diagnostics; count length
            if isinstance(ruff_json, list):
                ruff_errs = len(ruff_json)
            else:
                # older schema fallback
                ruff_errs = sum(len(f.get("messages", [])) for f in ruff_json)
        except Exception:
            pass

        cc_penalty = 0
        try:
            radon_json = json.loads(results.get("radon", "{}"))
            for _, blocks in radon_json.items():
                for b in blocks:
                    if b.get("rank") in ["D", "E", "F"]:
                        cc_penalty += 1
        except Exception:
            pass

        quality = max(0, 5 - (1 if ruff_errs > 50 else 0) - min(cc_penalty, 3))
        subs.append(SubScore(criterion="Code Quality", score=quality, weight=0.10, rationale=f"ruff={ruff_errs}, radon_bad={cc_penalty}"))

        # Security (bandit)
        high = 0
        try:
            bandit_json = json.loads(results.get("bandit", "{}"))
            for r in bandit_json.get("results", []):
                if r.get("issue_severity") == "HIGH":
                    high += 1
        except Exception:
            pass
        security = max(0, 5 - min(high, 5))
        subs.append(SubScore(criterion="Security", score=security, weight=0.05, rationale=f"bandit_high={high}"))

        # Tests
        has_tests = os.path.isdir(os.path.join(tmp, "tests"))
        tests_score = 5 if has_tests else 1
        subs.append(SubScore(criterion="Tests & Coverage", score=tests_score, weight=0.07, rationale=f"tests_dir={has_tests}"))

        # Architecture
        top_dirs = [d for d in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, d)) and d not in [".git", "tests", "venv", "__pycache__"]]
        arch = min(5, 1 + len(top_dirs) / 3)
        subs.append(SubScore(criterion="Architecture & Modularity", score=arch, weight=0.08, rationale=f"dirs={top_dirs}"))

        total = weighted_total(subs)
        return AgentResult(agent="code", subscores=subs, total=round(total, 2), notes="Static tools + heuristics")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
