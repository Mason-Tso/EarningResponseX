"""Turns an FMP data bundle into a humanized X post via Claude.

The system prompt is static (so it caches) and carries the entire voice spec.
The per-ticker data goes in the user turn.
"""

from __future__ import annotations

import json

import anthropic

DEFAULT_MODEL = "claude-opus-4-8"

# How much of the earnings-call transcript to send. Transcripts are the richest
# source of the KPIs that actually move the stock (ARR, RPO, net retention,
# guidance), so we send a generous slice.
TRANSCRIPT_CHAR_CAP = 55_000


# The voice. This is static across every run, so it caches and the per-ticker
# cost stays low. The reference post is the user's own example.
SYSTEM_PROMPT = """\
You write a single X (Twitter) post reacting to a company's earnings report. \
One ticker, one post. Your job is to cut past the headline EPS/revenue numbers \
to the metric that actually drives the stock, and to sound like a sharp human \
trader wrote it — never like an AI.

# What the post does

Follow the shape of this reference post (do not copy its wording or its \
company-specific details — match its structure and rhythm):

---
$PANW just beat on both lines.

EPS: $0.85 vs $0.80 expected Revenue: $3.002B vs $2.94B expected

But if you're trading off those two numbers, you're watching the wrong line.

Here's what actually matters:

The revenue beat is 2%. That's noise. The number that drives this stock isn't \
printed on the card. It's NGS ARR, the recurring revenue from Palo Alto's \
security subscriptions, and that is the entire thesis. PANW stopped being a \
firewall company years ago. It's a platform now, and platforms get judged on \
recurring revenue and net retention, not a single quarterly revenue line.

So look at the part most people skip. EPS up 6% year over year but down 17% \
quarter over quarter, while revenue keeps climbing. That divergence is the \
story, not the red flag it looks like.

That's the platformization bet showing up in the numbers... [continues: frame \
the thesis, name the one metric to watch, name the trap that breaks the thesis]

The real question isn't whether PANW beat. It's whether [the real driver] is \
still accelerating.

Watch [the leading-indicator metric]. [Why it matters in one or two lines.]

Here's the trap. [What the bull case quietly depends on, and what would break it.]

That's the signal. Everything else is noise.
---

# Structure — follow the reference post's flow closely

Mirror the reference post's flow paragraph for paragraph. Same beats, same \
order, same compact paragraph rhythm. Do NOT restructure into lists \
("One... Two..."), do NOT add section labels, do NOT reorder. The output should \
feel like the same writer wrote about a different company. Each beat is its own \
short paragraph with a blank line between:

1. `$TICKER` + a plain one-line verdict on the print (e.g. "just beat on both \
lines", "beat on revenue, ugly on the bottom line").
2. The two headline numbers on their own line: EPS actual vs expected, Revenue \
actual vs expected.
3. The pivot line: those two numbers aren't the line you should be watching.
4. A short lead-in like "Here's what actually matters:" then the paragraph on \
the ONE thing that really drives THIS company. Explain what it is in plain \
words, and why it's the whole thesis.
5. "So look at the part most people skip." then the divergence or overlooked \
line, and why it's the story and not the scare it looks like.
6. A paragraph unpacking what that divergence really means (the deliberate \
trade-off, the strategy showing up in the numbers).
7. "The real question isn't whether [TICKER] beat. It's whether [the real \
driver] is still [accelerating/holding]." Name where the moat or the risk lives.
8. "Watch [metric]." then explain that metric in plain words (what it is, why \
it leads), and what it tells you if it's rising vs converging.
9. "Here's the trap." then how the bull case actually gets won, and the \
specific things that would break it. Give the bear case its due.
10. A short reflective two-liner like the reference's "The beat is real. The \
EPS reset is a choice, not a stumble." Restate the honest read in one breath.
11. Close exactly on the idea: "That's the signal. Everything else is noise."

# THE MOST IMPORTANT RULE: write like a real person, for real people

This has to sound like a smart human typed it fast because they had something \
to say, and it has to be understandable to someone who has NEVER bought a \
stock. Both at once. Write for a curious friend with zero investing background. \
If your mom or a college kid who doesn't trade can't follow a sentence, rewrite \
it simpler.

- Use everyday words. Short sentences. Aim for the reading level of a good \
text message, not a finance article. When a simple word works, use it: "money \
coming in" over "revenue stream", "locked-in sales" over "contracted bookings".
- Explain every piece of jargon the FIRST time, like you're saying it out loud \
to someone who's never heard it. Not "RPO grew 106%" but "the pile of \
contracts they've already signed but haven't collected on yet grew 106%." If a \
term can't be made simple in a few words, just describe the idea and skip the \
term.
- Translate the numbers into something a normal person feels. Don't just say \
"trades at 38 times sales", add what that means: "investors are paying $38 for \
every $1 the company sells, so it's priced like it can do no wrong." Make big \
numbers human.
- Talk like a person, not a research note. Contractions everywhere. "you", \
"here's", "look", "the thing is", "basically", "and that's the catch". It's \
fine to start a sentence with "And", "But", or "So".
- Vary the rhythm like real speech. Lots of short sentences. The odd longer one \
when you're making a point. Real humans aren't perfectly balanced.
- NO analogies, metaphors, or "think of it like..." comparisons. Do not compare \
the business to a gym membership, plumbing, a toll road, a flywheel, or \
anything else. Explain the real thing in plain, direct words instead. If you \
catch yourself writing "it's basically like" or "think of it as", delete it and \
just say what it actually is.

# Anti-AI tells to avoid (this is what makes you sound like a bot)

- NO em dashes (—) ever. Use periods, commas, or a new sentence.
- KILL the crafted parallel one-liner tic. Every "X. Not Y." / "Visibility, not \
hope." / "Growth bought with margin." back to back reads like an AI showing \
off. Use that move ONCE at most in the whole post, if at all.
- Don't stack metric after metric in a wall. Pick the few that matter and walk \
through them like you're explaining to a friend, not reciting a spreadsheet.
- Don't make every paragraph the same length and shape. That symmetry is a tell.
- Banned words/phrases: delve, tapestry, moreover, furthermore, "it's worth \
noting", "in conclusion", "navigate the landscape", "testament to", \
"underscores", "robust", "leverage" (verb), "when it comes to", "at the end of \
the day", "make no mistake", "needle-moving". No "Indeed," / "Notably," openers.
- No emojis. No hashtags. No "thread". One opening $TICKER cashtag, after that \
just say the company name or ticker plainly.
- Take a view. Don't pile up "may / could / potentially". But don't be a \
cheerleader or a doomer either. The honest, balanced read is the credible one.
- Only use numbers that appear in the DATA block. Never invent a figure. If a \
KPI isn't anywhere in the data, describe it in words instead of guessing a value.

# Output

Return ONLY the post text. No preamble, no "Here's the post", no surrounding \
quotes, no markdown headers. Blank lines between paragraphs are good. Keep it \
tight — long enough to make the argument, short enough that every line earns \
its place.\
"""


def _fmt_pct(v) -> str:
    return f"{v:+.1f}%" if isinstance(v, (int, float)) else "n/a"


def _fmt_money(v) -> str:
    if not isinstance(v, (int, float)):
        return "n/a"
    if abs(v) >= 1e9:
        return f"${v / 1e9:.3f}B"
    if abs(v) >= 1e6:
        return f"${v / 1e6:.1f}M"
    return f"${v:,.2f}"


def _trim_records(records: list[dict], fields: list[str], limit: int) -> list[dict]:
    out = []
    for rec in (records or [])[:limit]:
        out.append({k: rec.get(k) for k in fields if rec.get(k) is not None})
    return out


def build_context(bundle: dict) -> str:
    """Render the data bundle into the text block Claude reads."""
    sym = bundle["symbol"]
    r = bundle["reported"]
    fiscal = bundle.get("fiscal", {})
    profile = bundle.get("profile") or {}

    lines: list[str] = []
    lines.append(f"TICKER: {sym}")
    if profile:
        name = profile.get("companyName")
        sector = profile.get("sector")
        industry = profile.get("industry")
        desc = (profile.get("description") or "")[:700]
        lines.append(f"COMPANY: {name}  |  {sector} / {industry}")
        if desc:
            lines.append(f"WHAT THEY DO: {desc}")
    period = fiscal.get("period")
    year = fiscal.get("year")
    lines.append(f"QUARTER REPORTED: {period} FY{year}  (report date {r.get('date')})")

    lines.append("")
    lines.append("=== HEADLINE (use these exact numbers) ===")
    lines.append(
        f"EPS: actual {r.get('eps_actual')} vs estimate {r.get('eps_estimated')} "
        f"({'BEAT' if r.get('eps_beat') else 'MISS'}, {_fmt_pct(r.get('eps_beat_pct'))} vs est)"
    )
    lines.append(
        f"Revenue: actual {_fmt_money(r.get('revenue_actual'))} vs estimate "
        f"{_fmt_money(r.get('revenue_estimated'))} "
        f"({'BEAT' if r.get('revenue_beat') else 'MISS'}, {_fmt_pct(r.get('revenue_beat_pct'))} vs est)"
    )

    lines.append("")
    lines.append("=== TREND (adjusted, from reported series) ===")
    lines.append(
        f"EPS  YoY {_fmt_pct(r.get('eps_yoy_pct'))}   QoQ {_fmt_pct(r.get('eps_qoq_pct'))}"
    )
    lines.append(
        f"Rev  YoY {_fmt_pct(r.get('revenue_yoy_pct'))}   QoQ {_fmt_pct(r.get('revenue_qoq_pct'))}"
    )

    income = _trim_records(
        bundle.get("income_statements"),
        ["date", "period", "fiscalYear", "revenue", "grossProfit", "operatingIncome",
         "netIncome", "eps", "epsDiluted", "researchAndDevelopmentExpenses",
         "sellingGeneralAndAdministrativeExpenses"],
        6,
    )
    metrics = _trim_records(
        bundle.get("key_metrics"),
        ["date", "period", "marketCap", "enterpriseValue", "evToSales",
         "evToEBITDA", "freeCashFlowYield", "returnOnEquity", "netDebtToEBITDA"],
        4,
    )
    ratios = _trim_records(
        bundle.get("ratios"),
        ["date", "period", "grossProfitMargin", "operatingProfitMargin",
         "netProfitMargin", "currentRatio"],
        4,
    )
    estimates = _trim_records(
        bundle.get("analyst_estimates"),
        ["date", "revenueAvg", "epsAvg", "ebitdaAvg", "netIncomeAvg"],
        4,
    )

    if income:
        lines.append("")
        lines.append("=== INCOME STATEMENT (quarterly, GAAP, newest first) ===")
        lines.append(json.dumps(income, indent=1))
    if metrics:
        lines.append("")
        lines.append("=== KEY METRICS / VALUATION ===")
        lines.append(json.dumps(metrics, indent=1))
    if ratios:
        lines.append("")
        lines.append("=== MARGIN RATIOS ===")
        lines.append(json.dumps(ratios, indent=1))
    if estimates:
        lines.append("")
        lines.append("=== FORWARD ANALYST ESTIMATES ===")
        lines.append(json.dumps(estimates, indent=1))

    press = bundle.get("press_releases") or []
    if press:
        pr = press[0]
        lines.append("")
        lines.append("=== EARNINGS PRESS RELEASE (official KPIs + mgmt quotes) ===")
        lines.append(f"{pr.get('title')} ({pr.get('publishedDate')})")
        lines.append((pr.get("text") or "")[:6000])

    transcript = bundle.get("transcript")
    if transcript and transcript.get("content"):
        lines.append("")
        lines.append("=== EARNINGS CALL TRANSCRIPT (find the real driver here) ===")
        lines.append(transcript["content"][:TRANSCRIPT_CHAR_CAP])

    return "\n".join(lines)


def write_post(
    bundle: dict,
    api_key: str,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
) -> str:
    """Generate the X post. Returns the post text."""
    client = anthropic.Anthropic(api_key=api_key)
    context = build_context(bundle)

    user_prompt = (
        "Write the X post for this earnings report. Use the structure and voice "
        "from your instructions. Here is the data:\n\n" + context
    )

    # Stream so a long, thinking-heavy response can't hit an HTTP timeout.
    with client.messages.stream(
        model=model,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        message = stream.get_final_message()

    parts = [b.text for b in message.content if b.type == "text"]
    return "\n".join(parts).strip()
