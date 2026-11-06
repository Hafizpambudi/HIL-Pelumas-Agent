# Roadmap and Decisions

---

## 1. Phases

### Phase 0 — Discovery (1 week)
Goal: replace assumptions with facts.

- Shadow the two admins for 2 days. Record real conversations.
- Answer the open questions in `01-prd.md` §11.
- Get: conversation volume, price source, stock source, quote conversion,
  discount authority, brand exclusivity.
- Collect datasheets for the low-spec SKUs.

**Exit:** a one-page baseline with real numbers.

### Phase 1 — Catalog and fitment (2 weeks)
Goal: the agent can answer product questions correctly.

- Crawl and normalize 91 products.
- Author Indonesian descriptions.
- Build fitment rules for flow meters (highest volume).
- Curate 15+ equivalence pairs with the client's technical contact.
- Stand up retrieval + guards, no WhatsApp yet.

**Exit:** 90% part resolution on the golden set, safety suite green.

### Phase 2 — RFQ and handoff (2 weeks)
Goal: one conversation becomes one priceable record.

- RFQ schema, assembler, validator.
- Admin handoff message.
- Price relay with audit trail.
- Staging WhatsApp number end to end.

**Exit:** 10 real conversations shadowed, admin approves 70%+ without edit.

### Phase 3 — Availability and substitution (1 week)
Goal: stockouts stop killing threads.

- Availability adapter, `manual` implementation first.
- Substitution flow with confidence labels.
- Warehouse check routing.

**Exit:** stockout scenarios in eval pass; admin agrees the fallback is usable.

### Phase 4 — Steady state
- Weekly eval run, monthly catalog refresh.
- Reporting to the owner.

Total: **6 weeks** to v1, assuming discovery yields answers.

## 2. Cut lines

If time compresses, cut in this order. Everything here is a real feature, just
not the thing that proves the concept.

1. Photo intake — accept images, attach them, do not interpret
2. Admin portal — WhatsApp-only handoff is enough for v1
3. Spec comparison (A5) — nice, not load-bearing
4. Job-to-BOM (A3) — valuable, but phase 2 is defensible without it
5. Warehouse routing automation — a manual forward is acceptable

**Never cut:** guards, RFQ validator, admin handoff, eval harness.

## 3. Phase 2 candidates

Ranked by expected value, from the earlier analysis.

| # | Use case | Why it is phase 2 |
|---|---|---|
| 1 | Quote follow-up at D+2 / D+7 / D+14 | Needs RFQ data from v1 to exist first |
| 2 | Repeat-order reactivation from WhatsApp history | Highest-margin revenue; needs consent and history access |
| 3 | Cross-sell accessory set from the primary part | Easy once fitment exists |
| 4 | Tender / project intake | Highest ticket size, needs a different workflow |
| 5 | After-sales and warranty | Protects repeat business |
| 6 | Meta CAPI / Google Ads feedback | Only if they actually advertise |
| 7 | Demand signal report | Cheap, and it is the renewal argument |
| 8 | Voice / inbound calls | Big differentiator, high effort |

Do not start any of these until v1 has run for a month with clean evals.

## 4. Architecture decisions

### ADR-001 — WhatsApp only, no web widget in v1
**Context:** buyers already arrive on WhatsApp; the site has no form.
**Decision:** single surface.
**Consequence:** no web presence for the agent; all value must land in chat.

### ADR-002 — The agent never quotes price
**Context:** price is negotiated per buyer and lives with the admin.
**Decision:** price is always a human action; the agent relays and records.
**Consequence:** slower than full automation, but protects margin and removes
the largest liability. Also removes the need to model pricing rules.

### ADR-003 — Availability is a state machine, not a lookup
**Context:** no machine-readable stock source is confirmed to exist.
**Decision:** model `available | indent | unknown | discontinued` with source
and timestamp; ship the `manual` adapter first.
**Consequence:** the feature is honest on day one and improves without a
rewrite when a real source appears.

### ADR-004 — Fitment is curated, not inferred
**Context:** model inference on industrial fitment is unsafe and unauditable.
**Decision:** explicit rules and a curated equivalence table, with a named
verifier.
**Consequence:** slower to extend to new categories, but every claim is
defensible.

### ADR-005 — Guards run post-generation in code
**Context:** prompt instructions are not guarantees.
**Decision:** validate outbound text; rewrite on violation; log the block.
**Consequence:** some legitimate messages get rewritten; accepted as the cost
of never misquoting.

### ADR-006 — Handoff happens in WhatsApp, not email
**Context:** the admins live in WhatsApp; a portal they do not open is dead
weight.
**Decision:** structured summary as a WhatsApp message plus a link.
**Consequence:** message length is constrained; the record carries the detail.

### ADR-007 — Retrieval is exact-first
**Context:** semantic search over an industrial catalog produces plausible
wrong answers.
**Decision:** exact part number, then structured filters, then semantic — and
semantic results are always candidates.
**Consequence:** some natural-language queries need a clarifying question.

## 5. Rejected options

- **Fine-tune on the catalog.** It hallucinates specs and cannot be audited.
  Retrieval is correct here.
- **Scrape prices from competitors.** Legal risk, and their prices are not the
  client's prices.
- **Auto-negotiate with a discount ladder.** Destroys the relationship the
  business runs on.
- **Full self-serve portal.** The buyer base does not want one; the admins will
  not maintain it.
- **Voice first.** Highest effort, and text must work before the channel
  multiplies.

## 6. Open decisions

| Decision | Needed by | Owner |
|---|---|---|
| Stock source reality | Phase 0 | Client |
| Datasheet availability | Phase 0 | Client |
| Who verifies equivalences | Phase 1 | Client |
| Discount authority | Phase 2 | Owner |
| Catalog maintenance after handover | Phase 4 | Both |
| Whether ads exist (CAPI value) | Phase 2 | Client |

## 7. Risks to revisit monthly

- Catalog coverage drifting below 80%
- Handoff rate climbing above 40% (retrieval degrading)
- Admin adoption slipping (measured by edit rate in shadow)
- WhatsApp template rejections
- Guard blocks spiking (either attacks or over-blocking)
