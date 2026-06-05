# Timing State Framework

Timing State measures entry quality. It is separate from Research Score.

## States

| State | Use when | Typical action language |
|---|---|---|
| Ready | Thesis is acceptable and entry setup has clear triggers/risk control | "Actionable only if position sizing and invalidation are respected." |
| Wait | Thesis may be good, but price, catalyst, or setup is not ready | "Wait for trigger." |
| Watch | Low confidence or incomplete data; keep on radar | "Monitor; no full position." |
| Avoid | Thesis quality, timing, liquidity, or valuation risk is too poor | "Avoid until conditions materially change." |

## Inputs

- Trend and price structure.
- Support/resistance or Wyckoff structure.
- RSI/volume/volatility.
- Earnings or catalyst window.
- Liquidity, short interest, options/sentiment crowding.
- Research Score as a guardrail.
- Data freshness.

## Required Output

Every Timing State needs:

- State.
- Main reasons.
- Entry triggers.
- Invalidation triggers.
- Risk flags.

## Guardrails

- Stale market data should usually prevent `Ready`.
- Low Research Score should cap timing at `Watch` unless the user explicitly asks for a short-term trade setup.
- High valuation can be compatible with `Ready` only if catalyst and risk controls are unusually clear.
