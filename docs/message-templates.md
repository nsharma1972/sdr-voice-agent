# Outreach Message Templates — Issue #8

Templates the agent uses as context and that humans send as follow-up. Placeholders
are filled from the active `INDUSTRY_PACK` + the fired signal — no vertical is baked
in. Voicemail scripts are written to drop into `src/voice/pipeline.py`.

## Placeholders

| Token | Source |
|---|---|
| `{first_name}` | prospect |
| `{company}` | lead.company_name |
| `{sender}` | sender identity (config) |
| `{product}` | what you sell |
| `{value}` | one-line value statement |
| `{signal_ref}` | short human phrase for the fired signal (e.g. "your Series B", "the new Head of Compliance role") |

**Tone:** direct, specific, one clear ask. Name the *specific* signal in the first
sentence. Voicemails 18–25s, AI identity stated up front, no improvising past script.

Signal codes match `src/signals/base.py`: S1 REGULATORY_ACTION, S2 REGULATORY_FILING,
S3 PRODUCT_CLEARANCE, S4 FUNDING_ROUND, S5 HIRING_SIGNAL, S6 EXEC_INTERVIEW,
S7 PRESS_RELEASE.

---

## S1 — REGULATORY_ACTION

**Subject:** `{first_name}, a thought on {signal_ref}`

**Email (<150 words):**
> Hi {first_name},
> Saw {signal_ref}. The scramble after this is usually less about the finding and
> more about proving controls are now in place — fast. {product} helps teams like
> {company} {value}, so the response holds up to scrutiny instead of becoming a
> fire drill.
> Worth 20 minutes to compare notes on how peers are handling it?
> — {sender}

**LinkedIn (<300 chars):**
> {first_name} — saw {signal_ref}. We help teams turn that into a closed-out,
> defensible response fast. Open to a quick call?

**Voicemail (~22s):**
> "Hi {first_name}, this is an AI assistant calling for {sender}. I'm following up
> on {signal_ref}. We help teams {value} — usually faster than expected. I'll send
> a short note. Thanks."

---

## S2 — REGULATORY_FILING

**Subject:** `{first_name} — re: {signal_ref}`

**Email:**
> Hi {first_name},
> Noticed {signal_ref}. Disclosures like that usually surface a backlog of evidence
> work that lands on a small team. {product} {value}, which keeps that continuous
> instead of a quarter-end crunch.
> Open to a 20-minute call?
> — {sender}

**LinkedIn:**
> {first_name}, saw {signal_ref}. Curious how you're handling the evidence side —
> we make it continuous. Worth a quick chat?

**Voicemail (~20s):**
> "Hi {first_name}, AI assistant for {sender}. Quick follow-up on {signal_ref}. We
> help teams {value}. Sending a note now. Thanks."

---

## S3 — PRODUCT_CLEARANCE

**Subject:** `Congrats on {signal_ref}, {first_name}`

**Email:**
> Hi {first_name},
> Congrats on {signal_ref}. Right after a launch/clearance is when post-market and
> support load spikes and small teams get stretched. {product} {value} so the win
> doesn't turn into a bottleneck.
> Worth 20 minutes?
> — {sender}

**LinkedIn:**
> Congrats on {signal_ref}, {first_name}! That's usually when {value} starts to
> matter. Quick call?

**Voicemail (~20s):**
> "Hi {first_name}, AI assistant for {sender}. Congrats on {signal_ref}. We help
> teams {value} right after that milestone. I'll send a note. Thanks."

---

## S4 — FUNDING_ROUND

**Subject:** `{first_name}, a thought on {signal_ref}`

**Email:**
> Hi {first_name},
> Congrats on {signal_ref}. Growth at that stage means more surface area, more
> scrutiny, and a team that's suddenly stretched. {product} {value}, so scaling
> doesn't outrun your controls.
> Worth 20 minutes to see if it's relevant?
> — {sender}

**LinkedIn:**
> Congrats on {signal_ref}, {first_name}! Growth like that usually surfaces exactly
> what we solve. Open to a quick call?

**Voicemail (~22s):**
> "Hi {first_name}, AI assistant calling for {sender}. Saw {signal_ref} — congrats.
> Growth like that usually surfaces the problem we solve: {value}. I'll send a note.
> Thanks."

---

## S5 — HIRING_SIGNAL

**Subject:** `{first_name} — saw you're hiring for {signal_ref}`

**Email:**
> Hi {first_name},
> Saw {company} is hiring around {signal_ref} — usually a sign the problem is real
> and budgeted, not theoretical. {product} {value}, which often takes pressure off
> the roles you're trying to fill.
> Worth 20 minutes before the team's fully ramped?
> — {sender}

**LinkedIn:**
> {first_name}, noticed {company}'s hiring around {signal_ref}. We help teams get
> ahead of that work. Quick call?

**Voicemail (~20s):**
> "Hi {first_name}, AI assistant for {sender}. Saw {company} is hiring around
> {signal_ref}. We help with exactly that — {value}. Sending a note. Thanks."

---

## S6 — EXEC_INTERVIEW

**Subject:** `{first_name}, your point on {signal_ref}`

**Email:**
> Hi {first_name},
> Caught {signal_ref} — your take resonated. It's exactly what {product} is built
> for: {value}. Teams like {company} use us for precisely that.
> Would a 20-minute call be worth it to compare notes?
> — {sender}

**LinkedIn:**
> {first_name}, your comments in {signal_ref} hit home — it's what we built for.
> Open to a quick call?

**Voicemail (~22s):**
> "Hi {first_name}, AI assistant for {sender}. Heard your comments in {signal_ref} —
> aligned with what we do: {value}. I'll follow up by email. Thanks."

---

## S7 — PRESS_RELEASE (fallback)

**Subject:** `{first_name} — quick thought`

**Email:**
> Hi {first_name},
> Came across {signal_ref} about {company}. It lined up with something we help with:
> {value}. Worth a short call to see if it's relevant?
> — {sender}

**LinkedIn:**
> {first_name} — saw {signal_ref}. Reminded me of what we do. Quick chat?

**Voicemail (~18s):**
> "Hi {first_name}, AI assistant for {sender}. Following up after {signal_ref}. We
> help with {value}. Sending a quick note. Thanks."

---

## Wiring into the voice layer

These voicemail scripts map 1:1 to the `SIGNAL_OPENERS` keys in
`src/voice/pipeline.py`. Recommended: have the voice layer pull opener + voicemail
from this file keyed by `signal_type`, so message copy lives in one place
(consistent with the industry-agnostic design).
