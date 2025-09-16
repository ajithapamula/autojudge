from typing import Dict, Any, Optional
import os
from langchain_openai import ChatOpenAI

# Try to import prompt; fallback to default text if not present
try:
    from app.prompt import JUDGE_PROMPT
except Exception:
    JUDGE_PROMPT = """You are the Head Judge of a hackathon.
You receive three agent reports (code/design/pitch). Each report has score, subscores, rationale, and evidence.
Task:
1) sanity-check the reports
2) compute weighted score with given weights
3) give 3-5 actionable feedback bullets

Return JSON:
- final_score (float)
- verdict (Excellent/Good/Average/Needs Work)
- feedback (list[str])
"""
