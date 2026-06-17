# stock-research-cockpit

An AI skill for structured equity research. It turns a rough stock question, user notes, or local `trader-obsidian` data into a repeatable research cockpit.

## What it does

- Separates **Research Score** from **Timing State**.
- Builds an evidence-backed report instead of a generic AI stock answer.
- Discloses data gaps and source failures.
- Works with or without the local `trader-obsidian` companion repo.

## Modes

| Mode | Requirement | Result |
|---|---|---|
| Skill-only | Any AI agent that can read this skill | Structured analysis from user-provided and available data |
| Local companion | `trader-obsidian` repo, CLI, or MCP tools | Data pipeline, Obsidian write-back, review/backtest, report quality checks |
| External finance skills | Optional finance/data/social-reader skills | Better valuation, estimates, sentiment, source-reader and market-structure coverage |

## Install / use

For Codex-style local skills, copy this folder into the user's skills directory or keep it in a repo-local `skills/` folder:

```text
skills/stock-research-cockpit/
```

Then ask the AI agent for stock analysis, thesis review, valuation, Timing State, or Obsidian write-back. The skill should trigger on stock research tasks.

## Safety boundary

This skill produces research, not personalized financial advice. It should not place trades, request brokerage credentials, hide source failures, or write to an Obsidian vault unless the user explicitly wants write-back.
