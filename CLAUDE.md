# CLAUDE.md

Guidance for Claude Code when working in this repo.

## What this project is

A CLI that drafts a humanized X (Twitter) post reacting to a company's earnings
report. You give it a ticker, it pulls the latest reported quarter from
Financial Modeling Prep (headline numbers, earnings-call transcript, press
release, valuation/margins), and drafts a post with Claude in a specific voice.
Nothing is auto-posted — drafts are for review.

## THE WORKFLOW (most important)

When the user gives you a ticker (e.g. "VEEV", "give me the post for NVDA",
"PANW"), this is the whole job:

1. Run the tool:
   ```powershell
   python earnings_post.py <TICKER>
   ```
2. Paste the **full post text back into the chat** for the user to read. Not a
   summary — the actual post, clean, ready to copy.

That's it. The user puts in a ticker, you give them the post. Don't explain the
internals unless asked. Don't restructure or hand-edit the post yourself — the
voice lives in the system prompt; if the voice needs to change, change
`writer.py` (see below) and re-run, don't patch the output by hand.

Useful flags: `--save` (also write to `drafts/`), `--no-transcript` (faster,
cheaper, less depth), `--effort low|medium|high|xhigh|max`.

## Files

- `earnings_post.py` — CLI entry point. Gather → draft → print.
- `fmp.py` — Financial Modeling Prep data layer. Uses the `/stable` API (the old
  `/v3` endpoints are retired). Computes the headline beat % and YoY/QoQ deltas
  in Python from the reported-earnings series, so numbers are never the model's
  arithmetic.
- `writer.py` — builds the prompt and calls Claude. **`SYSTEM_PROMPT` holds the
  entire voice spec.** This is the file to edit when tuning how posts sound.
- `.env` — API keys (gitignored, never committed).

## The voice (when editing `writer.py`'s SYSTEM_PROMPT)

The post must mirror the reference post's flow (verdict → headline numbers →
"you're watching the wrong line" → "Here's what actually matters" → the one
real driver → "So look at the part most people skip" → the divergence and what
it means → "The real question isn't whether X beat" → "Watch [metric]" →
"Here's the trap" → reflective two-liner → "That's the signal. Everything else
is noise."). Hard rules already encoded, keep them:

- Sound like a real person typing fast, understandable to someone who has never
  bought a stock. Everyday words, short sentences.
- Explain every finance term the first time, in plain words. Translate big
  numbers ("38x sales" → "$38 for every $1 of sales").
- **No analogies or metaphors.** Explain the real thing directly.
- No em dashes. No emojis, hashtags, or threads. One opening `$TICKER` cashtag.
- Only use numbers that appear in the data; never invent a figure.
- Balanced, not a cheerleader or a doomer.

## Conventions

- Model: `claude-opus-4-8`, adaptive thinking, effort `high`. The static system
  prompt is cached.
- Windows console is forced to UTF-8 in `earnings_post.py` so transcript
  characters (€, curly quotes) render and copy cleanly.
- Keys come from `.env` via `python-dotenv`. Never hardcode keys or print them.

## Don'ts

- Don't commit `.env` or anything under `drafts/`.
- Don't auto-post to X. This tool only drafts.
- Don't add the X posting step without an explicit confirm flow.
