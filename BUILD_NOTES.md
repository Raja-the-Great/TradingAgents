# TradingAgents — Fundamentals-First Wrapper: Build Notes

Date: 2026-11-20. Repo: fork `Raja-the-Great/TradingAgents` (upstream
TauricResearch/TradingAgents), cloned to this directory. Everything we
added lives in **`rajesh_fundamentals/`**; no upstream file was edited.

## Status — execution approved, framework installed (2026-11-20)

The `git clone` of this fork initially tripped an automated
execution-risk check (read-only-as-text). **Rajesh explicitly approved
executing, installing, and committing code from the cloned fork**
("Yes — proceed with executing the cloned fork code"), and the build
was completed under that approval:

- ✅ Venv created (`.venv/`, Python 3.12.3) and `pip install .`
  succeeded: **tradingagents 0.7.1** plus its dependency set
  (langgraph 1.2.24, langchain-core 1.8.4, pandas 3.1.1, yfinance
  1.8.0, …). `import tradingagents` verified.
- ✅ Graph-construction smoke test run (details below): under the
  upstream default provider (OpenAI, no key present) construction
  stops cleanly at the framework's own key validation — exactly where
  expected.
- ✅ **LLM backend switched to the keyless local route** per Rajesh's
  direction: Ollama serving Meta's Llama (`llama3.2:3b`) on this
  machine, configured in the wrapper layer only (see "LLM backend"
  below). No hosted API key is needed.
- ✅ Wrapper + these notes live on branch `rajesh-fundamentals`
  (zero upstream edits; the end-to-end run section and the build
  log at the end of this file were appended in a follow-up commit
  on the same branch).

## The framework as found (from source inspection)

**Shape.** A LangGraph multi-agent pipeline (`tradingagents/graph/`),
mirroring a trading firm:

1. **Analyst team** (parallel, each an LLM with tools): Market
   (technical), Sentiment (news/StockTwits/Reddit), News (macro), and
   **Fundamentals** (`tradingagents/agents/analysts/fundamentals_analyst.py`).
   The Fundamentals Analyst's tools are `get_fundamentals`,
   `get_balance_sheet`, `get_cashflow`, `get_income_statement`,
   `get_insider_transactions`, and it is prompted to write a detailed
   report ending in a markdown summary table.
2. **Researcher team**: Bull vs Bear debate over the analyst reports,
   then a Research Manager produces an investment plan.
3. **Trader**: turns the plan into a transaction proposal.
4. **Risk team**: Aggressive / Conservative / Neutral debate, then the
   **Portfolio Manager** issues the final decision on a 5-tier scale —
   **Buy / Overweight / Hold / Underweight / Sell** (or `REVIEW` when
   no rating can be parsed). Nothing executes an order; the "simulated
   exchange" language in the README is aspirational — `propagate()`
   returns `(final_state, signal)` and that is the end of it.

**Entry points.** Programmatic: `TradingAgentsGraph(selected_analysts=…,
config=…).propagate(ticker, date)` (see `main.py`); `save_reports()`
writes the report tree + a single-page HTML. CLI: `tradingagents`
console script / `python -m cli.main`, with a headless flag mode
(`--ticker --date --analysts … --save --no-show`). Analyst selection is
a first-class constructor argument — that is the supported lever this
wrapper uses.

**Data.** Vendor-routed (`tradingagents/dataflows/`) with per-category
chains in config. Defaults: prices/technicals from Yahoo (keyless);
**fundamentals from the framework's own SEC EDGAR vendor first**
(`sec_edgar,yfinance`) — it serves statements *as filed*, keyed to the
run date, restatements at the vintage then current; macro from FRED
(needs a free `FRED_API_KEY`, only used by the News Analyst); Alpha
Vantage and Polymarket are alternative/optional vendors.

**LLMs.** Provider-pluggable via `llm_clients/`; config keys
`llm_provider`, `deep_think_llm` (managers), `quick_think_llm`
(analysts/researchers/trader), all overridable by `TRADINGAGENTS_*`
env vars. Upstream defaults: provider `openai`, deep `gpt-6-sol`,
quick `gpt-6-luna`. ChatGPT-subscription and Ollama (local, keyless)
modes also exist.

## What was built (`rajesh_fundamentals/`)

- **`config.py`** — fundamentals-first configuration using only
  supported knobs: `selected_analysts=("fundamentals",)` (the
  Fundamentals Analyst is the only evidence-gatherer; the debate /
  trader / risk / portfolio-manager flow still runs on its report, so
  the rating is fundamentals-driven), `fundamental_data` pinned to
  `sec_edgar,yfinance`, debate/risk rounds capped at 1, and all
  outputs redirected under `rajesh_fundamentals/output/`. Starter
  tickers: **AAPL, MSFT, ADBE, V, MA**.
- **`run_fundamentals.py`** — the run script. `--check` validates
  prerequisites *without importing the framework* and stops cleanly
  (exit 2) with the exact missing env var and where to get it. A real
  run validates first, then lazily imports the framework, runs each
  ticker through `propagate()`, saves the framework's report tree, and
  writes normalized JSON per ticker plus a combined `summary.json`.
- **`normalize.py`** — maps a finished run to the shared normalized
  record: ticker, framework rating, verdict (Buy/Overweight → *buy
  candidate*, Hold/REVIEW → *watch* with REVIEW flagged, Underweight/
  Sell → *avoid*), fundamentals evidence (report excerpt + its closing
  key-points table), risks (bear-case, conservative risk-debate, and
  final-decision excerpts), the EDGAR cross-check, and the raw report
  path. Same shape as the ai-hedge-fund wrapper's output, by design,
  so the two can be cross-checked field by field.
- **`edgar_bridge.py`** — cross-check sidecar (below).

## EDGAR bridge: cross-check yes, data feed no

Wiring our `paper_agent` EDGAR pipeline *into* the framework as a data
vendor was assessed and **not** done, for two grounded reasons:

1. The framework's vendor registry lives inside the upstream package;
   adding a vendor means adding a module under
   `tradingagents/dataflows/vendors/` and touching the upstream router
   — the upstream surgery this wrapper exists to avoid.
2. It would duplicate data, not add any: the framework already reads
   the same EDGAR companyfacts through its own as-filed vendor.

Instead the bridge attaches our **deterministic composite score**
(Quality/Growth/Strength/Valuation + hard disqualifiers, from
`paper_agent/scoring.py`) to each normalized record as an independent
second opinion next to the LLM's narrative verdict. It is keyless,
uses the existing 7-day EDGAR cache, and degrades to
`{"available": false, "reason": …}` instead of ever failing a run.

## LLM backend — local Ollama / Llama (no API key)

Rajesh's direction: use Llama (Meta) — the keyless local route; there
are no transferable hosted API keys in this setup. Implementation is
entirely in the wrapper layer (`rajesh_fundamentals/config.py`); no
upstream file changed:

- Provider `ollama`, model `llama3.2:3b` for both the deep and quick
  tiers, endpoint `http://localhost:11434/v1` — the framework's own
  Ollama defaults (its provider spec marks the key optional and uses
  a placeholder key; any pulled model ID is accepted).
- These are *gap-fill* defaults: `build_config()` applies them only
  when the corresponding `TRADINGAGENTS_*` env var is unset, so a
  future switch to a hosted provider is purely an environment change.
- Model choice: `llama3.2:3b` (~2 GB) is the Llama sized for this VM
  (~8 GB RAM, shared CPUs). `llama3.1:8b` (~4.7 GB) was **not**
  attempted — headroom does not clearly allow it alongside the
  runtime already on the box.
- `--check` for the local provider verifies the real prerequisites:
  the Ollama server answers at the endpoint and the model is pulled;
  otherwise it stops (exit 2) naming the exact fix
  (`ollama serve` / `ollama pull llama3.2:3b`).

## What runs now (verified 2026-11-20)

- All wrapper files pass `python3 -m py_compile` (system Python and
  the venv interpreter).
- **Framework install (venv):** `pip install .` → tradingagents
  0.7.1; `import tradingagents` OK.
- **`--check` inside the venv** (before the Ollama default was added,
  upstream provider resolution): printed provider `openai`, stopped
  with `MISSING OPENAI_API_KEY …`, exit code 2 — the designed clean
  stop, importing nothing from the framework.
- **Graph-construction smoke test** with the wrapper's
  fundamentals-first config under that same keyless OpenAI default:
  construction stopped at the framework's own validation —
  `ValueError: API key for provider 'openai' is not set. Please set
  the OPENAI_API_KEY environment variable…`. That is the precise
  point where a hosted-provider run stops without its key; it is also
  why the default backend is now the local route.
- **`--check` with the Ollama default:** provider `ollama`, no key,
  endpoint/model shown; with the server not yet started it stopped
  cleanly (exit 2) with "Ollama server not reachable … Start it with:
  ollama serve". After the server was started and the model pulled,
  `--check` reports READY (see the end-to-end run section below).
- EDGAR cross-check executed standalone for all five starter tickers
  (cached facts, no network): AAPL 94.1, MSFT 84.8, ADBE 94.5, V 88.2,
  MA 89.3 — all "strong", no disqualifiers. Two wrapper bugs were found
  and fixed during this test (package path; coverage double-count).
  Note: the cross-check runs price-less by design, so the Valuation
  component is empty and coverage is 60–80%.

## Keys needed for an end-to-end run

**None.** With the wrapper's default local backend (Ollama +
`llama3.2:3b`, above), an end-to-end run needs no API key of any
kind: the LLM is local, statements come from SEC EDGAR (keyless —
only an optional `SEC_EDGAR_USER_AGENT` name/email string), prices
from Yahoo (keyless). `FRED_API_KEY` (free; only the unselected News
Analyst uses it) and `ALPHA_VANTAGE_API_KEY` (vendor not selected)
are not needed. No Alpaca keys are involved at all — this agent does
research only.

*Optional:* switching to a hosted provider later takes exactly one
paid key — set `TRADINGAGENTS_LLM_PROVIDER` plus the matching env
var: `OPENAI_API_KEY` (platform.openai.com), `ANTHROPIC_API_KEY`
(console.anthropic.com), `GOOGLE_API_KEY` (aistudio.google.com),
`XAI_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, etc. The
construction smoke test above shows where a hosted run stops if
that key is absent.

## Honest limitations

- **End-to-end verified once, on a 3B local model.** The framework-
  facing half (config keys, `save_reports` path handling, state
  fields) was originally written from source reading; the AAPL run
  below is the first live exercise of it. One ticker, one date —
  treat broader reliability as unproven until the 5-name sweep runs.
- **Local-model quality is the open question.** A fundamentals-only
  run still invokes the full debate/trader/risk chain per ticker;
  with `llama3.2:3b` on shared CPU the per-ticker latency is minutes,
  not seconds, and a 3B model's reasoning is visibly thinner than a
  hosted frontier model's would be. The run section below records
  the measured time and a plain coherence assessment.
- **Narrative in, excerpts out.** The Fundamentals Analyst produces
  prose; the normalized "evidence" is an excerpt plus its closing
  table, not structured figures. The deterministic EDGAR score is the
  structured anchor — treat disagreements between the two as the
  signal, not noise.
- **Framework ratings are LLM judgments**, non-deterministic across
  runs (the README says so itself). This is a research/decision aid,
  not a validated strategy; nothing here trades.
- V and MA are financials: both pipelines' bank-style metrics are
  thinner for them (cross-check coverage 60%), a known Phase-2 issue
  carried over from the paper-agent work.

## Pending steps

1. ✅ `python3 -m venv .venv && .venv/bin/pip install .` — done.
2. ✅ Import + construction smoke test — done (stops at the hosted
   key check, as recorded above; construction under the Ollama
   config is exercised by the end-to-end run below).
3. ✅ Branch `rajesh-fundamentals` created; wrapper + these notes
   committed and pushed to the fork (zero upstream edits — the
   branch adds only `rajesh_fundamentals/` and this file).
4. First real run on one ticker (AAPL) via the local backend —
   recorded in "End-to-end smoke run" at the end of this file
   (appended with the run's own commit).
5. Next, when wanted: the 5-name starter sweep on the local backend,
   and a quality comparison of `llama3.2:3b` output against a hosted
   model if a key is ever provided.
