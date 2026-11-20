"""Run the fundamentals-first TradingAgents sweep.

Usage:
    python -m rajesh_fundamentals.run_fundamentals --check
    python -m rajesh_fundamentals.run_fundamentals [--tickers AAPL,MSFT]
                                                   [--date 2026-11-20]
                                                   [--no-edgar]

``--check`` validates prerequisites and exits WITHOUT importing the
framework: exit 0 when everything needed is present, exit 2 with a
precise list of what is missing. A real run validates first too, so a
missing key produces this same clean stop instead of a stack trace
from deep inside LangGraph.

What a run needs (fundamentals-only configuration):
- An LLM backend. This wrapper's default is the keyless local route:
  Ollama serving Meta's Llama (llama3.2:3b) on this machine — no API
  key at all, but the Ollama server must be running and the model
  pulled (``--check`` verifies both). If TRADINGAGENTS_LLM_PROVIDER
  is set to a hosted provider instead, that provider's API key is
  required (e.g. openai -> OPENAI_API_KEY). Either way, no data key
  is required: statements come from SEC EDGAR (keyless) with Yahoo
  (keyless) as fallback.
- Optional, NOT required for this configuration:
  * SEC_EDGAR_USER_AGENT — not a key; a name+email SEC asks callers to
    send. The framework has a working default.
  * FRED_API_KEY — only used by the News Analyst's macro tools, which
    this configuration does not select.
  * ALPHA_VANTAGE_API_KEY — only if the data vendor is switched to
    Alpha Vantage; this configuration does not use it.

Research only: this script runs an analysis graph and writes reports.
It places no orders and talks to no broker.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rajesh_fundamentals import config as cfg  # noqa: E402

# Mirrors tradingagents/llm_clients/api_key_env.py (the framework's own
# provider -> env-var mapping), duplicated here so the prerequisite
# check never has to import the framework.
PROVIDER_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "xai": "XAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "qwen-cn": "DASHSCOPE_CN_API_KEY",
    "glm": "ZHIPU_API_KEY",
    "glm-cn": "ZHIPU_CN_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "minimax-cn": "MINIMAX_CN_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "kimi": "MOONSHOT_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
    "groq": "GROQ_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
    "azure": "AZURE_OPENAI_API_KEY",
    "ollama": None,  # local models: no key
}

KEY_SOURCES = {
    "OPENAI_API_KEY": "OpenAI — platform.openai.com -> API keys (paid API account)",
    "ANTHROPIC_API_KEY": "Anthropic — console.anthropic.com -> API keys",
    "GOOGLE_API_KEY": "Google — aistudio.google.com -> Get API key",
    "XAI_API_KEY": "xAI — console.x.ai -> API keys",
    "DEEPSEEK_API_KEY": "DeepSeek — platform.deepseek.com -> API keys",
    "OPENROUTER_API_KEY": "OpenRouter — openrouter.ai -> Keys",
}


def _check_ollama() -> list[str]:
    """For the local provider, 'ready' means the Ollama server answers
    and the configured model is pulled. Uses only the stdlib HTTP
    client against Ollama's native API — no framework import."""
    import urllib.error
    import urllib.request

    backend = (os.environ.get("TRADINGAGENTS_LLM_BACKEND_URL", "").strip()
               or cfg.LOCAL_BACKEND_URL)
    native = backend[:-3] if backend.endswith("/v1") else backend
    model = (os.environ.get("TRADINGAGENTS_QUICK_THINK_LLM", "").strip()
             or cfg.LOCAL_MODEL)
    try:
        with urllib.request.urlopen(native + "/api/tags", timeout=3) as resp:
            names = [m.get("name", "") for m in json.load(resp).get("models", [])]
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return [f"Ollama server not reachable at {native} ({exc}). "
                "Start it with: ollama serve"]
    if model not in names:
        return [f"Ollama model {model!r} is not pulled (server has: "
                f"{', '.join(names) or 'none'}). Pull it with: "
                f"ollama pull {model}"]
    return []


def validate_prerequisites() -> list[str]:
    """Return a list of human-readable problems; empty means ready."""
    problems = []
    provider = cfg.chosen_provider()
    if provider == "ollama":
        problems.extend(_check_ollama())
        return problems
    if provider == "chatgpt":
        problems.append(
            "Provider 'chatgpt' (ChatGPT subscription) needs an interactive "
            "browser sign-in (`tradingagents login chatgpt`); this script "
            "cannot do it unattended. Set TRADINGAGENTS_LLM_PROVIDER to an "
            "API-key provider instead.")
        return problems
    key_env = PROVIDER_KEY_ENV.get(provider)
    if key_env is None and provider != "ollama":
        problems.append(
            f"Unknown LLM provider {provider!r} (from "
            "TRADINGAGENTS_LLM_PROVIDER). Known providers: "
            + ", ".join(sorted(PROVIDER_KEY_ENV)))
    elif key_env and not os.environ.get(key_env, "").strip():
        source = KEY_SOURCES.get(key_env, "the provider's developer console")
        problems.append(
            f"MISSING {key_env} — the API key for provider {provider!r}. "
            f"Get one at: {source}. Then: export {key_env}=... "
            "(or put it in a .env file in the repo root).")
    return problems


def print_check() -> int:
    provider = cfg.chosen_provider()
    key_env = PROVIDER_KEY_ENV.get(provider)
    print(f"LLM provider        : {provider}")
    print(f"Required key        : {key_env or '(none — local provider)'}"
          + (f"  [{'set' if os.environ.get(key_env or '', '').strip() else 'MISSING'}]"
             if key_env else ""))
    if provider == "ollama":
        print("Local endpoint      : "
              + (os.environ.get("TRADINGAGENTS_LLM_BACKEND_URL", "").strip()
                 or cfg.LOCAL_BACKEND_URL))
        print("Local model         : "
              + (os.environ.get("TRADINGAGENTS_QUICK_THINK_LLM", "").strip()
                 or cfg.LOCAL_MODEL) + " (deep + quick tiers)")
    print("Data vendors        : fundamental_data=sec_edgar,yfinance "
          "(both keyless)")
    print("Optional (unused)   : FRED_API_KEY (news/macro analysts only), "
          "ALPHA_VANTAGE_API_KEY (vendor not selected)")
    problems = validate_prerequisites()
    if problems:
        print("\nNOT READY — prerequisites missing:")
        for p in problems:
            print(f"  - {p}")
        return 2
    print("\nREADY: all prerequisites for a fundamentals-first run are present.")
    return 0


def run(tickers: list[str], trade_date: str, with_edgar: bool) -> int:
    problems = validate_prerequisites()
    if problems:
        print("NOT READY — prerequisites missing:")
        for p in problems:
            print(f"  - {p}")
        return 2

    # Lazy imports: the framework is only touched once prerequisites pass.
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    from rajesh_fundamentals import edgar_bridge, normalize

    config = cfg.build_config()
    ta = TradingAgentsGraph(selected_analysts=cfg.SELECTED_ANALYSTS,
                            debug=False, config=config)

    out_dir = os.path.join(cfg.OUTPUT_DIR, "normalized")
    os.makedirs(out_dir, exist_ok=True)
    records = []
    for ticker in tickers:
        print(f"\n=== {ticker} on {trade_date} ===")
        final_state, signal = ta.propagate(ticker, trade_date)
        report_path = ta.save_reports(
            final_state, ticker,
            save_path=os.path.join(cfg.OUTPUT_DIR, "reports",
                                   f"{ticker}_{trade_date}"))
        cross = edgar_bridge.crosscheck(ticker) if with_edgar else None
        record = normalize.normalize(ticker, trade_date, final_state, signal,
                                     str(report_path), cross)
        out_file = os.path.join(out_dir, f"{ticker}.json")
        with open(out_file, "w") as f:
            json.dump(record, f, indent=2)
        records.append(record)
        print(f"{ticker}: rating={signal} verdict={record['verdict']} "
              f"-> {out_file}")

    summary_file = os.path.join(cfg.OUTPUT_DIR, "summary.json")
    with open(summary_file, "w") as f:
        json.dump(records, f, indent=2)
    print(f"\nSummary: {summary_file}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="validate prerequisites only; import nothing "
                             "from the framework")
    parser.add_argument("--tickers", default=",".join(cfg.STARTER_TICKERS),
                        help="comma-separated tickers "
                             f"(default: {','.join(cfg.STARTER_TICKERS)})")
    parser.add_argument("--date", default=datetime.date.today().isoformat(),
                        help="analysis date YYYY-MM-DD (default: today)")
    parser.add_argument("--no-edgar", action="store_true",
                        help="skip the EDGAR cross-check sidecar")
    args = parser.parse_args()

    if args.check:
        return print_check()
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    return run(tickers, args.date, with_edgar=not args.no_edgar)


if __name__ == "__main__":
    raise SystemExit(main())
