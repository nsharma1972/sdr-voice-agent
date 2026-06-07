"""Build SDR Voice Agent pitch deck."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# ── Brand colours ─────────────────────────────────────────────────────────────
DARK_BG   = RGBColor(0x0D, 0x0F, 0x1A)   # near-black navy
ACCENT    = RGBColor(0x5B, 0x9B, 0xF4)   # bright blue
ACCENT2   = RGBColor(0x3D, 0xD6, 0x8C)   # green
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT     = RGBColor(0xB8, 0xC8, 0xE8)
MUTED     = RGBColor(0x55, 0x66, 0x88)
CARD_BG   = RGBColor(0x14, 0x1A, 0x2E)

SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)


def new_prs() -> Presentation:
    prs = Presentation()
    prs.slide_width  = SLIDE_W
    prs.slide_height = SLIDE_H
    return prs


def blank_slide(prs):
    layout = prs.slide_layouts[6]   # completely blank
    return prs.slides.add_slide(layout)


def bg(slide, colour=DARK_BG):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = colour


def box(slide, l, t, w, h, colour, alpha=None):
    shape = slide.shapes.add_shape(1, Inches(l), Inches(t), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = colour
    shape.line.fill.background()
    return shape


def label(slide, text, l, t, w, h, size=18, bold=False, colour=WHITE,
          align=PP_ALIGN.LEFT, italic=False):
    txb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf  = txb.text_frame
    tf.word_wrap = True
    p   = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size   = Pt(size)
    run.font.bold   = bold
    run.font.italic = italic
    run.font.color.rgb = colour
    return txb


def accent_bar(slide, t=0.18, h=0.06):
    box(slide, 0, t, 13.33, h, ACCENT)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — TITLE
# ══════════════════════════════════════════════════════════════════════════════
def slide_title(prs):
    s = blank_slide(prs)
    bg(s)

    # gradient strip top
    box(s, 0, 0, 13.33, 0.5, ACCENT)

    # big headline
    label(s, "SDR Voice Agent", 1.0, 1.2, 11.33, 1.6,
          size=54, bold=True, colour=WHITE, align=PP_ALIGN.CENTER)

    # sub-headline
    label(s, "Signal-triggered AI outbound calls — qualify leads while you sleep",
          1.0, 2.8, 11.33, 0.8, size=22, colour=LIGHT, align=PP_ALIGN.CENTER)

    # divider
    box(s, 4.5, 3.7, 4.33, 0.06, ACCENT)

    # tag line chips
    chips = [("LiveKit", 3.1), ("Groq LLM", 5.2), ("Deepgram", 7.3), ("Free Stack", 9.4)]
    for txt, left in chips:
        box(s, left, 4.1, 1.6, 0.45, CARD_BG)
        label(s, txt, left + 0.1, 4.12, 1.4, 0.4,
              size=13, colour=ACCENT, align=PP_ALIGN.CENTER)

    # footer
    label(s, "Hackathon MVP  ·  June 2026", 0, 6.9, 13.33, 0.4,
          size=12, colour=MUTED, align=PP_ALIGN.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — PROBLEM STATEMENT
# ══════════════════════════════════════════════════════════════════════════════
def slide_problem(prs):
    s = blank_slide(prs)
    bg(s)
    accent_bar(s)

    label(s, "The Problem", 0.6, 0.35, 6.0, 0.7,
          size=32, bold=True, colour=WHITE)

    # Pain points — left column
    pains = [
        ("🧊  Cold outreach is broken",
         "< 2 % connect rate on cold calls.\nSDRs spend 6+ hours/day dialling to book 1 meeting."),
        ("💸  Human SDRs are expensive",
         "$60K – $90K fully-loaded cost per rep.\nHigh churn. Inconsistent messaging."),
        ("⏰  Signals go stale fast",
         "A funding round or regulatory filing is hot for 48 hours.\nManual teams can't react in time."),
    ]
    for i, (title, body) in enumerate(pains):
        top = 1.25 + i * 1.65
        box(s, 0.6, top, 6.0, 1.4, CARD_BG)
        label(s, title, 0.75, top + 0.08, 5.8, 0.45,
              size=15, bold=True, colour=ACCENT)
        label(s, body, 0.75, top + 0.5, 5.7, 0.85,
              size=13, colour=LIGHT)

    # Stat callout — right
    stats = [
        ("< 2%",    "average cold-call\nconnect rate"),
        ("$80K",    "fully-loaded cost\nper SDR/year"),
        ("48 hrs",  "before a trigger\nsignal goes stale"),
    ]
    for i, (num, desc) in enumerate(stats):
        top = 1.25 + i * 1.65
        box(s, 7.2, top, 5.5, 1.4, CARD_BG)
        label(s, num, 7.3, top + 0.08, 2.0, 0.7,
              size=38, bold=True, colour=ACCENT2)
        label(s, desc, 9.35, top + 0.22, 3.2, 0.9,
              size=14, colour=LIGHT)

    label(s, "Problem Statement", 0, 6.9, 13.33, 0.4,
          size=11, colour=MUTED, align=PP_ALIGN.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — SOLUTION
# ══════════════════════════════════════════════════════════════════════════════
def slide_solution(prs):
    s = blank_slide(prs)
    bg(s)
    accent_bar(s)

    label(s, "The Solution", 0.6, 0.35, 10.0, 0.7,
          size=32, bold=True, colour=WHITE)

    label(s, "An AI SDR that detects intent signals, calls prospects automatically,\n"
             "and books meetings — without asking for an email.",
          0.6, 1.1, 12.1, 0.8, size=17, colour=LIGHT)

    pillars = [
        (ACCENT,  "Signal-Triggered",
         "Monitors regulatory filings, funding rounds, hiring signals & press releases."
         " Calls within minutes of detection."),
        (ACCENT2, "Conversational AI",
         "Groq LLM (llama-3.1-8b-instant) drives natural single-sentence turns."
         " Strict 12-word rule keeps calls tight."),
        (RGBColor(0xF5, 0xA6, 0x23), "Zero-friction Booking",
         "Prospect details are on file. When they agree to meet, the invite goes out"
         " immediately — no email ask."),
        (RGBColor(0xE0, 0x50, 0x80), "Free Stack",
         "LiveKit · Groq · Deepgram · SQLite. $0/month for hackathon scale."
         " Swappable to paid tiers for production."),
    ]
    for i, (colour, title, body) in enumerate(pillars):
        col = i % 2
        row = i // 2
        l = 0.6 + col * 6.3
        t = 2.15 + row * 2.0
        box(s, l, t, 5.9, 1.75, CARD_BG)
        box(s, l, t, 0.12, 1.75, colour)
        label(s, title, l + 0.25, t + 0.1, 5.4, 0.45,
              size=16, bold=True, colour=colour)
        label(s, body, l + 0.25, t + 0.55, 5.5, 1.1,
              size=13, colour=LIGHT)

    label(s, "Solution", 0, 6.9, 13.33, 0.4,
          size=11, colour=MUTED, align=PP_ALIGN.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 4 — ARCHITECTURE OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
def slide_architecture(prs):
    s = blank_slide(prs)
    bg(s)
    accent_bar(s)

    label(s, "Architecture Overview", 0.6, 0.35, 10.0, 0.7,
          size=32, bold=True, colour=WHITE)

    # Pipeline row — top half
    pipeline = [
        (ACCENT,              "LiveKit\nWebRTC",   "Browser transport\naudio in/out"),
        (RGBColor(0x9B,0x59,0xF4), "Deepgram\nSTT",  "nova-2 model\n100 ms endpointing"),
        (RGBColor(0xF5,0xA6,0x23), "Groq LLM",       "llama-3.1-8b-instant\n~200 ms latency"),
        (ACCENT2,             "Deepgram\nTTS",     "Aura-Asteria\nstreaming audio"),
        (ACCENT,              "LiveKit\nOutput",   "Audio delivered\nto browser"),
    ]
    arrow_colour = MUTED
    for i, (colour, title, sub) in enumerate(pipeline):
        l = 0.5 + i * 2.45
        box(s, l, 1.25, 2.1, 1.5, CARD_BG)
        box(s, l, 1.25, 2.1, 0.08, colour)
        label(s, title, l + 0.08, 1.35, 1.95, 0.55,
              size=14, bold=True, colour=colour, align=PP_ALIGN.CENTER)
        label(s, sub, l + 0.05, 1.92, 2.0, 0.75,
              size=11, colour=LIGHT, align=PP_ALIGN.CENTER)
        if i < len(pipeline) - 1:
            label(s, "→", l + 2.12, 1.8, 0.3, 0.4,
                  size=20, bold=True, colour=MUTED)

    # SDRTurnPolicy box below — central
    box(s, 3.0, 3.05, 7.33, 1.3, RGBColor(0x1A, 0x22, 0x3A))
    box(s, 3.0, 3.05, 7.33, 0.08, ACCENT2)
    label(s, "SDRTurnPolicy  (FrameProcessor)", 3.1, 3.15, 7.0, 0.45,
          size=15, bold=True, colour=ACCENT2)
    label(s,
          "_check_agreement()  ·  _call_llm()  ·  _detect_outcome()  ·  flush_transcript()",
          3.1, 3.58, 7.1, 0.35, size=12, colour=LIGHT)
    label(s,
          "asyncio.Lock prevents concurrent turns  ·  httpx client reused  ·  Groq warmup on start",
          3.1, 3.88, 7.1, 0.35, size=11, colour=MUTED)

    # Data layer
    stores = [
        (0.5,  "Signal DB\n(SQLite)",   "Regulatory / hiring\nsignals"),
        (3.2,  "Call DB\n(SQLite)",     "Transcript + outcome\n+ booking status"),
        (5.9,  "Portal\n(FastAPI)",     "Review UI + notes\n+ outcome tags"),
        (8.6,  "Cal.com\n(optional)",   "Calendar invite\nwhen booked"),
        (11.1, "Resend\n(optional)",    "Follow-up email\nafter call"),
    ]
    for l, title, sub in stores:
        box(s, l, 4.65, 2.0, 1.35, CARD_BG)
        label(s, title, l + 0.05, 4.72, 1.9, 0.5,
              size=13, bold=True, colour=ACCENT, align=PP_ALIGN.CENTER)
        label(s, sub, l + 0.05, 5.2, 1.9, 0.7,
              size=11, colour=LIGHT, align=PP_ALIGN.CENTER)

    label(s, "Architecture Overview", 0, 6.9, 13.33, 0.4,
          size=11, colour=MUTED, align=PP_ALIGN.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 5 — HOW A CALL WORKS
# ══════════════════════════════════════════════════════════════════════════════
def slide_call_flow(prs):
    s = blank_slide(prs)
    bg(s)
    accent_bar(s)

    label(s, "How a Call Works", 0.6, 0.35, 10.0, 0.7,
          size=32, bold=True, colour=WHITE)

    steps = [
        (ACCENT,              "1  Signal Detected",
         "System monitors SEC filings, Crunchbase, job boards & press.\n"
         "Prospect scored — if above threshold, queued for a call."),
        (RGBColor(0x9B,0x59,0xF4), "2  Room Created",
         "FastAPI mints a LiveKit JWT token and opens a WebRTC room.\n"
         "Browser joins — pipeline spins up with STT + LLM + TTS."),
        (ACCENT2,             "3  AI Opens",
         "\"Hi Alex, calling about Rippling's recent funding round — got 60 seconds?\"\n"
         "Groq connection pre-warmed so first response is <250 ms."),
        (RGBColor(0xF5,0xA6,0x23), "4  Turn Loop",
         "Deepgram fires final transcript → SDRTurnPolicy → Groq → Deepgram TTS.\n"
         "Bot-speaking gate blocks echo. Lock prevents concurrent turns."),
        (RGBColor(0xE0,0x50,0x80), "5  Booking / Close",
         "Agent asks for 15-min meeting. On \"yes\" → sends calendar invite immediately.\n"
         "No email ask — details already on file. Outcome flushed to DB."),
    ]
    for i, (colour, title, body) in enumerate(steps):
        top = 1.25 + i * 1.02
        box(s, 0.5, top, 0.55, 0.82, colour)
        label(s, str(i+1), 0.5, top + 0.12, 0.55, 0.55,
              size=22, bold=True, colour=DARK_BG, align=PP_ALIGN.CENTER)
        box(s, 1.15, top, 11.6, 0.82, CARD_BG)
        label(s, title, 1.3, top + 0.04, 4.0, 0.38,
              size=14, bold=True, colour=colour)
        label(s, body, 1.3, top + 0.38, 11.2, 0.42,
              size=12, colour=LIGHT)

    label(s, "Call Flow", 0, 6.9, 13.33, 0.4,
          size=11, colour=MUTED, align=PP_ALIGN.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 6 — LATENCY BREAKDOWN
# ══════════════════════════════════════════════════════════════════════════════
def slide_latency(prs):
    s = blank_slide(prs)
    bg(s)
    accent_bar(s)

    label(s, "Response Latency  (measured, not estimated)", 0.6, 0.35, 12.0, 0.7,
          size=28, bold=True, colour=WHITE)

    # Bar chart — manual
    bars = [
        ("STT endpointing",         100,  ACCENT),
        ("Groq LLM (warmed)",        215,  ACCENT2),
        ("Deepgram TTS TTFB",        300,  RGBColor(0xF5,0xA6,0x23)),
        ("Pipeline frame overhead",   50,  MUTED),
    ]
    total = sum(v for _, v, _ in bars)
    max_w  = 8.0   # inches for max bar
    scale  = max_w / max(v for _, v, _ in bars)

    label(s, "Stage", 0.6, 1.2, 3.5, 0.4, size=13, bold=True, colour=MUTED)
    label(s, "ms", 11.8, 1.2, 1.0, 0.4, size=13, bold=True, colour=MUTED, align=PP_ALIGN.RIGHT)

    for i, (name, ms, colour) in enumerate(bars):
        top = 1.75 + i * 0.95
        label(s, name, 0.6, top + 0.15, 3.1, 0.5, size=14, colour=LIGHT)
        w = ms * scale
        box(s, 3.8, top + 0.08, w, 0.55, colour)
        label(s, f"{ms} ms", 3.9 + w, top + 0.15, 1.5, 0.4,
              size=14, bold=True, colour=colour)

    # Divider + total
    box(s, 3.8, 5.55, 8.0, 0.04, MUTED)
    label(s, f"Total felt latency", 0.6, 5.65, 3.1, 0.5, size=16, bold=True, colour=WHITE)
    box(s, 3.8, 5.62, total * scale, 0.6, RGBColor(0x1A, 0x22, 0x3A))
    label(s, f"~{total} ms", 3.9 + total * scale, 5.67, 2.0, 0.5,
          size=20, bold=True, colour=ACCENT2)

    label(s, "* First call adds ~800 ms (Groq TCP cold start) — eliminated by connection warmup on pipeline start.",
          0.6, 6.5, 12.0, 0.4, size=11, colour=MUTED, italic=True)

    label(s, "Latency Profile", 0, 6.9, 13.33, 0.4,
          size=11, colour=MUTED, align=PP_ALIGN.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 7 — PRODUCT ROADMAP
# ══════════════════════════════════════════════════════════════════════════════
def slide_roadmap(prs):
    s = blank_slide(prs)
    bg(s)
    accent_bar(s)

    label(s, "Product Roadmap", 0.6, 0.35, 10.0, 0.7,
          size=32, bold=True, colour=WHITE)

    phases = [
        (ACCENT2,             "v1  Hackathon MVP",  "NOW",
         ["Browser WebRTC via LiveKit",
          "Groq LLM + Deepgram STT/TTS",
          "Signal-triggered opener",
          "Call review portal",
          "Zero-email booking flow"]),
        (ACCENT,              "v2  Outbound Phone", "Q3 2026",
         ["Twilio / Vapi outbound PSTN calls",
          "Call window scheduling (8 AM–9 PM)",
          "Max 2 attempts per prospect",
          "Voicemail drop support",
          "Live dashboard & queue management"]),
        (RGBColor(0xF5,0xA6,0x23), "v3  Intelligence",  "Q4 2026",
         ["Cal.com auto-invite on booking",
          "Resend email follow-up sequence",
          "Multi-signal scoring engine",
          "Prospect enrichment (LinkedIn, Clay)",
          "A/B opener testing framework"]),
        (RGBColor(0xE0,0x50,0x80), "v4  Scale",         "Q1 2027",
         ["CRM sync (Salesforce / HubSpot)",
          "Multi-language voices",
          "Whisper-based local STT fallback",
          "Concurrency: 50+ parallel calls",
          "SOC 2 compliance + audit log"]),
    ]
    for i, (colour, title, when, items) in enumerate(phases):
        l = 0.4 + i * 3.22
        box(s, l, 1.2, 3.0, 5.55, CARD_BG)
        box(s, l, 1.2, 3.0, 0.08, colour)
        label(s, title, l + 0.12, 1.3, 2.76, 0.5,
              size=14, bold=True, colour=colour)
        label(s, when, l + 0.12, 1.78, 2.76, 0.38,
              size=12, colour=MUTED, italic=True)
        for j, item in enumerate(items):
            label(s, f"• {item}", l + 0.12, 2.28 + j * 0.82, 2.8, 0.72,
                  size=12, colour=LIGHT)

    label(s, "Roadmap", 0, 6.9, 13.33, 0.4,
          size=11, colour=MUTED, align=PP_ALIGN.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 8 — TECH STACK
# ══════════════════════════════════════════════════════════════════════════════
def slide_stack(prs):
    s = blank_slide(prs)
    bg(s)
    accent_bar(s)

    label(s, "Tech Stack  —  Entirely Free Tier", 0.6, 0.35, 12.0, 0.7,
          size=32, bold=True, colour=WHITE)

    rows = [
        ("Transport",     "LiveKit",       "Free cloud tier · WebRTC browser SDK · JWT auth"),
        ("STT",           "Deepgram",      "nova-2 · 12K minutes/year free · 100 ms endpointing"),
        ("LLM",           "Groq",          "llama-3.1-8b-instant · ~200 ms · free tier"),
        ("TTS",           "Deepgram Aura", "aura-asteria-en · streaming · same free quota as STT"),
        ("Backend",       "FastAPI",       "Python 3.12 · Uvicorn · async throughout"),
        ("Database",      "SQLite",        "aiosqlite · zero ops · swappable to Postgres"),
        ("Pipeline",      "Pipecat",       "FrameProcessor graph · VAD via Silero · asyncio"),
        ("Hosting",       "localhost",     "Hackathon demo — CapRover / Railway for production"),
    ]
    col_w = [2.0, 2.4, 7.5]
    col_x = [0.5, 2.6, 5.1]
    headers = ["Layer", "Provider", "Details"]
    for ci, (h, cx) in enumerate(zip(headers, col_x)):
        label(s, h, cx, 1.2, col_w[ci], 0.4,
              size=13, bold=True, colour=MUTED)

    for ri, (layer, provider, detail) in enumerate(rows):
        top  = 1.72 + ri * 0.58
        rowc = CARD_BG if ri % 2 == 0 else DARK_BG
        box(s, 0.5, top, 12.33, 0.52, rowc)
        label(s, layer,    col_x[0], top + 0.07, col_w[0], 0.4, size=13, colour=MUTED)
        label(s, provider, col_x[1], top + 0.07, col_w[1], 0.4, size=13, bold=True, colour=ACCENT)
        label(s, detail,   col_x[2], top + 0.07, col_w[2], 0.4, size=13, colour=LIGHT)

    label(s, "Stack", 0, 6.9, 13.33, 0.4,
          size=11, colour=MUTED, align=PP_ALIGN.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 9 — CLOSING / NEXT STEPS
# ══════════════════════════════════════════════════════════════════════════════
def slide_close(prs):
    s = blank_slide(prs)
    bg(s)
    box(s, 0, 0, 13.33, 0.5, ACCENT)

    label(s, "What's Next", 1.0, 0.8, 11.33, 1.0,
          size=44, bold=True, colour=WHITE, align=PP_ALIGN.CENTER)

    next_steps = [
        (ACCENT2,             "Outbound Phone",
         "Wire Twilio / Vapi for real PSTN outbound calls\nto prospect mobile numbers."),
        (ACCENT,              "Calendar Booking",
         "Auto-send Cal.com invite the moment prospect\nagrees — zero manual follow-up."),
        (RGBColor(0xF5,0xA6,0x23), "Signal Pipeline",
         "Expand beyond SEC/hiring to LinkedIn activity,\nG2 reviews, intent data providers."),
        (RGBColor(0xE0,0x50,0x80), "CRM Integration",
         "Push booked meetings + transcript directly into\nSalesforce or HubSpot deals."),
    ]
    for i, (colour, title, body) in enumerate(next_steps):
        col = i % 2
        row = i // 2
        l = 0.8 + col * 6.2
        t = 2.1 + row * 2.2
        box(s, l, t, 5.7, 1.85, CARD_BG)
        box(s, l, t, 0.1, 1.85, colour)
        label(s, title, l + 0.25, t + 0.12, 5.2, 0.45,
              size=16, bold=True, colour=colour)
        label(s, body, l + 0.25, t + 0.58, 5.2, 1.1,
              size=13, colour=LIGHT)

    label(s, "github.com/nsharma1972/sdr-voice-agent", 0, 6.9, 13.33, 0.4,
          size=12, colour=MUTED, align=PP_ALIGN.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
# BUILD
# ══════════════════════════════════════════════════════════════════════════════
def main():
    prs = new_prs()
    slide_title(prs)
    slide_problem(prs)
    slide_solution(prs)
    slide_architecture(prs)
    slide_call_flow(prs)
    slide_latency(prs)
    slide_roadmap(prs)
    slide_stack(prs)
    slide_close(prs)
    out = "/Users/narendrasharma/projects/sdr-voice-agent/SDR_Voice_Agent.pptx"
    prs.save(out)
    print(f"Saved → {out}")


if __name__ == "__main__":
    main()
