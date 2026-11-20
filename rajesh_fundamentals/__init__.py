"""Rajesh's fundamentals-first wrapper around the TradingAgents fork.

This package EXTENDS the upstream framework from the outside: it never
modifies upstream files. It configures a fundamentals-only analyst run,
normalizes the framework's output into a per-ticker JSON record, and
attaches an independent cross-check from our own SEC EDGAR pipeline.

Research / decision support only. Nothing here places, simulates, or
routes any trade.
"""
