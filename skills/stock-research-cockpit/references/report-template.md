# Stock Research Cockpit Report Template

Use this template for normal analysis. Keep the top section compact so a user can decide what to inspect next.

```markdown
# {Company Name} ({Ticker})

## Cockpit Summary

| Field | Result |
|---|---|
| Research Score | {score}/100 ({confidence}) |
| Timing State | {Ready/Wait/Watch/Avoid} |
| Current stance | {research / wait / watch / avoid} |
| Biggest positive driver | {driver} |
| Biggest risk | {risk} |
| Data gaps | {none or concise list} |

**One-line view:** {plain-language conclusion}

## Evidence Table

| Claim | Direction | Source / evidence | Credibility | Impact |
|---|---|---|---|---|
| {claim} | Supports / weakens / neutral | {source} | High / medium / low | Up / down / confidence-only |

## Five-Dimension Research Score

| Dimension | Score | Weight | Rationale |
|---|---:|---:|---|
| Industry / TAM | {0-10} | 20% | {why} |
| Moat | {0-10} | 20% | {why} |
| Growth quality | {0-10} | 20% | {why} |
| Valuation | {0-10} | 25% | {why} |
| Team / governance | {0-10} | 15% | {why} |

## Timing Plan

- **State:** {Ready/Wait/Watch/Avoid}
- **Entry triggers:** {observable triggers}
- **Invalidation triggers:** {observable conditions that break the thesis or timing setup}
- **Position guardrail:** {size guidance based on confidence/risk, not a command}

## Valuation and Scenarios

| Scenario | Probability | Key assumptions | Implied value / return |
|---|---:|---|---:|
| Bull | {x}% | {assumptions} | {value} |
| Base | {x}% | {assumptions} | {value} |
| Bear | {x}% | {assumptions} | {value} |

## Risks and Open Questions

- **Top risk:** {risk and quantified impact if possible}
- {risk 2}
- {risk 3}

## Next Actions

- {actionable research step}
- {data to verify}
- {price/event trigger to watch}

## Data Gaps

- {missing module/source/input and impact}

**Disclaimer:** This analysis is for research only and is not financial advice.
```
