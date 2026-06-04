# EarningResponseX

Type a ticker the moment an earnings report drops, get a humanized X post draft
that cuts past the headline EPS/revenue numbers to the metric that actually
moves the stock.

It pulls the latest reported quarter from **Financial Modeling Prep** (the
headline numbers, the earnings-call transcript, the press release, valuation and
margin context), then drafts the post with **Claude** in a specific
non-AI-sounding voice. Nothing is posted automatically — every draft prints to
your terminal for review.

## Setup

```powershell
# 1. install deps
python -m pip install -r requirements.txt

# 2. copy the env template and fill in your keys
copy .env.example .env
# then edit .env and set FMP_API_KEY and ANTHROPIC_API_KEY
```

Get keys here:
- **FMP**: https://site.financialmodelingprep.com/developer/docs
- **Anthropic (Claude)**: https://console.anthropic.com/settings/keys

## Use

```powershell
python earnings_post.py PANW
python earnings_post.py NVDA --save              # also write to drafts/
python earnings_post.py MSFT --no-transcript     # skip transcript (faster/cheaper)
python earnings_post.py AMD --effort medium      # lower reasoning effort
```

It always uses the **most recent reported quarter** for the ticker.

## How it works

```
ticker ─▶ fmp.py ──▶ data bundle ──▶ writer.py ──▶ Claude ──▶ draft post
              │                          │
   earnings / income / metrics /   builds the prompt:
   ratios / estimates / transcript / static voice spec (cached)
   press release                   + per-ticker data block
```

- `fmp.py` — fetches all six FMP data sources and computes the headline beat and
  the YoY/QoQ deltas in Python (so the numbers are never the model's
  arithmetic). The earnings-call transcript is where the real driver lives
  (ARR, RPO, net retention, guidance), so a generous slice is sent to the model.
- `writer.py` — holds the voice spec in a static (cached) system prompt and
  sends the data in the user turn. Uses `claude-opus-4-8` with adaptive thinking.
- `earnings_post.py` — the CLI. Gather → draft → print.

## Cost & caching

The voice spec is a static system prompt with a cache breakpoint, so repeat runs
within the cache window are cheaper. Most of the input tokens are the transcript;
use `--no-transcript` to cut cost when you only need a numbers-driven take.

## Security

`.env` is gitignored — keys never reach GitHub. The FMP and X keys were shared
in chat during setup; rotate them in their respective dashboards when convenient.

## Roadmap ideas

- `--post` flag to publish via the X API after a `y/n` confirm.
- Cache the transcript locally to re-draft without re-fetching.
- A `--style` flag to swap voice presets.
