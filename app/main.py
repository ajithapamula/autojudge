# app/main.py
import os
from typing import Optional, Literal, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx

from app.graph import build_graph
from app.profile import score_profile as score_profile_fn
from app.utils.github_client import _headers  # for /debug/diag

# ------------- App + Graph Engine -------------
app = FastAPI(title="Autonomous Hackathon Judge")
engine = build_graph()

# ------------- Optional frontend --------------
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
async def root():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"message": "Frontend not found. Create app/frontend/index.html"}, status_code=200)

# ------------- Models -------------------------
class ScoreRequest(BaseModel):
    repo_url: str
    pitch_url: Optional[str] = None  # optional; README used if missing

class ProfileRequest(BaseModel):
    handle: str
    kind: Literal["user", "org"] = "user"
    max_repos: int = 5
    include_forks: bool = False

# ------------- Global Error Handlers ----------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        body = await request.body()
    except Exception:
        body = b""
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "detail": exc.errors(), "body": body.decode("utf-8", errors="ignore")},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Return a JSON error without indent (older Starlette doesn't support it)
    return JSONResponse(
        status_code=500,
        content={"error": type(exc).__name__, "message": str(exc)},
    )

# ------------- Helpers ------------------------
async def get_score_payload(request: Request) -> Dict[str, Any]:
    """
    Accept JSON (preferred) or form-encoded payloads.
    Also supports query params for quick tests.
    Returns a plain dict with keys like repo_url / pitch_url.
    """
    ctype = (request.headers.get("content-type") or "").lower()
    data: Dict[str, Any] = {}
    if "application/json" in ctype:
        try:
            data = await request.json()
        except Exception:
            data = {}
    elif "application/x-www-form-urlencoded" in ctype or "multipart/form-data" in ctype:
        try:
            form = await request.form()
            data = dict(form)
        except Exception:
            data = {}
    if not data:
        # allow quick testing via ?repo_url=...
        data = dict(request.query_params)
    return data

# ------------- Endpoints ----------------------
@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/score")
async def score(request: Request):
    """
    Full detailed scoring: code + design + pitch + final aggregation.
    Accepts JSON or form. Requires repo_url; pitch_url optional.
    """
    data = await get_score_payload(request)
    repo_url = data.get("repo_url")
    pitch_url = data.get("pitch_url")
    if not repo_url:
        raise HTTPException(422, detail="repo_url is required")
    out = await engine.ainvoke({"repo_url": repo_url, "pitch_url": pitch_url})
    # out already contains agents + final from the graph
    return JSONResponse(content=out)

@app.post("/score_summary")
async def score_summary(request: Request):
    """
    Human-friendly short version. Accepts JSON or form.
    If pitch_url missing, README will be used as pitch automatically.
    """
    data = await get_score_payload(request)
    repo_url = data.get("repo_url")
    pitch_url = data.get("pitch_url")
    if not repo_url:
        raise HTTPException(422, detail="repo_url is required")
    out = await engine.ainvoke({"repo_url": repo_url, "pitch_url": pitch_url})
    final = out.get("final", {})
    # include light agent scores so you can see why the final is what it is
    return JSONResponse(
        content={
            "repo": repo_url,
            "final_score": final.get("final_score"),
            "verdict": final.get("verdict"),
            "feedback": final.get("feedback", []),
            "agents": {
                "code": (out.get("code") or {}).get("score"),
                "design": (out.get("design") or {}).get("score"),
                "pitch": (out.get("pitch") or {}).get("score"),
            },
        }
    )

@app.post("/score_profile")
async def score_profile(payload: ProfileRequest):
    """
    Aggregate multiple repos for a user/org and compute code-quality stats.
    """
    result = await score_profile_fn(
        handle=payload.handle,
        kind=payload.kind,
        max_repos=payload.max_repos,
        include_forks=payload.include_forks,
    )
    return JSONResponse(content=result)

@app.get("/debug/diag")
async def diag():
    """
    Quick diagnostics:
      - openai_key_present: bool
      - github: rate limit remaining (if token is set you'll see a higher value)
    """
    openai_ok = bool(os.getenv("OPENAI_API_KEY"))
    gh_status = {"ok": None, "remaining": None, "message": None}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://api.github.com/rate_limit", headers=_headers())
            gh_status["ok"] = (r.status_code == 200)
            if r.status_code == 200:
                j = r.json()
                gh_status["remaining"] = j.get("resources", {}).get("core", {}).get("remaining")
            else:
                gh_status["message"] = f"HTTP {r.status_code}"
    except Exception as e:
        gh_status["message"] = f"{type(e).__name__}: {e}"
    return {"openai_key_present": openai_ok, "github": gh_status}

@app.post("/debug/echo")
async def debug_echo(request: Request):
    """
    Echo back exactly what the browser/client sent.
    Helpful when you see 500/422 to confirm payload structure.
    """
    data = await get_score_payload(request)
    return {"headers": dict(request.headers), "data": data}
