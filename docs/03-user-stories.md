# User Stories — v1

Format: story, then acceptance criteria as testable statements.
`AC` lines are the definition of done. Anything without an AC is not in v1.

Actors: **Engineer** (U1), **Procurement** (U2), **Project buyer** (U3),
**Admin** (U4), **Owner** (U5).

---

## Epic A — Catalog retrieval and fitment (S1)

### A1 — Part lookup by name or number
As an **engineer**, I want to name a part and get its specs, so I can confirm
it matches my installation.

- AC: Given "BM250", the agent resolves to `Avery Hardoll BM250` and returns
  connection size, max pressure, flow range, and fluid handled.
- AC: Given a misspelling or partial ("avery bm 250"), the agent resolves to the
  same part or asks one disambiguating question. It never silently picks.
- AC: Every spec returned is traceable to a catalog row. No spec is generated.
- AC: If a spec is missing for that product, the agent says it is not published
  rather than omitting it silently.

### A2 — Fitment confirmation
As an **engineer**, I want to know whether a part fits my job, so I do not
order the wrong size.

- AC: Given connection size, pressure, flow rate, and fluid, the agent returns
  fit / does not fit / needs confirmation with the specific dimension that
  drives the answer.
- AC: A "does not fit" answer names the failing dimension and the threshold.
- AC: A fitment claim without a backing rule or equivalence row is blocked by
  the guard and replaced with "perlu konfirmasi".
- AC: The agent asks at most one clarifying question before answering.

### A3 — Job-to-parts configuration
As a **project buyer**, I want to describe the installation, not the part, and
still get a credible shortlist.

- AC: Given "SPBU mini, 2 nozzle, flow meter solar", the agent returns a
  candidate BOM of 2–5 items with category and a one-line reason for each.
- AC: Candidates are labelled as candidates, not as a recommendation.
- AC: Missing inputs (flow rate, tank size, power) are asked for, one at a time,
  maximum three questions before offering to hand off.
- AC: The BOM is attachable to the RFQ as line items.

### A4 — Equivalence and substitution
As an **engineer**, I want a workable alternative when my part is unavailable.

- AC: Given a discontinued or indent part, the agent offers at most two
  equivalents, each with the differing dimensions named.
- AC: Equivalents with confidence below high are labelled "perlu konfirmasi
  teknis".
- AC: The agent never presents a substitution as identical.
- AC: If no equivalence row exists, the agent says so and offers handoff
  instead of guessing.

### A5 — Spec comparison
As a **procurement** buyer, I want two options compared side by side.

- AC: Given two parts, the agent returns only the dimensions that differ.
- AC: Dimensions present in one and absent in the other are shown as "tidak
  dipublikasikan", not as zero.
- AC: No winner is declared. The agent may state trade-offs, not a verdict.

### A6 — Honest unknown
As an **admin**, I want the agent to admit gaps, so I do not inherit a confident
wrong answer.

- AC: When retrieval returns nothing, the agent says it could not find the item
  and asks for a photo of the nameplate or the exact model.
- AC: After one failed clarification, it hands off with the thread attached.
- AC: It never invents a brand, model, or spec.

---

## Epic B — RFQ capture and handoff (S2)

### B1 — Buyer identification
As an **admin**, I want to know who I am pricing for, so I can set terms and
priority.

- AC: The agent captures buyer type (engineer / procurement / project) and
  company name where offered.
- AC: Buyer type is inferred from language and confirmed by a single question
  only when it changes the path.
- AC: No more than two identification questions before the buyer's actual need
  is addressed.

### B2 — Structured RFQ
As an **admin**, I want one record per inquiry, so I can price in 30 seconds.

- AC: An RFQ contains: items (part/qty/specs), delivery city, urgency, buyer
  type, contact, open questions.
- AC: An RFQ is only emitted when required fields are present. Required: at
  least one resolvable item, quantity, delivery city.
- AC: Missing required fields are asked for once, in one message, not one by one.
- AC: The RFQ has a human-readable id and a stable deep link.
- AC: The record is written before the handoff message is sent. No handoff
  without a record.

### B3 — Admin handoff in WhatsApp
As an **admin**, I want the summary where I already work, so I do not open a new
tool.

- AC: The handoff arrives on the admin WhatsApp number with: RFQ id, buyer type,
  item summary, qty, city, urgency, and open questions.
- AC: The handoff message fits one screen without scrolling on a phone.
- AC: If the admin does not reply within the configured window, the agent tells
  the buyer an honest ETA and logs a pending handoff.
- AC: The admin can reply with a price in the same thread and the agent relays
  it and records it against the RFQ.

### B4 — Price relay with audit
As an **owner**, I want every quoted price to be traceable, so we never argue
about what was promised.

- AC: A price is only sent to a buyer after an admin action. Never generated.
- AC: Every relayed price stores: admin identity, timestamp, raw admin message,
  RFQ id.
- AC: If the buyer asks for a discount, the agent hands off. It does not
  counter-offer.
- AC: The guard blocks any outbound message containing a currency amount that
  did not originate from an admin action.

### B5 — Conversation continuity
As a **buyer**, I want the agent to remember what I already said.

- AC: Across a thread, previously supplied fields are never asked again.
- AC: If the buyer returns after more than 24 hours, the agent reuses the
  stored state and confirms rather than restarts.
- AC: A buyer may say "seperti tadi" and the agent resolves it from state.

---

## Epic C — Availability and substitution (S3)

### C1 — Availability states
As a **buyer**, I want to know if you can actually deliver.

- AC: Every availability answer is one of: tersedia, indent (with lead time),
  perlu dicek, discontinued.
- AC: "Tersedia" is only stated when the source is fresh and non-manual.
- AC: In manual mode, the answer is always "perlu dicek ke gudang" and a
  warehouse check is requested.
- AC: The agent never states a stock quantity.

### C2 — Stockout recovery
As an **owner**, I want a stockout to still produce a quote, not a dead thread.

- AC: On indent or unknown, the agent offers: wait for indent, or consider an
  equivalent, or handoff.
- AC: If the buyer chooses the equivalent, the RFQ is updated with both options
  so the admin can price either.
- AC: The thread is never left without a next step.

### C3 — Warehouse request
As an **admin**, I want stock checks routed, not guessed.

- AC: A stock check creates an event and, if configured, a message to the
  warehouse contact.
- AC: The buyer is told when to expect an answer.
- AC: If no answer arrives, the agent follows up internally once, then tells the
  buyer honestly.

---

## Epic D — Operations and safety

### D1 — Guard enforcement
As an **owner**, I want the agent physically unable to misquote.

- AC: The price guard is unit-tested against 40+ adversarial strings and blocks
  all of them.
- AC: A blocked message is replaced by the safe fallback, not dropped silently.
- AC: Guard blocks are logged as events with the original text.

### D2 — Admin override
As an **admin**, I want to take over any conversation.

- AC: The admin can send a keyword or use a dashboard action to pause the agent.
- AC: While paused, the agent sends nothing.
- AC: Resuming restores state and the agent picks up with context.
- AC: Overrides are logged.

### D3 — Reporting
As an **owner**, I want to see what buyers ask for.

- AC: Weekly report: conversation count, RFQ count, conversion to priced quote,
  top requested parts, requested-but-not-stocked parts, guard blocks, handoff
  reasons.
- AC: Every number links to the underlying records.

### D4 — Catalog freshness
As an **admin**, I want to correct the catalog without a developer.

- AC: A product's specs and status can be edited by an admin, with an audit
  trail.
- AC: Edited rows are flagged and re-embedded within one hour.
- AC: A discontinued flag removes the product from candidate answers but keeps
  it resolvable by exact part number.

---

## Out of v1 — do not build

Quote follow-up, reactivation campaigns, cross-sell bundling, tender intake,
after-sales tickets, voice, web widget, payments, PO generation, multi-language
beyond ID/EN.

Each has a placeholder in `06-roadmap-and-decisions.md`.

---

## Definition of ready

A story enters the build only when it has: an AC set, the data it depends on,
a way to test it, and a named owner.

## Definition of done

Code merged, AC covered by an automated test where testable, eval set updated,
logged in the changelog, and demoable on staging.
