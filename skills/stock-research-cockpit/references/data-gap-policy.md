# Data Gap Policy

Data gaps are not footnotes. They directly affect confidence and actionability.

## Required Disclosures

Disclose missing or failed data for:

- Current price / historical price.
- Fundamentals and valuation inputs.
- Earnings dates and estimates.
- Liquidity and short interest.
- Options / IV / Greeks / GEX when relevant.
- Insider or congressional trading when relevant.
- News, filings, transcripts, or source-reader outputs.
- User-provided notes if the user expected vault/material context.

## Handling Missing Data

| Situation | Response |
|---|---|
| Source unavailable | State source failure and continue with lower confidence. |
| Conflicting sources | Show both values and avoid false precision. |
| Stale data | Mark timing as lower confidence; avoid `Ready` unless setup is source-independent. |
| No valuation inputs | Do not invent valuation. Ask for or fetch the missing input. |
| No user notes/context | Say the report is public-data-only and may miss prior thesis history. |

## Local Companion

When `trader-obsidian` is available, inspect `_data_sources` from `generate_analysis()` and include source-attempt failures in the Data Gaps section.
