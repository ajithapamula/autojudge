from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Optional

class SubScore(BaseModel):
    criterion: str
    score: float  # 0-5
    weight: float # 0-1
    rationale: str

class AgentResult(BaseModel):
    agent: str  # code/design/pitch
    subscores: List[SubScore]
    total: float  # weighted 0-100
    notes: Optional[str] = None

class JudgeRequest(BaseModel):
    project_id: str
    repo_url: Optional[HttpUrl] = None
    figma_file_key: Optional[str] = None
    pitch_url: Optional[HttpUrl] = None
    weights: Dict[str, float] = {"code":0.4, "design":0.3, "pitch":0.3}

class JudgeResponse(BaseModel):
    project_id: str
    agent_results: List[AgentResult]
    final_score: float
    ranking_features: Dict[str, float]
    verdict: str
