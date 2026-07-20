#!/usr/bin/env python3
"""
Capture newly created Polymarket questions into data.json / data.js.

Talks to the public Gamma API (gamma-api.polymarket.com). If the network
blocks Polymarket (some ISPs reset the connection), it falls back to the
r.jina.ai read-proxy automatically.

Run daily (cron / launchd / manually):
    python3 fetch_new_questions.py

Outputs:
    data.json  - accumulated list of new questions (last KEEP_DAYS days)
    data.js    - same data as `window.QUESTIONS = ...` so index.html works
                 when opened directly from disk (file://)
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

GAMMA = "https://gamma-api.polymarket.com"
PROXY_PREFIX = "https://r.jina.ai/"  # fallback when Polymarket is blocked

# Tag 102169 = "Hide From New": Polymarket's own flag for auto-generated
# recurring markets (5-min crypto up/down etc). Excluding it server-side
# avoids paging through ~2000 machine-made events per day.
EVENTS_QUERY = (
    "/events?limit=100&offset={offset}&order=createdAt&ascending=false"
    "&active=true&closed=false&exclude_tag_id=102169"
)

PAGES = 5          # 5 x 100 events covers several days of creations
KEEP_DAYS = 14     # how much history to keep in data.json

HERE = Path(__file__).resolve().parent
DATA_JSON = HERE / "data.json"
DATA_JS = HERE / "data.js"

_use_proxy = False


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "new-questions-tracker/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(path: str):
    """GET a Gamma API path, falling back to the read-proxy on network errors."""
    global _use_proxy
    if not _use_proxy:
        try:
            return json.loads(http_get(GAMMA + path))
        except Exception as exc:
            print(f"  direct fetch failed ({exc}); switching to proxy", file=sys.stderr)
            _use_proxy = True
    body = http_get(PROXY_PREFIX + GAMMA + path)
    # The proxy wraps the payload in a markdown envelope.
    match = re.search(r"Markdown Content:\n(.*)", body, re.S)
    return json.loads(match.group(1) if match else body)


def is_new_question(event: dict) -> bool:
    """A genuinely new question, not an auto-generated recurring market."""
    if event.get("series"):
        return False
    tags = {t.get("slug") for t in (event.get("tags") or [])}
    return not tags & {"recurring", "hide-from-new"}


def slim(event: dict) -> dict:
    markets = event.get("markets") or []
    outcomes = []
    # For grouped events show the leading outcomes; for a single binary
    # market show its Yes price.
    try:
        if len(markets) == 1:
            names = json.loads(markets[0].get("outcomes") or "[]")
            prices = json.loads(markets[0].get("outcomePrices") or "[]")
            outcomes = sorted(zip(names, map(float, prices)), key=lambda p: -p[1])
        else:
            for m in markets:
                prices = json.loads(m.get("outcomePrices") or "[0]")
                outcomes.append((m.get("groupItemTitle") or m.get("question") or "", float(prices[0])))
            outcomes.sort(key=lambda p: -p[1])
    except (ValueError, TypeError):
        outcomes = []
    return {
        "id": event["id"],
        "title": event.get("title", ""),
        "slug": event.get("slug", ""),
        "createdAt": event.get("createdAt", ""),
        "endDate": event.get("endDate") or "",
        "image": event.get("image") or event.get("icon") or "",
        "volume": float(event.get("volume") or 0),
        "tags": [t.get("label", "") for t in (event.get("tags") or [])][:4],
        "outcomes": [[n, p] for n, p in outcomes[:3]],
        "nMarkets": len(markets),
    }


def main() -> None:
    print("Fetching newest events from Gamma API...")
    fresh = {}
    for page in range(PAGES):
        events = fetch_json(EVENTS_QUERY.format(offset=page * 100))
        if not events:
            break
        kept = [slim(e) for e in events if is_new_question(e)]
        for q in kept:
            fresh[q["id"]] = q
        print(f"  page {page + 1}: {len(events)} events, {len(kept)} new questions")

    existing = {}
    if DATA_JSON.exists():
        try:
            existing = {q["id"]: q for q in json.loads(DATA_JSON.read_text())["questions"]}
        except (ValueError, KeyError):
            pass

    merged = {**existing, **fresh}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).isoformat()
    questions = sorted(
        (q for q in merged.values() if q["createdAt"] >= cutoff),
        key=lambda q: q["createdAt"],
        reverse=True,
    )

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "questions": questions,
    }
    DATA_JSON.write_text(json.dumps(payload, indent=1))
    DATA_JS.write_text("window.QUESTIONS = " + json.dumps(payload) + ";\n")
    print(f"Saved {len(questions)} questions ({len(fresh)} seen this run) -> data.json, data.js")


if __name__ == "__main__":
    main()
