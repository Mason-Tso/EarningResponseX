"""Type a ticker, get a humanized earnings-reaction X post draft.

Usage:
    python earnings_post.py PANW
    python earnings_post.py NVDA --save
    python earnings_post.py MSFT --no-transcript --effort medium

Pulls the latest reported quarter's data from FMP (numbers, transcript, press
release), then drafts an X post in the configured voice via Claude. Nothing is
posted — the draft prints to your terminal for review.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

import fmp
import writer

load_dotenv()

# Windows consoles default to cp1252, which mangles characters like the euro
# sign that show up in transcripts. Force UTF-8 so drafts render and copy clean.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def _die(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"\n[error] {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Draft a humanized earnings-reaction X post.")
    parser.add_argument("ticker", help="Stock ticker, e.g. PANW")
    parser.add_argument("--save", action="store_true", help="Also save the draft to drafts/")
    parser.add_argument("--no-transcript", action="store_true",
                        help="Skip the earnings-call transcript (faster, cheaper, less depth)")
    parser.add_argument("--model", default=os.getenv("CLAUDE_MODEL", writer.DEFAULT_MODEL),
                        help="Claude model id (default: %(default)s)")
    parser.add_argument("--effort", default=os.getenv("CLAUDE_EFFORT", "high"),
                        choices=["low", "medium", "high", "xhigh", "max"],
                        help="Reasoning effort (default: %(default)s)")
    args = parser.parse_args()

    fmp_key = os.getenv("FMP_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not fmp_key:
        _die("FMP_API_KEY is not set. Add it to your .env file.")
    if not anthropic_key:
        _die("ANTHROPIC_API_KEY is not set. Add it to your .env file "
             "(get one at https://console.anthropic.com/settings/keys).")

    ticker = args.ticker.upper().strip()

    # 1. Gather data
    print(f"[1/2] Pulling {ticker} earnings data from FMP...", file=sys.stderr)
    try:
        bundle = fmp.gather(ticker, fmp_key, include_transcript=not args.no_transcript)
    except fmp.FMPError as e:
        _die(f"FMP: {e}")
    except Exception as e:  # network etc.
        _die(f"Could not fetch data for {ticker}: {e}")

    r = bundle["reported"]
    fiscal = bundle.get("fiscal", {})
    has_transcript = bool(bundle.get("transcript"))
    print(
        f"      {fiscal.get('period')} FY{fiscal.get('year')} | "
        f"EPS {r.get('eps_actual')} vs {r.get('eps_estimated')} | "
        f"Rev {writer._fmt_money(r.get('revenue_actual'))} vs "
        f"{writer._fmt_money(r.get('revenue_estimated'))} | "
        f"transcript: {'yes' if has_transcript else 'no'}",
        file=sys.stderr,
    )

    # 2. Write the post
    print(f"[2/2] Drafting post with {args.model} (effort={args.effort})...", file=sys.stderr)
    try:
        post = writer.write_post(bundle, anthropic_key, model=args.model, effort=args.effort)
    except Exception as e:
        _die(f"Claude: {e}")

    # Output
    print("\n" + "=" * 60)
    print(f"  DRAFT X POST  -  ${ticker}  ({fiscal.get('period')} FY{fiscal.get('year')})")
    print("=" * 60 + "\n")
    print(post)
    print("\n" + "=" * 60)
    print(f"  {len(post)} chars  |  review before posting", file=sys.stderr)

    if args.save:
        out_dir = Path("drafts")
        out_dir.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = out_dir / f"{ticker}_{fiscal.get('period') or 'Q'}{fiscal.get('year') or ''}_{stamp}.txt"
        path.write_text(post, encoding="utf-8")
        print(f"  saved -> {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
