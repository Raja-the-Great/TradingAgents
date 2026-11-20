"""Fundamentals-first configuration for the TradingAgents fork.

How the emphasis is achieved, using only knobs the framework itself
supports (no upstream edits):

- ``TradingAgentsGraph(selected_analysts=("fundamentals",))`` — the graph
  constructor accepts an analyst selection; choosing only "fundamentals"
  means the Fundamentals Analyst is the sole evidence-gatherer. The
  bull/bear researcher debate, Trader, risk debate and Portfolio Manager
  still run downstream on that one report, so the final 5-tier rating is
  a fundamentals-driven decision rather than a blend with technical /
  sentiment / news reads.
- ``data_vendors["fundamental_data"] = "sec_edgar,yfinance"`` — the
  framework's own vendor chain for statements: SEC EDGAR *as filed*
  first (point-in-time, restatement-aware), Yahoo as fallback for
  anything EDGAR does not serve. This is also the framework default;
  it is pinned here explicitly so a future upstream default change
  cannot silently alter our data basis.
- All run outputs (results, cache, memory log) are redirected under
  ``rajesh_fundamentals/output/`` so wrapper runs never mix with
  upstream CLI runs in ``~/.tradingagents``.

The LLM provider and models are NOT hard-coded: the framework reads
``TRADINGAGENTS_LLM_PROVIDER`` / ``TRADINGAGENTS_DEEP_THINK_LLM`` /
``TRADINGAGENTS_QUICK_THINK_LLM`` from the environment. Upstream
defaults are provider "openai", deep "gpt-6-sol", quick "gpt-6-luna".

**Wrapper default backend (Rajesh's direction, 2026-11-20): the
keyless local route — Ollama serving Meta's Llama on this machine.**
There are no transferable hosted API keys in this setup, so when the
operator has not set the ``TRADINGAGENTS_*`` variables, this wrapper
fills them with: provider ``ollama``, deep and quick model
``llama3.2:3b`` (sized for this VM), endpoint
``http://localhost:11434/v1`` (the framework's own Ollama default).
Setting any ``TRADINGAGENTS_*`` variable overrides the corresponding
wrapper default, so switching to a hosted provider later is purely an
environment change.
"""
from __future__ import annotations

import os

# Starter set: strong-fundamentals names chosen by Rajesh's brief.
STARTER_TICKERS: tuple[str, ...] = ("AAPL", "MSFT", "ADBE", "V", "MA")

# The fundamentals-first analyst selection (see module docstring).
SELECTED_ANALYSTS: tuple[str, ...] = ("fundamentals",)

# Local LLM backend defaults (see module docstring). llama3.2:3b is
# the largest Llama that fits this VM's memory with headroom; the
# endpoint is the framework's own Ollama default base URL.
LOCAL_PROVIDER = "ollama"
LOCAL_MODEL = "llama3.2:3b"
LOCAL_BACKEND_URL = "http://localhost:11434/v1"

_HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_HERE, "output")


def build_config() -> dict:
    """Return a full framework config dict with our overrides applied.

    The upstream import happens here, lazily, so that merely importing
    this module (e.g. for prerequisite checks) never pulls in — let
    alone executes — framework code.
    """
    from tradingagents.default_config import DEFAULT_CONFIG

    config = DEFAULT_CONFIG.copy()
    config["results_dir"] = os.path.join(OUTPUT_DIR, "results")
    config["data_cache_dir"] = os.path.join(OUTPUT_DIR, "cache")
    config["memory_log_path"] = os.path.join(OUTPUT_DIR, "memory", "trading_memory.md")
    config["data_vendors"] = dict(config["data_vendors"])
    config["data_vendors"]["fundamental_data"] = "sec_edgar,yfinance"
    config["data_vendors"]["core_stock_apis"] = "yfinance"
    # One round each keeps a 5-ticker sweep's token cost bounded; the
    # debate still happens, it just does not loop.
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["checkpoint_enabled"] = False
    config["output_language"] = "English"
    # LLM backend: local Ollama/Llama by default (see module docstring).
    # DEFAULT_CONFIG has already folded in any TRADINGAGENTS_* env vars
    # the operator set, so only fill the gaps they left.
    if not os.environ.get("TRADINGAGENTS_LLM_PROVIDER"):
        config["llm_provider"] = LOCAL_PROVIDER
    if not os.environ.get("TRADINGAGENTS_DEEP_THINK_LLM"):
        config["deep_think_llm"] = LOCAL_MODEL
    if not os.environ.get("TRADINGAGENTS_QUICK_THINK_LLM"):
        config["quick_think_llm"] = LOCAL_MODEL
    if not os.environ.get("TRADINGAGENTS_LLM_BACKEND_URL"):
        config["backend_url"] = LOCAL_BACKEND_URL
    return config


def chosen_provider() -> str:
    """The LLM provider a run would use: TRADINGAGENTS_LLM_PROVIDER env
    var, else this wrapper's local default (Ollama — see docstring)."""
    return os.environ.get("TRADINGAGENTS_LLM_PROVIDER", "").strip() or LOCAL_PROVIDER
