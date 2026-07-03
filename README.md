# Tenant Communication Platform

An intelligent **Florida landlord assistant** built as a Kaggle capstone demo. A landlord
uploads a lease (or addendum), asks about a tenant situation, and the system returns lease
findings, Florida landlord–tenant law considerations, a risk analysis, deadline
calculations, recommended next steps, and a ready-to-edit tenant message.

> ⚠️ **This is not legal advice. Verify with a Florida attorney or local court before taking
> legal action.** This is an educational demo using simplified summaries of Florida law.

---

## Project purpose

Landlords face recurring, time-sensitive situations — unpaid rent, notices, utilities,
lease breaks, abandonment, maintenance access, unauthorized occupants. This MVP combines
five capabilities into one assistant:

1. **Uploaded lease retrieval** — find the relevant clauses in *this* lease.
2. **Florida landlord-tenant law lookup** — Chapter 83, Part II, via a local MCP server.
3. **Risk analysis** — compare the lease against the law and surface risks.
4. **Deadline / timeline calculation** — deterministic notice-deadline math.
5. **Tenant communication drafting** — a landlord-to-tenant message in a chosen tone.

Priorities: a **runnable MVP** and **demo quality** over production complexity.

---

## Architecture

Built on **Google ADK 2.0** with a graph **`Workflow`**, a **Gemini** model (Vertex AI),
one **MCP server** for Florida law, exactly **one explicit tool** for deadline math, and a
**Streamlit** UI.

```
                         ┌─────────────────────── Streamlit UI (app.py) ───────────────────────┐
                         │  upload lease (in-memory)  ·  scenario  ·  tone  ·  Analyze          │
                         └───────────────────────────────┬─────────────────────────────────────┘
                                                          │  run_workflow(lease_text, question, tone)
                                                          ▼
   ADK 2.0 graph Workflow (app/workflow.py, app/nodes.py)
   START ─► intake ─► lease_retrieval ─► florida_law ─► risk_analysis ─► timeline ─► message_draft ─► final_response
             (fn)        (fn)            (LLM+MCP)         (LLM)          (LLM+tool)      (LLM)           (fn)
                          │                  │                                 │                            │
                   keyword search      MCP stdio server            timeline_calculator          assemble 7 sections
                   over lease chunks    (mcp_server/)               (THE one tool)               + append disclaimer
```

- **Function nodes** (`intake`, `lease_retrieval`, `final_response`) are plain Python —
  breakpoints work, behavior is deterministic.
- **LLM nodes** (`florida_law`, `risk_analysis`, `timeline`, `message_draft`) are ADK
  `LlmAgent`s wired directly into the graph. Data flows between nodes through session state.
- The **disclaimer** and **lease-vs-law separation** are enforced in code, not left to the
  model, so they are guaranteed and testable.

### The ADK graph workflow

Defined in [`app/workflow.py`](app/workflow.py) and [`app/nodes.py`](app/nodes.py):

| Node | Type | Role |
|------|------|------|
| `intake` | function | Normalize question/tone; chunk the lease once. |
| `lease_retrieval` | function | Keyword/TF-IDF search over lease chunks → cited clauses. |
| `florida_law` | LlmAgent + MCP | Look up Florida statutes via the MCP server. |
| `risk_analysis` | LlmAgent (structured) | Compare lease vs law; list risks + next steps. |
| `timeline` | LlmAgent + tool | Call `timeline_calculator` when a deadline applies. |
| `message_draft` | LlmAgent (structured) | Draft the landlord-to-tenant message. |
| `final_response` | function | Assemble the seven sections; append the disclaimer. |

### Why only one tool?

Deadline calculation is the single capability that genuinely benefits from **deterministic
computation** — off-by-one date errors have legal consequences. So `timeline_calculator`
([`app/tools.py`](app/tools.py)) is the **only** explicit ADK tool. Everything else is
handled by graph orchestration, MCP context, and LLM reasoning:

- **Lease retrieval** is graph reasoning (a function node), not a tool.
- **Legal lookup** is MCP context (the `lookup_florida_law` MCP tool is provided by the
  server, not registered as a project tool).
- **Risk analysis** and **message drafting** are LLM generation.

This keeps the tool surface minimal and the reasoning legible.

### MCP usage

[`mcp_server/`](mcp_server/) is a local **Model Context Protocol** server (stdio):

- [`mcp_server/data/florida_landlord_tenant.md`](mcp_server/data/florida_landlord_tenant.md)
  — a curated, human-editable knowledge base of Fla. Stat. Ch. 83 Part II summaries.
- [`mcp_server/florida_law.py`](mcp_server/florida_law.py) — a **pure, importable**
  `lookup()` that parses and ranks the KB. Directly unit-testable and debuggable.
- [`mcp_server/server.py`](mcp_server/server.py) — a thin `FastMCP` wrapper exposing the
  `lookup_florida_law` tool over stdio.

The `florida_law` node connects to it via ADK's `McpToolset` + `StdioConnectionParams`
(launch command computed in [`app/config.py`](app/config.py)).

---

## Setup

Requirements: Python 3.11+, Google Cloud credentials (ADC) for Vertex AI.

```bash
# 1. Configure environment (Vertex AI via ADC by default)
cp .env.example .env        # then edit if needed (project is preset)
gcloud auth application-default login    # if you haven't already

# 2. Install dependencies — either path works:
pip install -r requirements.txt          # plain pip
#   or (recommended):
uv sync                                  # uv
```

`.env` (already pointed at the demo project):

```
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=sanguine-method-458311-b0
GOOGLE_CLOUD_LOCATION=global
```

To use Google AI Studio instead of Vertex, comment those out and set `GEMINI_API_KEY`.

---

## Run commands

```bash
pip install -r requirements.txt     # install
pytest                              # fast, offline tests
python evals/run_evals.py           # lightweight evals (calls the real model)
streamlit run app.py                # the UI
```

With `uv`, prefix Python commands with `uv run` (e.g. `uv run pytest`,
`uv run streamlit run app.py`). A single non-UI run for quick checks:

```bash
uv run python scripts/run_workflow.py \
  --question "The tenant did not pay rent. When does a 3-day notice expire?" --tone firm
```

---

## How to run tests

```bash
pytest                       # or: uv run pytest
pytest tests/unit            # unit tests only
pytest tests/integration     # offline end-to-end (stubbed model)
```

- **Unit tests** cover document loading/extraction/chunking, retrieval ranking, the
  timeline calculator (date math), the Florida-law lookup, and section assembly.
- **Integration tests** run the **real ADK graph engine** with the four LLM nodes replaced
  by deterministic stubs — proving graph wiring, state flow, and assembly for the three
  required scenarios, fully offline.
- Following ADK guidance, pytest **never asserts on LLM-generated prose** (that's
  non-deterministic). Response quality is validated by the eval layer instead.
- A **live** server test exists but is skipped by default. Enable it with
  `RUN_SERVER_E2E=1 uv run pytest tests/integration/test_server_e2e.py`.

## How to run evals

Two complementary layers:

```bash
# 1. Custom lightweight runner (heuristic scoring, transparent) — calls the real model:
python evals/run_evals.py
python evals/run_evals.py --only did_not_pay_rent lock_change_after_notice

# 2. Native agents-cli eval (LLM-as-judge):
agents-cli eval run
```

The custom runner scores each scenario on seven criteria: cites lease, separates law vs
lease, includes the disclaimer, avoids pretending to be a lawyer, provides next steps,
generates a tenant message, and includes a deadline when a timeline applies (see
[`evals/fixtures/expected_signals.md`](evals/fixtures/expected_signals.md)).

---

## Debugging in VS Code

Open the **`tenant-comms-platform`** folder in VS Code and select the `.venv` interpreter.
[`.vscode/launch.json`](.vscode/launch.json) provides four configurations:

| Configuration | What it does |
|---------------|--------------|
| **Streamlit App Debug** | Runs `streamlit run app.py` with the debugger attached. |
| **Graph Workflow Debug (single run)** | Runs `scripts/run_workflow.py` once. |
| **Pytest Debug (unit + integration)** | Debugs the test suite. |
| **Eval Debug (run_evals.py)** | Debugs the lightweight eval runner. |

**Where breakpoints work:**

- ✅ Agent graph **function nodes** — `app/nodes.py` (`intake`, `lease_retrieval`,
  `final_response`).
- ✅ **Retrieval logic** — `app/retrieval.py`, and chunking in `app/documents.py`.
- ✅ **The timeline tool** — `app/tools.py`.
- ✅ **MCP handler logic** — set breakpoints in `mcp_server/florida_law.py` and run/debug it
  directly (or via its unit tests). Because the pure `lookup()` is importable, you don't
  need the MCP transport to debug the retrieval logic.
- ⚠️ **Caveat:** the MCP *server process* (`mcp_server/server.py`) is launched by ADK as a
  **separate stdio subprocess**, so breakpoints inside it won't be hit by the app/Streamlit
  debugger. Debug the law logic through `florida_law.py` directly instead.

Entry points are explicit (`app.py`, `scripts/run_workflow.py`, `evals/run_evals.py`) and
`.env` drives configuration — no dynamic magic to obscure the call path.

---

## Demo scenarios

Use the sample lease ([`fixtures/sample_lease.txt`](fixtures/sample_lease.txt)) and try:

1. Tenant moved out without notice and still owes utilities.
2. Tenant wants to break the lease early.
3. Tenant did not pay rent.
4. Tenant refuses maintenance access.
5. Does an unpaid utility count as additional rent?
6. Can I change the locks after a 3-day notice?

Scenarios 3 and 6 exercise the `timeline_calculator` tool; scenario 5 exercises the
"utilities as additional rent" nuance.

---

## Assumptions

- **Florida only.** The law KB covers Fla. Stat. Ch. 83 Part II and a few related statutes.
- **Vertex AI + ADC** with `gemini-flash-latest` on the `global` endpoint (the scaffold
  default; verified working). Switchable to AI Studio via `GEMINI_API_KEY`.
- **In-memory only.** Uploaded leases are parsed from a memory buffer and never written to
  disk; sessions are in-memory and cleared on restart.
- **Simplified legal timing.** The timeline tool models common notice periods and a small
  set of Florida legal holidays; it deliberately does **not** compute court/eviction dates.
- Lease retrieval uses lightweight keyword/TF-IDF ranking (no embeddings/vector DB), which
  is sufficient at demo scale.

## Limitations

- The law summaries are **educational paraphrases**, not statutory text, and may lag
  legislative changes (e.g., the 2023 month-to-month notice change from 15 → 30 days is
  flagged as a warning, not silently applied).
- LLM output can still err; the app enforces structure and the disclaimer in code, but the
  substance should always be verified with a Florida attorney.
- No authentication, persistence, deployment, or multi-user support (prototype scope). Add
  deployment later with `agents-cli scaffold enhance . --deployment-target <target>`.
- The holiday list is not exhaustive (no county-specific or weekend-observance handling).

---

## Project layout

```
tenant-comms-platform/
├── app.py                     # Streamlit UI (streamlit run app.py)
├── app/                       # ADK agent package (App(name="app"))
│   ├── agent.py               # exports root_agent (the Workflow) + app
│   ├── workflow.py            # graph definition + run_workflow entrypoint
│   ├── nodes.py               # the 7 graph nodes
│   ├── tools.py               # timeline_calculator (the ONE explicit tool)
│   ├── retrieval.py           # lease clause search (graph reasoning)
│   ├── documents.py           # PDF/DOCX/TXT extraction + chunking
│   ├── schemas.py             # Pydantic I/O + AnalysisResult (7 sections)
│   └── config.py              # model, MCP launch, tones, disclaimer
├── mcp_server/                # Florida-law MCP server (stdio)
│   ├── florida_law.py         # pure importable lookup()
│   ├── server.py              # FastMCP stdio wrapper
│   └── data/florida_landlord_tenant.md
├── scripts/run_workflow.py    # single-run CLI / debug entrypoint
├── evals/                     # custom lightweight eval layer
│   ├── run_evals.py
│   ├── scenarios.py
│   └── fixtures/expected_signals.md
├── tests/
│   ├── conftest.py            # offline stub-graph harness
│   ├── unit/                  # documents, retrieval, timeline, law, schemas, graph
│   ├── integration/           # offline e2e (+ gated live server test)
│   └── eval/                  # native agents-cli eval (LLM-as-judge)
├── fixtures/                  # sample_lease.txt, sample_scenarios.md
├── .vscode/                   # launch.json (4 configs) + settings.json
├── requirements.txt           # pip path (mirrors pyproject.toml)
└── .env.example
```
