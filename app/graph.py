# app/graph.py
from typing import TypedDict, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

from app.agents.code_agent import score_code_quality
from app.agents.pitch_agent import score_pitch_quality
from app.agents.design_agent import score_design_quality
from app.agents.judge_agent import judge_finalize


class JudgeState(TypedDict, total=False):
    repo_url: str
    pitch_url: Optional[str]
    code: Dict[str, Any]
    pitch: Dict[str, Any]
    design: Dict[str, Any]
    final: Dict[str, Any]


async def code_node(state: JudgeState) -> Dict[str, Any]:
    if not state.get("repo_url"):
        return {}
    res = await score_code_quality(state["repo_url"])
    return {"code": res}


async def pitch_node(state: JudgeState) -> Dict[str, Any]:
    """
    If pitch_url provided -> analyze it.
    Else -> analyze repo README as pitch (fallback).
    """
    target = state.get("pitch_url") or state.get("repo_url")
    if not target:
        return {}
    res = await score_pitch_quality(target)
    return {"pitch": res}


async def design_node(state: JudgeState) -> Dict[str, Any]:
    if not state.get("repo_url"):
        return {}
    res = await score_design_quality(state["repo_url"])
    return {"design": res}


async def judge_node(state: JudgeState) -> Dict[str, Any]:
    final = await judge_finalize({
        "code": state.get("code"),
        "pitch": state.get("pitch"),
        "design": state.get("design"),
    })
    return {"final": final}


def build_graph():
    g = StateGraph(JudgeState)
    g.add_node("code", code_node)
    g.add_node("pitch", pitch_node)
    g.add_node("design", design_node)
    g.add_node("judge", judge_node)

    g.add_edge(START, "code")
    g.add_edge(START, "pitch")
    g.add_edge(START, "design")
    g.add_edge("code", "judge")
    g.add_edge("pitch", "judge")
    g.add_edge("design", "judge")
    g.add_edge("judge", END)

    return g.compile()
