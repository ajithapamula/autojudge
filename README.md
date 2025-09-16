🚀 Autonomous Hackathon Judge

Multi-Agent Hackathon Scoring System powered by FastAPI, LangChain, and Model Context Protocol (MCP).
Judges GitHub repos, README pitches, and design heuristics, then aggregates into final scores with actionable feedback.

📌 Features

Multi-Agent Architecture

Code Agent → static analysis (docs, tests, CI/CD, structure).

Design Agent → UX heuristics (README visuals, structure, accessibility).

Pitch Agent → LLM-based scoring of README / pitch deck.

Judge Agent → aggregates all agents with weights & prompts.

MCP Tooling

Connects to external MCP servers (@modelcontextprotocol/server-github, server-web) for GitHub + web context.

Async orchestration with LangChain Runnable Graph.

REST API Endpoints

POST /score → detailed agent + final scoring.

POST /score_summary → simplified verdict + feedback.

POST /score_profile → aggregate scores across multiple repos for a GitHub user/org.

GET /debug/diag → check GitHub rate limit + OpenAI key presence.

GET /health → health check.

Optional Frontend

React/Vite UI (served via FastAPI static mount at /static).

Visual dashboards for scores, verdicts, and repo profiles.

🏗 Architecture

               ┌───────────────────────┐
               │      Client / UI      │
               │ React / cURL / API    │
               └──────────┬────────────┘
                          │ REST
                   ┌───────▼────────┐
                   │    FastAPI     │
                   │  app/main.py   │
                   └───────┬────────┘
         ┌─────────────────┼─────────────────┐
         │                 │                 │
 ┌───────▼──────┐   ┌──────▼───────┐  ┌──────▼───────┐
 │ Code Agent   │   │ Design Agent │  │ Pitch Agent  │
 │ Heuristics   │   │ Heuristics   │  │ LLM via MCP  │
 └───────┬──────┘   └──────┬───────┘  └──────┬───────┘
         │                 │                 │
         └──────────┬──────┴───────┬────────┘
                    ▼              ▼
                ┌──────────────────────┐
                │   Judge Aggregator   │
                │  (Prompt + Weights)  │
                └─────────┬────────────┘
                          ▼
                   Final Score + Verdict

⚡️ Quickstart
1. Clone repo
git clone https://github.com/ajithapamula/autojudge.git
cd autojudge

2. Create venv & install deps

python -m venv venv
venv\Scripts\activate   # Windows
# or source venv/bin/activate (Linux/Mac)

pip install -r requirements.txt

3. Set environment variables

Create .env:

OPENAI_API_KEY=sk-xxxxx
GITHUB_TOKEN=ghp_xxxxx       # optional, for higher rate limits

4. Run server

uvicorn app.main:app --reload --port 8080

API docs → http://127.0.0.1:8080/docs

🔥 Example Usage
Health check
curl http://127.0.0.1:8080/health
# {"ok": true}

Score single repo
curl -X POST "http://127.0.0.1:8080/score" \
     -H "Content-Type: application/json" \
     -d '{"repo_url":"https://github.com/ajithapamula/Edu-App"}'

Aggregate user profile
curl -X POST "http://127.0.0.1:8080/score_profile" \
     -H "Content-Type: application/json" \
     -d '{"handle":"ajithapamula","kind":"user","max_repos":5}'

🧩 Project Structure

app/
 ├── agents/          # Code, Design, Pitch, Judge agents
 ├── utils/           # MCP tools, GitHub client
 ├── graph.py         # LangChain graph orchestration
 ├── main.py          # FastAPI entrypoint
 ├── profile.py       # Profile aggregation
 ├── prompt.py        # Judge prompt template
 └── frontend/        # (optional) React/Vite UI

🛠 Development

Run MCP servers locally
npx @modelcontextprotocol/server-github
npx @modelcontextprotocol/server-web

Debug MCP tools
curl http://127.0.0.1:8080/debug/mcp-tools

📊 Roadmap

 Improve Pitch agent retry logic

 Add CI workflow for scoring self-tests

 Frontend dashboard (charts + repo comparisons)

 Persistent scoring DB (Postgres/Redis)

 Multi-modal design judging (images/screenshots)

 📊 Roadmap

 Improve Pitch agent retry logic

 Add CI workflow for scoring self-tests

 Frontend dashboard (charts + repo comparisons)

 Persistent scoring DB (Postgres/Redis)

 Multi-modal design judging (images/screenshots)


 🧑‍💻 Contributing

Fork the repo & create a feature branch.

Ensure tests pass:

pytest


Submit PR with clear description.

