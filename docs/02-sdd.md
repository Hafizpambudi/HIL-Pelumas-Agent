# SDD — System Design Document

WABA Agent for CV Cahaya Pelumasindo
Version 0.1 — 2026-10-28
Companion to `01-prd.md`

---

## 1. Design principles

1. **Retrieval before generation.** Every product claim must trace to a row in
   the catalog table. If it is not in the table, the agent says it does not
   know. No model memory, no inference from brand familiarity.
2. **Guards in code, not in prompts.** Price and stock assertions are blocked
   by a validator that runs on the outbound message, after generation.
3. **The handoff is the product.** A perfect conversation that produces no
   structured record is a failure.
4. **WhatsApp is the UI.** No portal is required for v1 operation. A read-only
   admin view is optional.
5. **Fail to a human, never to a guess.** Ambiguity resolves upward.

## 2. Architecture

```
WhatsApp Business Platform (Cloud API)
        |
        v
  Webhook receiver  ──►  dedupe + normalize  ──►  queue
                                                     |
                                                     v
                                            Conversation orchestrator
                                            (state machine + LLM loop)
                                              |        |         |
                        ┌─────────────────────┘        |         └──────────────┐
                        v                              v                        v
                 Catalog / Fitment             Availability            RFQ assembler
                 (Postgres + pgvector)         (adapter + cache)        (schema + validator)
                        |                              |
                        └──────────► Tool layer ◄──────┘
                                          |
                                          v
                                  Outbound guard
                                  (price / stock / claim check)
                                          |
                                          v
                                  WhatsApp send  +  Admin handoff
```

### Components

**Webhook receiver**
Verifies Meta signature, acknowledges fast, enqueues. Must be idempotent on
message id — Meta retries.

**Conversation orchestrator**
Owns per-thread state: stage, resolved entities, open questions, buyer type.
Decides whether to answer, ask, or hand off. LLM is called with a bounded
context built from state plus retrieved rows, never the raw catalog.

**Catalog and fitment store**
Normalized product table plus a spec table plus a fitment rules table.
Vector index for fuzzy natural-language lookup. Exact lookup by part number and
brand takes precedence over semantic search.

**Availability adapter**
Interface with three implementations, chosen per client reality:
- `erp` — query the client's system, if one exists and is reachable
- `sheet` — read a maintained spreadsheet, with a freshness timestamp
- `manual` — no source; every answer is "perlu konfirmasi" and routed to the
  admin. This is the expected v1 implementation.

Returns one of `available | indent | unknown | discontinued` plus a
`source` and `observed_at`.

**Tool layer**
Narrow, typed functions. The model may only call these. No free-form HTTP.

- `search_products(query, filters)`
- `get_product(part_no)`
- `compare_specs(part_nos[], dimensions[])`
- `find_equivalent(part_no, constraints)`
- `check_availability(part_no, qty)`
- `create_rfq(payload)`
- `handoff(reason, summary)`
- `log_event(type, payload)`

**RFQ assembler**
Builds and validates the record. Refuses to emit an RFQ missing required
fields; instead it names the missing fields and asks for them, once.

**Outbound guard**
Runs on every outbound message. Blocks:
- currency amounts, price-like patterns, discount language
- absolute stock claims without a fresh `available` from a non-manual source
- fitment claims not backed by a retrieved row
On block, the message is rewritten to the safe fallback for that intent.

**Admin handoff**
Sends a compact WhatsApp message to the admin number with the RFQ summary and
a deep link. Admin replies with price in-thread. Agent records the quote.

## 3. Conversation state machine

```
NEW
 └─► IDENTIFY        buyer type, company, intent
      └─► QUALIFY    part or job; specs; quantity
           ├─► RESOLVE     part number confirmed against catalog
           │    └─► FIT_CHECK  fitment confirmed or questioned
           ├─► CONFIGURE   job described → candidate BOM
           └─► UNRESOLVED  cannot map → ask once → handoff
                └─► AVAILABILITY
                     ├─► AVAILABLE → RFQ
                     ├─► INDENT    → lead time note → RFQ
                     ├─► UNKNOWN   → RFQ flagged "cek stok"
                     └─► DISCONTINUED → SUBSTITUTE
                                        └─► RFQ
RFQ ──► HANDOFF ──► AWAIT_PRICE ──► QUOTED ──► CLOSED | LOST | DORMANT
```

Any state may transition to `HANDOFF` on: explicit request, repeated
misunderstanding, negotiation, complaint, or a guard block that cannot be
safely rewritten.

## 4. Data model

### `product`
| field | notes |
|---|---|
| `id` | uuid |
| `part_no` | canonical, uppercased, unique where known |
| `slug` | from the site path |
| `name` | as published |
| `brand` | normalized (Avery Hardoll, LC, Macnaught, ...) |
| `category` | flow_meter, pompa, nozzle_gun, water_meter, hose_reel, aksesoris |
| `subcategory` | e.g. positive displacement, diaphragm, vane |
| `description_id` | buyer-facing Indonesian description, written by us |
| `source_url` | provenance |
| `data_confidence` | high / medium / low |
| `status` | active / discontinued / unknown |

### `spec`
| field | notes |
|---|---|
| `product_id` | fk |
| `key` | connection_size, max_pressure_bar, flow_min_lpm, flow_max_lpm, fluid, flange_rating, voltage, ... |
| `value_num` | numeric where possible |
| `value_text` | unit-bearing original |
| `unit` | normalized unit |
| `source` | datasheet / site / inferred |
| `confidence` | high / medium / low |

### `fitment_rule`
| field | notes |
|---|---|
| `id` | uuid |
| `category` | applies to which category |
| `dimension` | e.g. connection_size |
| `relation` | eq / gte / lte / in_set / overlap |
| `threshold` | json |
| `rationale` | one line, human-readable |
| `verified_by` | name |

### `equivalence`
| field | notes |
|---|---|
| `a_product_id` | fk |
| `b_product_id` | fk |
| `relation` | interchangeable / close / not_equivalent |
| `differing_dims` | json |
| `verified_by` | name, or null for model-suggested |
| `confidence` | high / medium / low |

Rule: an equivalence with `confidence != high` may only be presented as
"kandidat, perlu konfirmasi".

### `conversation`
`id`, `wa_thread_id`, `buyer_phone`, `buyer_type`, `stage`, `state_json`,
`created_at`, `updated_at`, `assigned_admin`

### `rfq`
| field | notes |
|---|---|
| `id` | human-readable, e.g. `RFQ-2026-10-0001` |
| `conversation_id` | fk |
| `company` | nullable |
| `contact_name` | nullable |
| `buyer_type` | engineer / procurement / project / unknown |
| `items` | json array: part_no, qty, specs, notes |
| `delivery_city` | |
| `urgency` | |
| `open_questions` | json |
| `status` | draft / ready / sent_to_admin / priced / closed / lost |
| `admin_note` | |
| `quoted_total` | written only by admin path |

### `event`
Append-only. `conversation_id`, `type`, `payload`, `at`. Types: `message_in`,
`message_out`, `tool_call`, `guard_block`, `handoff`, `rfq_created`,
`admin_price`, `error`.

## 5. Retrieval design

Three tiers, in order:

1. **Exact** — part number, brand + model. Deterministic. Highest trust.
2. **Filtered** — structured filters (category + connection size + flow range).
   Deterministic, computed from spec table.
3. **Semantic** — embedding search over name + description + specs. Used only
   when 1 and 2 return nothing, and results are always presented as candidates.

Hard rule: a semantic hit is **never** stated as a fact about fitment. It
produces a candidate list and a question.

Chunking: one document per product, composed of name, brand, category,
normalized specs, and description. Include part number verbatim. Do not chunk
mid-spec.

## 6. Prompt and context contract

Per turn the orchestrator builds:

- system: role, guard rules, tone rules, language rules
- conversation state: stage, resolved entities, open questions
- retrieved rows: at most 5 products, each with only the fields needed
- last N messages (N bounded, oldest dropped first)
- tool schemas

Explicitly **excluded** from context: full catalog, price data, other
conversations, admin notes.

Tone rules: Bahasa Indonesia default, mirror the buyer's language and register,
natural code-switching with English technical terms, no corporate filler, short
messages, one question at a time.

## 7. Guards

### Price guard
Block if outbound contains: `Rp`, `IDR`, digit groups resembling money,
`harga`, `diskon`, `potongan`, `nego`, `net`, `grosir` in a pricing sense.
Fallback: "Untuk harga, saya teruskan ke admin ya — sebentar."

### Stock guard
Block any `available` claim unless `check_availability` returned
`available` with `observed_at` within the freshness window (default 15 min) and
`source != manual`.
Fallback: "Saya cek dulu ketersediaannya ke gudang."

### Fitment guard
Block any statement of compatibility unless backed by an `equivalence` row or a
`fitment_rule` evaluation. Fallback: "Perlu saya konfirmasi dulu kecocokannya
dengan tim teknis."

Guards run post-generation and are unit-tested against a corpus of adversarial
outputs. They are not prompt instructions.

## 8. WhatsApp specifics

- **24-hour window.** Free-form replies only inside it. Outside, use approved
  templates. v1 templates: `rfq_ack`, `quote_ready`, `need_info`,
  `availability_pending`.
- **Idempotency.** Dedupe on `wamid`. Store processed ids for 7 days.
- **Media.** Buyers send photos of nameplates and competitor datasheets. v1
  extracts text and attaches it to the RFQ as an image reference; it does not
  attempt OCR-based part resolution unless confidence is high.
- **Handoff.** Agent posts the RFQ to the admin's WhatsApp, not email. A link
  to a read-only record is included but not required to operate.
- **Rate and quality.** Keep template categories correct; avoid marketing
  templates for service messages.

## 9. Non-functional

- **Latency.** p95 first reply under 6 seconds. Retrieval under 300 ms.
- **Availability.** Webhook 99.5%. Queue retries with backoff.
- **Observability.** Every turn logs: retrieved rows, tool calls, guard
  results, token cost. One trace per conversation.
- **Cost.** Target under USD 0.01 per conversation at v1 volume. Cache
  retrieval results per thread.
- **Security.** Meta signature verification, secrets in env, no PII in logs
  beyond phone hash, admin actions authenticated.
- **Data retention.** Conversation text 12 months; RFQ records retained.
- **Auditability.** Every price ever shown to a buyer must be traceable to an
  admin action. This is a hard requirement.

## 10. Failure modes

| Failure | Behaviour |
|---|---|
| Model calls no tool and answers from memory | Guard blocks; force retrieval retry once; then handoff |
| Retrieval returns nothing | Say so, ask one clarifying question, then handoff |
| Availability adapter down | Degrade to `unknown`, never to `available` |
| Admin does not respond | Agent tells buyer an honest ETA; logs a pending handoff |
| Buyer sends a competitor PDF | Extract, attach to RFQ, do not guess equivalence |
| Buyer negotiates | Handoff immediately, with context |
| Duplicate webhook | Deduped, no double reply |
| Buyer writes in English | Mirror English, keep part numbers verbatim |

## 11. Environments

- `dev` — local, mocked WhatsApp, seeded catalog subset
- `staging` — real Meta sandbox number, full catalog, admin test number
- `prod` — client number, both admins, eval gate before promotion

## 12. Deployment

Single service plus Postgres. Containerized. Webhook behind a stable HTTPS
endpoint. Config per client: WhatsApp credentials, admin numbers, availability
adapter, freshness window, language default, feature flags.

Feature flags for v1: `substitution`, `photo_intake`, `admin_portal`.

## 13. Testing strategy

- **Unit** — guards, RFQ validator, fitment rules, spec normalization
- **Golden set** — 120 real-style inquiries with expected part resolution
- **Adversarial** — prompt injection, price extraction attempts, competitor
  bait, "just give me the price"
- **Shadow replay** — recorded real conversations replayed against new prompts
- **E2E** — staging number, full loop including admin price relay

Gate to prod: fitment accuracy at or above target on the golden set, zero guard
escapes on the adversarial set.

## 14. Open technical questions

- Does any stock source exist that can be queried? Determines whether S3 is
  real or a confirmation workflow.
- Can we get datasheets for the low-spec SKUs? Determines catalog coverage.
- Who maintains the catalog after handover, and how often do prices change?
- Is a read-only admin view required, or is WhatsApp enough?
