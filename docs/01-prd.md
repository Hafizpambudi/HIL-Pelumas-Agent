# PRD — WABA Agent for CV Cahaya Pelumasindo

Status: draft for pitch
Owner: [you]
Version: 0.1
Last updated: 2026-10-28

---

## 1. Problem

CV Cahaya Pelumasindo sells industrial fuel-handling equipment — flow meters,
pumps, nozzle guns, water meters, hose reels and safety accessories. Buyers are
B2B: plant engineers, procurement staff, and contractors building fuel
installations (SPBU, depot, fleet yards, mining).

The website publishes **91 product pages and no prices**. Every page ends with
the same button: *"Cek Harga dan Ketersediaan"* — which opens a WhatsApp chat
with one of two admins.

That makes WhatsApp the checkout. And the checkout has three structural
failures:

**F1 — Price is the conversation, not a page.**
Nothing can be decided without an admin. Every inquiry is a human dependency.
Volume cannot grow without headcount.

**F2 — The inquiry arrives unstructured.**
A buyer sends "selamat siang, mau tanya flow meter solar buat pertamina 2
nozzle, budget 15jt" or forwards a competitor's PDF. The admin must reconstruct
part number, quantity, spec, company, delivery city and urgency before anything
can be priced. That reconstruction is repeated hundreds of times.

**F3 — Out of stock is invisible until it is too late.**
Availability is not published. When a part is unavailable, the conversation
either stalls or dies. There is no fallback path to an equivalent model, even
though the catalog carries many interchangeable brands (Avery Hardoll, LC,
Macnaught, Tokico, Flomec, Z-Flo).

Secondary problems, not solved in v1: quotes expire silently, consumables are
never re-ordered proactively, and after-sales competes with sales in the same
inbox.

## 2. Evidence base

Collected from the public site on 2026-10-28.

- 91 product pages, 6 categories: flow meter (48), pompa (18), nozzle gun (12),
  water meter (6), hose reel (4), aksesoris (3)
- 10+ brands, heavily overlapping in function
- Zero price fields, zero stock status, zero cart, zero quotation form
- Spec depth is **uneven**: Avery Hardoll BM250 and Corken PZ10 carry real
  technical blocks; Gazzo carries two lines; some pages carry nothing
- Product descriptions are copied from manufacturer marketing copy (the Avery
  Hardoll block is US aviation copy, not buyer-facing Indonesian)
- Site is Google Sites, copyright 2020 — a brochure, not a commerce system
- Two WhatsApp numbers, one Gmail address, two physical locations
  (Tangerang office + Harco Glodok counter)

Unverified and to be confirmed in discovery: conversation volume, ERP or stock
system, quote-to-order rate, current response time, ad spend.

## 3. Users

### U1 — Plant / fleet engineer (primary)
Knows the spec. Asks for a part number or a precise capability. Wants
availability and lead time. Low patience for discovery questions, low margin,
fastest to close.

### U2 — Procurement / purchasing (primary)
Asks for a quotation, an invoice, terms, company documentation. The negotiation
and approval step happens here. This is where deals are actually won or lost.

### U3 — Project / contractor (primary)
Describes a job, not a part: "SPBU mini, 2 nozzle, flow meter solar, budget X."
Needs configuration. Highest margin, most work, most valuable to capture well.

### U4 — Admin / sales (internal operator, the real customer of the product)
Two people. Currently the bottleneck, the price authority, and the memory of
the business. The agent must make their day faster, not add a new inbox.

### U5 — Owner (economic buyer)
Cares about: more quotes converted, fewer lost inquiries, no new headcount,
visibility into what buyers actually ask for.

## 4. Jobs to be done

- When a buyer messages at 22:00, I want a complete inquiry captured, so the
  admin can price it first thing instead of interviewing the buyer again.
- When a buyer names a part, I want its fitment confirmed against the catalog,
  so we do not quote the wrong size and lose credibility.
- When a part is unavailable, I want a credible equivalent offered in the same
  thread, so the sale does not die on a stockout.
- When a conversation ends, I want one structured record, so nothing is lost in
  a chat history.
- When I am the admin, I want to price in 30 seconds, not re-read 40 messages.

## 5. Scope — v1

Three capabilities, shipped as one loop.

### S1 — Catalog retrieval and fitment matching
Answer product questions from the real catalog, and confirm fitment on the
dimensions that matter: connection size, max working pressure, flow range,
fluid handled, flange rating, brand.

Must handle: part-number lookup, spec lookup, "which one fits X", and
equivalent-model questions.

### S2 — RFQ capture and structured handoff
Convert a free-form thread into a structured RFQ record:

- buyer type (engineer / procurement / project)
- company + contact
- requested item(s), with part number where resolved
- quantity
- key specs
- delivery city
- urgency
- notes and open questions

Hand to the admin in WhatsApp with a compact summary and a link to the record.
The admin replies with price; the agent relays and records.

### S3 — Availability gate and substitution
Never assert stock as fact unless it came from a fresh machine-readable source.
Three states: confirmed available, indent (order-to-lead-time), unknown.

On unavailable or unknown, offer up to two credible equivalents with the
differing specs called out, and mark the substitution as needing confirmation.

## 6. Non-goals — v1

Explicitly excluded. Each is a phase-2 candidate, not an oversight.

- Quoting or negotiating price. The agent never states a number.
- Payments, invoicing, or PO generation.
- Proactive follow-up campaigns, quote expiry chasing, reactivation
- Cross-sell and accessory bundling
- Tender / project intake workflows
- After-sales tickets and warranty
- Voice / inbound calls
- Web widget or any surface other than WhatsApp
- Multi-language beyond Bahasa Indonesia with natural English code-switching
- Replacing the admin. The agent feeds them; it does not displace them.

## 7. Success metrics

Measured against a two-week baseline captured before launch.

**Primary**
- Median time from first buyer message to price-ready RFQ: baseline → under 10
  minutes during business hours, captured overnight otherwise
- Share of inbound conversations ending in a structured RFQ: target 70%+
- Share of RFQs the admin prices without asking the buyer a follow-up question:
  target 80%+ (this is the quality bar for extraction)

**Secondary**
- Wrong-fit recommendations in eval: under 1 in 100, and zero wrong-fit
  recommendations stated with confidence
- Stockout conversations that continue (substitution offered and accepted or
  declined, rather than thread abandoned): target 50%+
- Admin minutes per inquiry: measured before/after, target 50% reduction

**Guardrail**
- Any instance of the agent stating a price: zero tolerance
- Any instance of the agent asserting stock without a fresh source: zero
  tolerance

## 8. Constraints

- **WhatsApp Business Platform rules.** Template messages for anything
  business-initiated; 24-hour customer service window for free-form replies.
  The agent must be built around this, not against it.
- **Two admins, no CRM.** Handoff must work inside WhatsApp. A portal that
  nobody opens is worthless.
- **Uneven catalog data.** Fitment must be built from datasheets, not scraped
  marketing copy.
- **No price data exists digitally.** Price stays human. This is a design
  constraint, not a temporary limitation.
- **Indonesian B2B norms.** Buyers expect fast, informal, code-switching
  replies. Over-formality reads as a bot.

## 9. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Wrong spec recommendation | Lost credibility, wrong goods shipped | Fitment table built from datasheets; default to "perlu konfirmasi" |
| Agent invents a price or stock figure | Commercial and legal damage | Hard block in code, not prompt; eval gate |
| Admin does not adopt the handoff | Product has no value | WhatsApp-native handoff; measure admin minutes |
| Stock lives in one person's memory | Availability feature is hollow | Model it as a human confirmation step in v1 |
| Catalog specs missing for many SKUs | Coverage gaps | Publish a coverage number; be explicit about unknown |
| Client expects full automation | Scope creep, disappointment | Pitch the RFQ framing explicitly; show the non-goals |

## 10. Rollout

1. **Shadow** — agent drafts, admin approves every send. Two weeks.
2. **Assisted** — agent handles product Q&A and RFQ capture directly; price
   always via admin. Two weeks.
3. **Steady** — full v1 scope, weekly eval review, catalog update process live.

## 11. Open questions

- Where does price live today: spreadsheet, ERP, or memory?
- What stock system exists, and is it queryable?
- Daily conversation volume, and new vs. repeat split?
- Current quote-to-order rate and median response time?
- Do they run Meta or Google ads?
- Who may discount, and by how much?
- Which brands are exclusive vs. competing? This changes substitution rules.
