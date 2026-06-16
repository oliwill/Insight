---
name: stock-research-cockpit
description: Use this skill whenever the user asks for stock analysis, investment research, a buy/hold/sell view, valuation, timing, thesis review, or wants to turn notes/news/materials into a structured equity research report. It creates a stock research cockpit with evidence, Research Score, Timing State, valuation, risks, data gaps, and next actions. It can run in pure skill-only mode or use the trader-obsidian local companion tools when available.
---

# Stock Research Cockpit

Create structured, evidence-backed stock research that separates long-term thesis quality from short-term trade timing. The goal is not to sound confident; the goal is to make the user's decision process inspectable, repeatable, and easy to revisit.

## Operating Modes

Choose the mode from available tools and the user's request.

| Mode | Use when | Behavior |
|---|---|---|
| Skill-only | No local repo, MCP, or Obsidian tools are available | Use user-provided data and accessible sources. Disclose missing data explicitly. Do not pretend to have live prices or filings if not available. |
| Local companion | `trader-obsidian` repo, MCP server, or CLI is available | Prefer local pipeline data, Obsidian context, evidence extraction, report quality checks, and optional wiki writes. Ask before writing to the vault unless the user explicitly requested a write. |
| External finance skills | Market-analysis/data-provider/social-reader skills are available | Use them to fill investment-grade gaps such as valuation, estimates, GEX/options flow, insider activity, supply chain, SEPA, sentiment, or TradingView data. |

## Core Rule

Keep these two layers separate:

- **Research Score**: company/thesis quality. It answers "is this worth researching or owning?"
- **Timing State**: entry quality. It answers "is now a good time to act?"

A great company can be a poor entry. A strong chart can still be a weak thesis. Never collapse these into one generic recommendation.

## Workflow

1. **Identify the task**
   - Extract ticker, market, time horizon, and whether the user wants analysis, review, valuation, timing, or Obsidian write-back.
   - Ask a clarifying question only if the ticker or task boundary is missing. Otherwise proceed and state assumptions.

2. **Collect context**
   - In skill-only mode, use user notes, screenshots/text, and available public/source data.
   - In local companion mode, prefer `python run_analysis.py <TICKER>` for data-only context.
   - If the user explicitly wants a report written to Obsidian, use the local write path such as `python scripts/analyze_stock.py <TICKER>`.
   - If using social/source readers, keep them read-only and disclose risk or access gaps.

3. **Build evidence**
   - Separate facts, source claims, user notes, and inference.
   - Track credibility and whether each item supports or weakens the thesis.
   - If evidence is thin, lower confidence rather than filling the gap with prose.

4. **Score the thesis**
   - Use the five-dimension Research Score in `references/scoring-framework.md`.
   - Report score as 0-100 and include confidence.
   - Explain the top 2 positive drivers and top 2 weaknesses.
   - Add a separate moat stress test: first define the business boundary, then analyze a new entrant attack path, industry profit pool, and long-term durability.

5. **Assess Timing State**
   - Use `Ready`, `Wait`, `Watch`, or `Avoid` from `references/timing-framework.md`.
   - Timing must include entry triggers and invalidation triggers.
   - If market data is stale or unavailable, Timing State should usually be `Watch` or `Wait`, not `Ready`.

6. **Build valuation and scenarios**
   - Use P/S, PSG, forward PE, DCF, relative valuation, or SOTP as appropriate to the business.
   - Include Bull/Base/Bear scenarios when valuation is part of the question.
   - If valuation inputs are missing, list them as data gaps.

7. **Produce the report**
   - Use `references/report-template.md` as the default shape.
   - Keep the top cockpit short. Put long analysis below.
   - Include data gaps and report confidence before any action language.

8. **Quality check**
   - Confirm required sections exist.
   - Confirm Research Score and Timing State are not mixed.
   - Confirm data gaps are disclosed.
   - If local `analyzer.report_quality.ReportQualityEvaluator` is available, use it.

## Local Companion Commands

Use these only when the repo is available and the user has consented to any write side effects.

```bash
# Data only; does not write an Obsidian report.
python run_analysis.py <TICKER>

# Full Cockpit report; writes to the configured Obsidian vault.
python scripts/analyze_stock.py <TICKER>

# Review previously logged timeline signals.
python scripts/run_review.py --days-after 30 --lookback 90

# Environment and regression smoke checks.
powershell -ExecutionPolicy Bypass -File scripts\windows\run_smoke_tests.ps1 -SkipRuntimeChecks
```

Do not run write commands when the user only asked for reasoning or a dry run.

## Output Requirements

For normal stock analysis, output in this order:

1. **Cockpit Summary**: one-screen conclusion with Research Score, Timing State, confidence, key evidence, biggest risk, and data gaps.
2. **Evidence Table**: key facts and source quality.
3. **Five-Dimension Score**: scores and rationale.
4. **Timing Plan**: state, triggers, invalidation, position sizing guardrails.
5. **Valuation / Scenarios**: only as strong as the data supports.
6. **Risks and Open Questions**.
7. **Next Actions**.
8. **Disclaimer**: analysis only, not financial advice.

## Safety and Trust Boundaries

- Do not fabricate live prices, analyst estimates, filings, insider data, or source-reader outputs.
- Do not give personalized financial advice as a command. Prefer "conditions under which this becomes actionable."
- Do not place trades, suggest broker actions, or request brokerage credentials.
- Do not write to Obsidian or modify local files without explicit user intent.
- Do not hide data-source failures. Data gaps are part of the product.

## References

Load only the relevant reference:

| Reference | Use when |
|---|---|
| `references/report-template.md` | Need the full report shape or output format. |
| `references/scoring-framework.md` | Need Research Score calculation. |
| `references/timing-framework.md` | Need entry/timing state. |
| `references/data-gap-policy.md` | Data is missing, stale, conflicting, or source failures occurred. |
| `references/obsidian-sections.md` | User wants Obsidian write-back or Markdown section compatibility. |

Examples:

- `examples/first-analysis.md`: compact first report shape.
- `examples/review-report.md`: review/backtest summary shape.
