"""Normalize a finished TradingAgents run into one JSON record per ticker.

Target shape (shared with the ai-hedge-fund wrapper so the two
frameworks' outputs can be cross-checked field by field):

    {
      "ticker": "AAPL",
      "trade_date": "2026-11-20",
      "framework": "TradingAgents",
      "framework_rating": "Overweight",        # 5-tier, or "REVIEW"
      "verdict": "buy candidate",              # buy candidate|watch|avoid
      "fundamentals_evidence": {
        "summary_excerpt": "...",              # head of the analyst report
        "key_points_table": "...",             # its closing markdown table
        "report_path": ".../fundamentals_report.md (inside raw_report_path)"
      },
      "risks": {
        "bear_case_excerpt": "...",
        "risk_debate_excerpt": "...",
        "final_decision_excerpt": "..."
      },
      "edgar_crosscheck": {...} | null,        # from edgar_bridge
      "raw_report_path": "..."                 # framework report tree
    }

The framework's rating scale is Buy / Overweight / Hold / Underweight /
Sell, plus the REVIEW sentinel when its decision carries no parseable
rating. Mapping: Buy/Overweight -> "buy candidate", Hold/REVIEW ->
"watch" (REVIEW is flagged, never silently treated as a Hold),
Underweight/Sell -> "avoid".
"""
from __future__ import annotations

RATING_TO_VERDICT = {
    "Buy": "buy candidate",
    "Overweight": "buy candidate",
    "Hold": "watch",
    "Underweight": "avoid",
    "Sell": "avoid",
    "REVIEW": "watch",
}

_EXCERPT_CHARS = 1600


def _excerpt(text: str | None, limit: int = _EXCERPT_CHARS) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " [...]"


def _closing_table(report: str | None) -> str:
    """The markdown table the Fundamentals Analyst is told to append."""
    lines = (report or "").splitlines()
    table = [ln for ln in lines if ln.strip().startswith("|")]
    if len(table) < 2:
        return ""
    return "\n".join(table[-12:])


def normalize(ticker: str, trade_date: str, final_state: dict, signal: str,
              raw_report_path: str, edgar_crosscheck: dict | None) -> dict:
    debate = final_state.get("investment_debate_state") or {}
    risk = final_state.get("risk_debate_state") or {}
    fundamentals_report = final_state.get("fundamentals_report") or ""
    return {
        "ticker": ticker,
        "trade_date": trade_date,
        "framework": "TradingAgents",
        "framework_rating": signal,
        "verdict": RATING_TO_VERDICT.get(signal, "watch"),
        "needs_review": signal == "REVIEW",
        "fundamentals_evidence": {
            "summary_excerpt": _excerpt(fundamentals_report),
            "key_points_table": _closing_table(fundamentals_report),
            "report_path": raw_report_path,
        },
        "risks": {
            "bear_case_excerpt": _excerpt(debate.get("bear_history")),
            "risk_debate_excerpt": _excerpt(
                risk.get("current_conservative_response")),
            "final_decision_excerpt": _excerpt(
                final_state.get("final_trade_decision")),
        },
        "edgar_crosscheck": edgar_crosscheck,
        "raw_report_path": raw_report_path,
    }
