# Demo site

Static capability page plus a replay of recorded agent runs. No backend, no API key,
no hosting cost.

## Pages

- `index.html` — capability page (English)
- `demo.html` — replay UI, bilingual: Indonesian and English

## Regenerate the recordings

```powershell
uv run python scripts/make_demo_transcripts.py          # deterministic MockLLM (offline)
uv run python scripts/make_demo_transcripts.py --live   # record with the configured LLM
```

Writes `site/assets/transcripts.json`, merging English text from
`site/assets/translations.json`. Output is deterministic except for the
`generated_at` date, so re-running on unchanged code produces the same file.

The recorder fails loudly when a translation is missing: every scenario needs
`title_en` and `subtitle_en`, and every non-trace message needs `text_en` at the
same index as the recording.

## Translations

| File | Holds |
|---|---|
| `site/assets/i18n.json` | UI strings, `id` and `en` dictionaries |
| `site/assets/translations.json` | scenario titles, subtitles, message text, guard proofs |

English text is hand-authored, not machine-translated at build time.

## Language switch

The demo opens with `?lang=` if present, then a stored choice, then the browser
language, then Indonesian. The `id | en` control sits in the top right of the
header, updates `<html lang>`, the URL query, and the stored preference.

In English mode every chat bubble shows the English text, with the original
Indonesian recording underneath labelled `original`, so the replay stays honest.

`tests/test_site_i18n.py` enforces:

- identical key sets in both dictionaries
- every `data-i18n` key in `demo.html` is defined
- no unused keys
- every scenario and message has English text
- no hardcoded Indonesian strings left in `demo.js`

## Preview locally

```powershell
cd site
python -m http.server 8899
```

Then open `http://localhost:8899/index.html` or `/demo.html?lang=en`.

## Publish

`.github/workflows/pages.yml` uploads `site/` to GitHub Pages on push to
`main` or `master`. Enable Pages with source "GitHub Actions" in repository
settings.

## Content rules

- Agent lines in the replay carry their real guard verdict, computed by the same
  `run_guards` function the agent uses.
- `guard_proofs` shows forbidden strings and the replacement that is sent instead.
- The recorder redacts phone numbers and refuses to write the file if a secret,
  a phone number, or a timestamp leaks into the JSON.
