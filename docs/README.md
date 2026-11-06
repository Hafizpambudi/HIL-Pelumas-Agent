# Agent CV Pelumasindo

WABA agent for CV Cahaya Pelumasindo — an industrial fuel-handling equipment
distributor (flow meters, pumps, nozzles, water meters).

The agent does **not** sell. It converts a messy WhatsApp inquiry into a
**price-ready RFQ** for the admin.

## The one-line thesis

> Price and availability live only in conversation. The WhatsApp admin *is* the
> checkout. So the agent's job is to make that one conversation complete.

## v1 scope — three things

1. Catalog retrieval + fitment matching over the real 91-product catalog
2. RFQ capture + structured handoff to the admin
3. Availability gate + substitution suggestion when a part is unavailable

Everything else (follow-up, reactivation, cross-sell, tender intake, voice)
is deliberately out of v1. See `docs/06-roadmap-and-decisions.md`.

## Docs

| File | What it answers |
|---|---|
| `docs/01-prd.md` | Why, for whom, what success looks like |
| `docs/02-sdd.md` | How it is built: architecture, data model, pipeline |
| `docs/03-user-stories.md` | Stories with acceptance criteria |
| `docs/04-catalog-and-fitment.md` | The normalization work and matching rules |
| `docs/05-eval-plan.md` | How we prove it works before the client sees it |
| `docs/06-roadmap-and-decisions.md` | Phases, cut lines, ADRs |
| `docs/07-pitch-onepager.md` | One page to leave with the owner |

## Hard rules baked into the design

- Never quote a price. Ever. The agent produces an RFQ.
- Never state stock as fact unless the source is fresh and machine-read.
- Never guess a part when fitment is ambiguous. Ask one question, then hand off.
- Always identify as an AI assistant.
