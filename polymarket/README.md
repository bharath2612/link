# The Question Wire — new Polymarket questions, daily

A tiny tracker + landing page for genuinely new questions added to Polymarket.

## How it works

Polymarket's public **Gamma API** (`gamma-api.polymarket.com`, no auth needed) lists
every market/event with a `createdAt` timestamp:

```
GET /events?limit=100&order=createdAt&ascending=false&active=true&closed=false&exclude_tag_id=102169
```

Two layers of filtering separate real questions from machine-generated noise:

1. **`exclude_tag_id=102169`** ("Hide From New" — Polymarket's own tag for its
   auto-generated markets) drops the ~2,000/day 5-minute crypto up/down markets
   server-side.
2. Events with a **`series`** field (recurring sports match markets, player props,
   etc.) are dropped client-side.

What remains is ~20–30 genuinely new questions per day.

## Files

- `fetch_new_questions.py` — pulls the newest 500 events, filters, and merges them
  into `data.json` (14 days of history kept) and `data.js` (same data, loadable
  from `file://`).
- `index.html` — the landing page. Just open it; no server needed.
- `data.json` / `data.js` — generated output.

## Usage

```bash
python3 fetch_new_questions.py   # capture today's new questions
open index.html                  # view the page
```

Run the fetcher on a daily cron to keep capturing:

```
0 9 * * * cd /Users/bharathchippa/Downloads/Projects/polymarket && python3 fetch_new_questions.py
```

## Note on network blocking

This network resets direct connections to `*.polymarket.com` (ISP-level block of
betting sites). The fetch script detects this and automatically falls back to the
`r.jina.ai` read-through proxy. On an unblocked network (e.g. a deployed server),
it uses the API directly.
