# Example: Review / Backtest Summary Shape

## Review Summary

| Field | Result |
|---|---|
| Reviewed tickers | 8 |
| Verified signals | 21 |
| Win rate | 57.1% |
| Expectancy | +1.8% |
| Profit factor | 1.42 |
| Main issue | Ready signals near earnings had poor risk/reward |

## Diagnosis

- Signals with clear invalidation levels performed better than generic bullish calls.
- Reports that disclosed data gaps had fewer false Ready states.
- The next improvement should tighten the rule for earnings-window entries.

## Process Fix

- Require earnings-window scenario analysis before any `Ready` state inside 10 trading days of earnings.
- Lower Timing State to `Wait` when options/IV data is missing and the stock is event-driven.
