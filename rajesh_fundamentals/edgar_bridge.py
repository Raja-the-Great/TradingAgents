"""Cross-check bridge to our own free SEC EDGAR pipeline.

Why a cross-check and not a data feed INTO the framework:

TradingAgents already ships a first-class SEC EDGAR vendor
(``tradingagents/dataflows/vendors/sec_edgar.py``) and routes statement
tools through a vendor registry that lives inside the upstream package.
Feeding our pipeline in as a vendor would mean adding a module inside
``tradingagents/dataflows/vendors/`` and editing the upstream router —
exactly the upstream surgery this wrapper exists to avoid. It would
also buy nothing on data: both pipelines read the same EDGAR
companyfacts, and the framework's vendor is arguably stricter (it
serves statements as filed, by filing date).

What our pipeline adds is a *deterministic second opinion*: the
Quality/Growth/Strength/Valuation composite score and hard
disqualifiers from ``paper_agent/scoring.py``, computed from
``paper_agent/edgar.py`` extractions. The wrapper attaches that score
to each normalized record so an LLM narrative verdict can be checked
against a number that no LLM produced.

Everything here is keyless (SEC EDGAR is free; facts are cached under
the paper-agent goal's hidden_files for 7 days). Any failure returns
``{"available": False, "reason": ...}`` — a missing cross-check must
never fail a framework run.
"""
from __future__ import annotations

import os
import sys

_PAPER_AGENT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "paper_agent")
)


def _strength_hint(result: dict) -> str:
    if result.get("disqualifiers"):
        return "disqualified"
    score = result.get("score")
    if score is None:
        return "no_data"
    if score >= 70:
        return "strong"
    if score >= 55:
        return "moderate"
    return "weak"


def crosscheck(ticker: str, price: float | None = None) -> dict:
    """Deterministic EDGAR score for one ticker, or an unavailable stub.

    ``price`` is optional: without it the valuation sub-metrics (P/E,
    FCF yield) come back empty and coverage drops, but the quality /
    growth / strength picture — the part that cross-checks a
    fundamentals narrative — is unaffected.
    """
    try:
        # paper_agent is a package: its PARENT dir goes on sys.path.
        parent = os.path.dirname(_PAPER_AGENT_DIR)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        from paper_agent import edgar, scoring  # noqa: E402
        from paper_agent.universe import UNIVERSE  # noqa: E402

        entry = next((e for e in UNIVERSE if e.ticker == ticker), None)
        if entry is None:
            return {"available": False,
                    "reason": f"{ticker} is not in the paper-agent universe"}
        facts = edgar.fetch_company_facts(entry.cik)
        fin = edgar.extract_financials(facts)
        result = scoring.score_company(ticker, fin, price)
        return {
            "available": True,
            "source": "paper_agent EDGAR pipeline (deterministic, keyless)",
            "score": result["score"],
            # scoring.py's coverage_pct is already a percentage (0-100).
            "coverage_pct": result.get("coverage_pct"),
            "components": {
                name: comp.get("score")
                for name, comp in result["components"].items()
            },
            "disqualifiers": result["disqualifiers"],
            "strength_hint": _strength_hint(result),
        }
    except Exception as exc:  # cross-check is advisory; never raise
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
