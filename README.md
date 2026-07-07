# 🏠 Tenant Communication Platform

**An AI agent that helps Florida landlords handle tenant situations without accidentally breaking the law.**

Upload a lease, describe what's happening ("the tenant moved out early and still owes utilities"), and in one pass the agent reads *your* lease, looks up the relevant Florida statutes, weighs the legal risk, calculates any deadlines, and even drafts the message you'd send the tenant — with a legal disclaimer baked in.

> ⚠️ **This is not legal advice.** It's an educational demo using simplified summaries of Florida law. Always verify with a Florida attorney or local court before acting.

🔗 **Live demo:** [tenantcomm.streamlit.app](https://tenantcomm.streamlit.app/)  ·  🎥 **Video:** _<YouTube link>_  ·  💻 **Code:** [github.com/dynamasoft/tenant-comms-platform](https://github.com/dynamasoft/tenant-comms-platform)

---

## The problem

A Florida landlord has a tenant who stopped paying rent. They want to act — post a notice, maybe change the locks, maybe shut off the water until they pay.

Here's the trap: in Florida, **a wrong move isn't just a mistake, it's a liability.**

- Put the *wrong amount* on a 3-day notice (say, you tack on late fees or utilities) and a court can throw out your entire eviction — you start over, weeks lost.
- Change the locks or cut the utilities to force a tenant out — a "self-help" eviction — and under **Fla. Stat. § 83.67** you can owe the tenant **three months' rent plus their attorney's fees.**

Landlords aren't lawyers. Hiring one for every routine question is slow and expensive. So they **guess** — and guessing is exactly where costly errors happen. The knowledge to avoid these mistakes exists in the statutes and in the lease itself; it's just scattered, dense, and easy to get wrong under time pressure.

## The solution

One assistant that does what a careful paralegal would — instantly, and grounded in real sources:

| # | Section it returns | What it does for the landlord |
|---|--------------------|-------------------------------|
| 1 | **Lease findings** | Pulls the exact clauses from *this* lease that apply, quoted and cited. |
| 2 | **Florida law considerations** | Looks up the on-point statutes (Ch. 83) — not the model's memory. |
| 3 | **Risk analysis** | Compares lease vs. law and flags where acting is dangerous. |
| 4 | **Timeline / deadlines** | Does the notice-deadline math, exactly (dates have legal consequences). |
| 5 | **Recommended next steps** | Conservative, lawful actions — never self-help. |
| 6 | **Draft tenant message** | A ready-to-edit message in the tone you choose. |
| 7 | **Disclaimer** | Always appended, in code, so it can never be dropped. |

## Why an *agent*, not a chatbot?

Because this is genuinely a **multi-step job, and each step needs a different capability**:

- *retrieving* the right clauses from a specific document,
- *looking up* factual law from an authoritative source,
- *reasoning* about how the two interact,
- doing *exact arithmetic* on dates, and
- *writing* a human message.

A single prompt can't reliably do all five — it'll hallucinate a statute, or fumble a date, or forget the disclaimer. So the system is built as a **graph of specialized agents and tools**, each responsible for one thing, passing results down an assembly line. That's the whole thesis: **decompose a risky task into small, verifiable steps.**

---

## How it works

Built on **Google ADK 2.0** — a graph `Workflow` orchestrating a **Gemini** model, a **Model Context Protocol (MCP)** server for Florida law, exactly **one** deterministic tool for date math, and a **Streamlit** UI.

```
                    ┌───────────────── Streamlit UI (app.py) ─────────────────┐
                    │  upload lease (in-memory) · scenario · tone · Analyze    │
                    └───────────────────────────┬─────────────────────────────┘
                                                 │ run_workflow(lease_text, question, tone)
                                                 ▼
  ADK 2.0 graph Workflow  (app/workflow.py, app/nodes.py)
  START ─► intake ─► lease_retrieval ─► florida_law ─► risk_analysis ─► timeline ─► message_draft ─► final_response
            (fn)        (fn)             (LLM+MCP)        (LLM)          (LLM+tool)      (LLM)           (fn)
                         │                  │                              │                             │
                  keyword search      MCP stdio server           timeline_calculator          assemble 7 sections
                  over lease chunks    (mcp_server/)              (THE one tool)               + append disclaimer
```

Think of it as an **assembly line**: each node adds one finished piece to a shared "clipboard" (session state), and the last node bundles everything into the answer.

| Node | Type | Role |
|------|------|------|
| `intake` | function | Normalize question/tone; chunk the lease once. |
| `lease_retrieval` | function | Keyword/TF-IDF search over lease chunks → cited clauses. |
| `florida_law` | **LLM + MCP** | Look up Florida statutes via the MCP server. |
| `risk_analysis` | LLM (structured) | Compare lease vs. law; list risks + next steps. |
| `timeline` | **LLM + tool** | Call `timeline_calculator` when a deadline applies. |
| `message_draft` | LLM (structured) | Draft the landlord-to-tenant message. |
| `final_response` | function | Assemble the seven sections; append the disclaimer. |

---

## Design decisions worth explaining

These are the "why we built it this way" choices — the interesting part.

**1. Grounded law, not hallucinated law (MCP).**
The `florida_law` node doesn't recite statutes from the model's memory. It calls a **local MCP server** ([`mcp_server/`](mcp_server/)) that searches a curated knowledge base of Fla. Stat. Ch. 83, Part II, and returns real citations. The model summarizes *only what the tool returned* — so legal claims are traceable to a source, not invented.

**2. Exactly one deterministic tool — on purpose.**
Deadline math is the one capability where a wrong answer is unacceptable and an LLM shouldn't be trusted: an off-by-one on a 3-day notice has legal consequences. So `timeline_calculator` ([`app/tools.py`](app/tools.py)) is the **only** explicit tool — plain, testable Python that skips weekends and Florida holidays. Everything else is graph orchestration, MCP context, or reasoning. Minimal tool surface, maximum legibility.

**3. Safety enforced in code, not left to the model.**
The **disclaimer** and the **lease-vs-law separation** are guaranteed by the `final_response` function node, not by asking the model nicely. That makes them deterministic and unit-testable — the model literally cannot forget the disclaimer.

**4. Deliberately simple retrieval.**
Lease clauses are found with lightweight **keyword/TF-IDF** ranking, not embeddings or a vector DB. At demo scale (one lease, shared vocabulary between question and clause) it's plenty — and it stays **deterministic, offline, and unit-testable**, which matters for reproducible evals. The clean upgrade path (swap in embeddings + a vector index) is noted below.

**Course concepts demonstrated:** multi-agent system (ADK graph) · MCP server · Agents CLI (eval/playground) · deployability (live on Streamlit Cloud) · security/privacy (in-memory-only document handling).

---

## Quickstart

Requirements: **Python 3.11+** and a free **Gemini API key** from [Google AI Studio](https://aistudio.google.com/apikey).

```bash
# 1. Get the code
git clone https://github.com/dynamasoft/tenant-comms-platform.git
cd tenant-comms-platform

# 2. Configure your key
cp .env.example .env
#   then edit .env and set:  GEMINI_API_KEY=your-key-here

# 3. Install (either path works)
pip install -r requirements.txt      # plain pip
#   or, recommended:
uv sync                              # uv

# 4. Run the app
streamlit run app.py                 # or: uv run streamlit run app.py
```

Then upload [`fixtures/sample_lease.txt`](fixtures/sample_lease.txt), ask a question, and click **Analyze**.

> **Model access — two doors, same Gemini.** By default this uses the **Gemini API key** (Google AI Studio) — the simplest path, no cloud setup. To use **Vertex AI** instead (for Google Cloud deployment), comment out `GEMINI_API_KEY` in `.env` and set `GOOGLE_GENAI_USE_VERTEXAI=true` + your project. The agent code is identical either way.

### Deployment

The app is deployed on **Streamlit Community Cloud** — the whole bundle (UI + agent graph + MCP server) runs in one container, calling Gemini via the API key. To reproduce: push to a public GitHub repo, connect it at [share.streamlit.io](https://share.streamlit.io), set `app.py` as the entry point, and add `GEMINI_API_KEY` as a secret.

---

## Testing & evaluation

Correctness is verified at **three levels** — deterministic tests for the plumbing, and two eval
layers for the parts a language model actually generates.

```bash
pytest                       # fast, offline tests (or: uv run pytest)
pytest tests/unit            # unit tests only
pytest tests/integration     # offline end-to-end (stubbed model)
python evals/run_evals.py    # lightweight heuristic evals (calls the real model)
```

- **Unit tests** cover document extraction/chunking, retrieval ranking, the timeline date-math, the Florida-law lookup, and section assembly.
- **Integration tests** run the **real ADK graph engine** with the four LLM nodes replaced by **deterministic stubs** — proving graph wiring, state flow, and assembly for the required scenarios, fully offline and with no API cost.
- Following ADK guidance, tests **never assert on LLM-generated prose** (it's non-deterministic); response quality is checked by the eval layer instead.
- A **live** server test exists but is gated: `RUN_SERVER_E2E=1 pytest tests/integration/test_server_e2e.py`.

### Two eval layers

**1. Lightweight heuristic evals** ([`evals/`](evals/)) — `python evals/run_evals.py` runs the real
workflow on the six demo scenarios and scores each assembled answer on **seven safety/structure
signals**: cites the lease, separates law from lease, includes the disclaimer, never pretends to be
a lawyer, gives next steps, drafts a message, and includes a deadline when one applies (see
[`evals/fixtures/expected_signals.md`](evals/fixtures/expected_signals.md)). Fast, deterministic,
and cheap — a guardrail that the required *behaviors* are present on every run.

**2. Native `agents-cli` eval (LLM-as-judge)** — the quality flywheel from the Agents CLI:

```bash
agents-cli eval generate    # run the agent over the eval dataset → traces (artifacts/traces/)
agents-cli eval grade       # grade those traces with the LLM-as-judge → results (artifacts/grade_results/)
agents-cli eval analyze     # (optional) cluster failure modes across results
```

- The judge is a **real, lintable/testable custom metric** ([`tests/eval/metrics.py`](tests/eval/metrics.py)),
  not an inline prompt blob. It scores each final response **1–5** for accuracy, relevance, and
  clarity, grading against each case's ground-truth `reference` and returning **schema-valid JSON**
  (Pydantic `response_schema`, `temperature=0` for deterministic grading).
- It's wired in via [`tests/eval/eval_config.yaml`](tests/eval/eval_config.yaml) and runs on **both**
  Vertex AI (ADC) and Google AI Studio (`GEMINI_API_KEY`) — `genai.Client()` auto-selects the backend.
- The eval dataset lives in [`tests/eval/datasets/`](tests/eval/datasets/); traces and graded results
  are written under [`artifacts/`](artifacts/).

**Result:** on the sampled scenarios the LLM-as-judge scored **5/5** — praising the correct
§ 83.56(3) citation, the weekend/holiday-aware deadline math, the self-help-eviction warning, and the
honest statement of uncertainty.

---

## Debugging in VS Code

Open the folder, select the `.venv` interpreter. [`.vscode/launch.json`](.vscode/launch.json) provides ready-to-run debug configs (Streamlit, single graph run, playground, the MCP law-lookup, pytest, evals).

- ✅ **Function nodes** (`intake`, `lease_retrieval`, `final_response`), **retrieval** (`app/retrieval.py`), **chunking** (`app/documents.py`), and the **timeline tool** (`app/tools.py`) — breakpoints work directly.
- ✅ **LLM nodes** are ADK-managed, so to inspect them the `florida_law` node has **debug callbacks** (`before_agent` / `after_tool` / `after_model`) — plain Python where breakpoints *do* fire, letting you see the exact prompt, the tool result, and the generated text during a real run.
- ⚠️ The MCP **server process** runs as a separate stdio subprocess, so debug its logic through the importable `lookup()` in [`mcp_server/florida_law.py`](mcp_server/florida_law.py) (or the "Debug Florida-Law Lookup" config) rather than across the transport.

---

## Demo scenarios

Using [`fixtures/sample_lease.txt`](fixtures/sample_lease.txt):

1. Tenant moved out without notice and still owes utilities.
2. Tenant wants to break the lease early.
3. Tenant did not pay rent. *(exercises the deadline tool)*
4. Tenant refuses maintenance access.
5. Does an unpaid utility count as additional rent? *(the "additional rent" nuance)*
6. Can I change the locks after a 3-day notice? *(exercises the deadline tool + self-help warning)*

---

## Assumptions & limitations

- **Florida only.** The knowledge base covers Fla. Stat. Ch. 83, Part II, and a few related statutes.
- **In-memory only.** Uploaded leases are parsed from a memory buffer and **never written to disk**; sessions clear on restart. (This is a deliberate privacy/security choice.)
- **Simplified legal timing.** The timeline tool models common notice periods and a small set of Florida holidays; it deliberately does **not** compute court/eviction dates.
- **Educational summaries.** The law entries are paraphrases, not statutory text, and may lag legislative changes (e.g., the 2023 month-to-month notice change from 15 → 30 days is flagged as a warning rather than silently applied).
- LLM output can still err — structure and the disclaimer are enforced in code, but the substance should always be verified with a Florida attorney.
- Prototype scope: no authentication, persistence, or multi-user support. Retrieval is keyword-based (no embeddings/vector DB); the clean upgrade path is to swap `search_clauses` for an embedding index without touching the graph.

---

## Project layout

```
tenant-comms-platform/
├── app.py                     # Streamlit UI (streamlit run app.py)
├── app/                       # ADK agent package (App(name="app"))
│   ├── agent.py               # exports root_agent (the Workflow) + app
│   ├── workflow.py            # graph definition + run_workflow entrypoint
│   ├── nodes.py               # the 7 graph nodes (+ debug callbacks)
│   ├── tools.py               # timeline_calculator (the ONE explicit tool)
│   ├── retrieval.py           # lease clause search (graph reasoning)
│   ├── documents.py           # PDF/DOCX/TXT extraction + chunking
│   ├── schemas.py             # Pydantic I/O + AnalysisResult (7 sections)
│   └── config.py              # model, MCP launch, tones, disclaimer
├── mcp_server/                # Florida-law MCP server (stdio)
│   ├── florida_law.py         # pure importable lookup()
│   ├── server.py              # FastMCP stdio wrapper
│   └── data/florida_landlord_tenant.md
├── scripts/                   # run_workflow.py, debug_law_lookup.py
├── evals/                     # custom lightweight eval layer
├── tests/                     # unit, integration (offline + gated live), eval
├── fixtures/                  # sample_lease.txt, sample_scenarios.md
├── .vscode/                   # launch.json + settings.json
├── requirements.txt           # pip path (mirrors pyproject.toml)
└── .env.example
```
