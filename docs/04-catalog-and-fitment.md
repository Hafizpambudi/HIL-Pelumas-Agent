# Catalog and Fitment — Working Doc

The agent is only as good as this document. Build it first.

Source: https://www.cahayapelumasindo.com — audited 2026-10-28.

---

## 1. What exists today

91 product paths across 6 categories.

| Category | Paths | Brands seen |
|---|---|---|
| flow-meter | 48 | Avery Hardoll, LC, Macnaught, Tokico, Nitto, Flomec, Flo-Rite, Fill-Rite, OGM, Oval, TCS, Z-Flo |
| pompa | 18 | Corken, Ebsray, Southern Cross, Graco (Husky diaphragm) |
| nozzle-gun | 12 | Husky, Gazzo, Shawdev, Flomax, Banlaw, Fast Fill |
| water-meter | 6 | Amico, Itron, SHM, Sensus, BR, POWOGAZ |
| hose-reel | 4 | Graco, Z-Flo |
| aksesoris | 3 | hammer, life vest, wind sock |

Path depth is inconsistent (`/flow-meter/flow-meter-avery-hardoll/avery-hardoll-bm250`
vs `/flow-meter/z-flo-flow-meter/z-flo-40-meter`), so slugs cannot be trusted as
a data model. Parse each page and assign `category` and `brand` explicitly.

## 2. What is missing

- No price. None. Anywhere.
- No stock status, no cart, no quotation form.
- No structured spec block — specs are free text inside the page body.
- No normalized units: pressure appears as bar, psi, and psid; flow as LPM,
  GPM, imp gallon, m3/h.
- Descriptions are manufacturer marketing copy, often English, sometimes about
  aviation refuelling in Illinois. Not buyer-facing.

**Consequence:** the catalog must be *authored*, not scraped. Scraping gives you
91 pages; the agent needs 91 rows with typed fields.

## 3. Normalization schema

Per product, capture these fields. Mark `null` where absent — never guess.

### Identity
`part_no`, `name`, `brand`, `category`, `subcategory`, `status`, `source_url`

### Hydraulic / mechanical
| field | unit | notes |
|---|---|---|
| `connection_size_in` | inch | normalize "2 1/2 Inch", "2.5\"", "2½" |
| `connection_type` | enum | NPT, BSP, flange ASA, victaulic, hose barb |
| `max_pressure_bar` | bar | convert from psi/psid; keep original in `value_text` |
| `test_pressure_bar` | bar | where published |
| `max_temp_c` | °C | normalize "300°F" → 149 |
| `min_temp_c` | °C | |
| `flow_min_lpm` / `flow_max_lpm` | L/min | normalize GPM and m3/h |
| `fluid` | enum set | petrol, diesel, avgas, jet A1, water, solvent, lubricant |
| `flange_rating` | text | "ASA 150 FF" |
| `voltage` | V | pumps only |
| `power_kw` | kW | pumps only |
| `displacement_per_rev_l` | L | positive displacement meters |

### Commercial
`packaging`, `moq` (if known), `lead_time_indent` (if known)

### Editorial
`description_id` — 2–4 sentences in Bahasa Indonesia, written for a buyer.
What it measures, where it is used, what it replaces. Never copied.

## 4. Unit conversion rules

Store numeric + original string. Conversion happens at ingest, once.

- 1 psi = 0.0689476 bar; 1 psid is a differential, not absolute — label it
- 1 US gallon = 3.78541 L; 1 imperial gallon = 4.54609 L
  **Watch this:** Avery Hardoll pages quote "Imp Gallon" and "m3/h" and "l/m" on
  the same line. Getting US vs imperial wrong is a 20% error.
- °F → °C: (F − 32) × 5/9
- Flow range with three representations on one page (BM250 shows 25–250 imp
  gal, 115–1140 l/m, 7–68 m3/h) must be reconciled and checked for consistency.
  If the three do not agree, flag the row `data_confidence = low`.

## 5. Fitment rules

Fitment is not "does it look similar". It is a set of explicit checks. Start
with these for flow meters, which are the highest-volume category.

### FM-1 Connection size
Buyer's line size must equal the meter's connection size, or the buyer must
accept an adapter. If it differs, say so and name both sizes.

### FM-2 Pressure
`max_pressure_bar >= buyer_system_pressure` with a margin. Default margin: 10%.
Below that, do not confirm.

### FM-3 Flow range
`flow_min_lpm <= buyer_flow <= flow_max_lpm`. Below minimum, accuracy degrades
and the agent must say so. Above maximum, the meter is unsuitable.

### FM-4 Fluid compatibility
Fluid must be in the meter's supported set. Aviation meters on diesel is a
question, not a yes.

### FM-5 Flange rating
Where the buyer specifies a flange, it must match or be adaptable.

### FM-6 Accuracy class
Where the buyer specifies a metering standard, compare the published
repeatability/accuracy. Do not claim compliance with a standard not published.

**Evaluation order matters.** Check size first (cheapest to verify, most common
failure), then pressure, then flow, then fluid, then flange. Report the first
failing dimension, not all of them, unless the buyer asks for a full comparison.

## 6. Equivalence classes

Many brands overlap. Equivalence is a curated table, not a model output.

Candidate pairs to verify with the client's technical contact:

- Avery Hardoll BM series ↔ LC positive displacement bulk meters
- Macnaught F/M series ↔ Z-Flo oval gear
- Tokico ↔ Tatsuno-compatible equivalents
- Corken PZ ↔ Ebsray vane pumps (different category, similar duty)
- Graco Husky diaphragm ↔ generic AODD
- Nozzle: Husky ↔ Gazzo ↔ Flomax (connection size and flow are the deciders)
- Water meter: Amico ↔ Itron ↔ Sensus (class and connection)

Each row needs: `relation`, `differing_dims`, `verified_by`, `confidence`.

**Rule:** only `confidence = high` rows may be stated as interchangeable.
Everything else is "kandidat, perlu konfirmasi teknis".

## 7. Coverage targets

Publish these numbers honestly. They are part of the pitch.

| Metric | Target |
|---|---|
| Products with at least 4 typed specs | 80% of 91 |
| Products with a written Indonesian description | 100% |
| Flow meters with full fitment coverage | 100% of 48 |
| Equivalence rows verified by client | 15+ pairs |
| Products with `data_confidence = low` | under 10% |

If the client cannot supply datasheets for the low-spec SKUs, those products
resolve by part number only and always end in handoff. Say this out loud in the
pitch — it is a credibility win, not a weakness.

## 8. Ingest pipeline

1. Crawl the 91 URLs, store raw HTML.
2. Extract: name, brand (from breadcrumb + title), category, spec block text,
   description text, image URL.
3. Parse specs with per-brand patterns. Brands format differently; do not use
   one regex for all.
4. Normalize units. Flag inconsistencies.
5. Write a Bahasa Indonesia description for each product.
6. Human review pass — this is the step that cannot be skipped.
7. Embed and index.
8. Store `source_url` and `fetched_at` for every row.

Re-run the crawl monthly. Diff against the previous run and queue changes for
review rather than overwriting silently.

## 9. Known traps

- **Imp vs US gallon.** Reconcile, do not assume.
- **"psid" is differential.** Not the same as psi working pressure.
- **BM250 spec block describes BM-850.** The page copy says "The BM-850 with
  mechanical register" and quotes 115–3780 LPM — which does not match the
  BM250 header values. Copy-paste error on the source site. Do not trust page
  prose over the header table.
- **Duplicate brand spellings.** "Z-FLO" / "Z-flo", "FLow Meter", "Husky
  Automatic Heavy Nozle" (typo on site). Normalize names, keep the typo as an
  alias so buyers can find it.
- **Some pages have no spec block at all.** Those must be flagged, not filled.
- **Water meter category page has no product links** in the crawl — verify
  manually whether those 6 brands have real product pages or only brand blurbs.

## 10. Open questions for the client

- Can you supply manufacturer datasheets for the low-spec SKUs?
- Which brands do you stock vs. indent?
- Which equivalences are you willing to stand behind?
- Who signs off on the fitment table, and how often is it reviewed?
- What is the actual lead time for indent items?
