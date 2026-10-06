# AI assistant

## Status: Sprint 16 — AI consultation and booking agent, with safety, a reviewed knowledge library and an evaluation suite

The patient chat (`/consultation` in the app, `POST /conversations/{id}/chat`
in the API) runs a short preliminary consultation: follow-up questions,
then a preliminary assessment with a suggested specialty. It never
diagnoses, prescribes or books.

## How one message is handled

```
patient message
   │
   ├─ limits: length ≤ CHAT_MAX_MESSAGE_CHARS, ≤ CHAT_MESSAGES_PER_HOUR per patient   → 422 / 429
   ├─ safety screen (plain code, EN + AR + Egyptian)            app/workflows/safety.py
   ├─ save the patient's message (committed before any model call)
   │
   ├─ HIGH risk ──► fixed emergency message (call 123), conversation → escalated,
   │                SafetyEvent requires_human. The model is NOT called.
   │
   └─ otherwise ──► consultation checklist: what's known/missing  app/workflows/consultation.py
                    knowledge search (approved passages only)    app/rag/retrieval.py, see rag.md
                    model (structured output)                   app/agents/llm.py
                     │  system prompt, versioned                app/prompts/chat.py
                     │  last CHAT_HISTORY_MESSAGES turns, text only
                     ├─ MEDIUM rule match → fixed caution appended in code
                     ├─ model says "high" → escalate + urgent-care line, no booking suggestion
                     ├─ model fails → polite fallback message (degraded=true), never a 500
                     ├─ citations → "Sources" (only passages actually given to the model)
                     └─ save reply with provider, model, prompt_version, risk, suggestion,
                        sources and the retrieved passages (for evaluation)
```

The orchestration is plain Python (`app/workflows/chat.py`), not
LangGraph: this flow is a fixed sequence, which is simpler to read,
test and audit. A graph framework can come in with the Booking Agent
(Sprint 10) if the flow starts branching on tool calls.

## The consultation (Sprint 9)

The platform, not the model, runs the checklist; the model does the
talking and the extracting.

- Required details, always asked in this order: **concern → body area →
  duration → symptoms** (an explicit "no symptoms" counts as an answer).
  Optional, when relevant: what they tried, goal, pregnancy/breastfeeding,
  medicines/allergies.
- Each turn the model gets a "Consultation state" developer message
  (known details, what's missing, the one detail to ask about next) and
  returns `intake_update` with details from the patient's latest message
  only. The platform merges them into the conversation's `intakes` row
  (lists are combined; a null never erases a known value).
- The model may return an `assessment` (patient-facing summary, suggested
  specialty, urgency routine/soon/urgent, what to prepare, what to watch
  for). **The platform accepts it only when nothing required is missing,
  or after 6 patient messages** (so someone who can't answer everything
  still gets guidance). A premature assessment is dropped and logged.
  Once accepted the intake is `complete`, and later assessments are
  ignored.
- The suggested specialty comes only from the accepted assessment. This
  replaced the fixed concern → specialty lookup the app used before.
- The app shows the assessment as a card, so the model's reply only
  introduces it (no duplicated summary).
- An `urgent` assessment raises the safety level to at least medium; a
  model-rated emergency suppresses the assessment and booking buttons.
- If the safety rules detect pregnancy/breastfeeding, it's written into
  the intake in code and the model is told.
- Emergencies create no intake: they never reach the model.

The app shows a progress bar (4 details), then a summary card with next
steps (find a slot, browse doctors), and a full summary page at
`/consultation/result?conversation=<id>`. Patients read their own intake
via `GET /intakes?conversation_id=…`.

## The booking agent (Sprint 10)

"Book me tomorrow with a dermatologist at 5 PM in Cairo" works at any
point in the chat (also "yes" to the assistant's offer, or the summary
card's "Find me a slot"). Code: `app/workflows/booking_agent.py`.

**The model only understands; the platform does the rest.**

1. The model fills `booking_request` (specialty, city, date range,
   morning/afternoon/evening, preferred HH:MM, doctor name). It's told
   today's date in Egypt time so "tomorrow" resolves correctly.
2. The platform validates it: unreadable dates are ignored, no past
   dates, at most a 30-day window, times must be real. A missing specialty
   falls back to the consultation's assessment.
3. It searches real **bookable** slots (verified, active doctors; active
   clinics; not booked, held or past), filtering time of day in the
   clinics' time zone (`CLINIC_TIMEZONE`, default Africa/Cairo).
4. It ranks them (closest to the preferred time, else soonest; one option
   per doctor before a second one) and offers up to 3.
5. If nothing matches, it relaxes step by step (any time of day → a
   14-day window → any city) and says it did.
6. **The platform writes the reply**, not the model, so the model can
   never state a time, a doctor or availability that doesn't exist.

**Nothing is booked by the AI.** The patient taps "Reserve" on an option:
`POST /conversations/{id}/booking/reserve` places the usual 10-minute
payment-step hold, and only for slots the agent actually offered in that
conversation (else 404); the reservation is recorded in the transcript.
The appointment is created only when the patient presses "Pay & Confirm"
on the payment screen. Typing "yes, book it" can't book anything.

No booking options are offered in a turn the model rates as an
emergency. This is deliberately not a free-form tool-calling loop: the
model picks the (only) tool and its arguments through structured output,
and the platform validates and runs it, in line with the project's
workflow-first principle (docs/architecture.md).

## Safety rules

`app/workflows/safety.py` screens every patient message before any
model sees it. Messages are normalized first (Arabic letter variants,
diacritics, Arabic-Indic digits).

| Level | Rules | What happens |
|---|---|---|
| HIGH | trouble breathing / throat or tongue swelling; severe allergic reaction; vision loss; vision change, skin turning white/blue/grey, or severe pain **after an injection** (possible vascular occlusion); chest pain, fainting, seizure; stroke signs; severe skin reaction with fever; self-harm | Fixed emergency message (self-harm has its own wording), escalation, human alerted, no model call |
| MEDIUM | infection signs after a procedure; changing mole; pregnancy/breastfeeding; under 18; burn after a treatment | Model replies, informed of the flag; fixed caution appended; SafetyEvent logged |

The rules lean towards flagging: a false alarm costs one cautious
message, a missed emergency can cost sight. `tests/test_safety_rules.py`
holds positive, negative and Arabic cases, including false positives
found while writing them ("مش مستحمل" is not pregnancy; "I'm 2 weeks
after filler" is not a toddler).

**Before launch, a clinician must review the rules and the fixed
messages.** Emergency number used: 123 (Egypt ambulance).

## The model

- Provider interface `LLMProvider` (`app/agents/llm.py`). Implementations:
  - `OpenAIProvider`: the OpenAI Responses API with **structured output**
    (`AssistantDraft` in `app/agents/schemas.py`: reply, intake_update,
    assessment, booking_request, risk_level, cited_sources), `store=False` (the provider keeps
    no copy) and a hashed user id as `safety_identifier`.
  - `OllamaProvider`: a local model served by [Ollama](https://ollama.com),
    free and with no token budget to run out. Calls Ollama's `/api/chat`
    with the same `AssistantDraft` JSON schema as `format`. Local
    development and demos only. On a laptop with a 4 GB GPU, `qwen2.5:3b`
    answers in ~20 s and `qwen2.5:7b` in ~1 min (each reply is ~240 tokens
    of JSON); the knowledge search keeps using the offline demo embedder.
  - `DemoProvider` (`app/agents/demo_llm.py`): deterministic and offline,
    for local development and tests. The UI shows a "Demo mode" badge.
- **Only message text is sent.** No names, phone numbers, emails or ids
  (tested in `test_chat_api.py`).
- Configuration (`.env`):

  | Variable | Default | Notes |
  |---|---|---|
  | `AI_PROVIDER` | `demo` | `openai`, `ollama` or `demo`. Must be `openai` in staging/production (startup check) |
  | `OLLAMA_BASE_URL` | `http://localhost:11434` | `http://host.docker.internal:11434` from inside Docker |
  | `OLLAMA_MODEL` | `qwen2.5:3b` | Any model from `ollama list` |
  | `OLLAMA_NUM_CTX` | 8192 | Context window, in tokens |
  | `OPENAI_API_KEY` | – | Required for `openai` |
  | `OPENAI_MODEL` | – | Required for `openai`; no default on purpose, so the model is chosen and pinned deliberately |
  | `OPENAI_EMBEDDING_MODEL` | – | Required for `openai`; knowledge search embeddings (see [`rag.md`](rag.md)) |
  | `AI_TIMEOUT_SECONDS` | 30 | Use ~180 with `ollama` |
  | `CLINIC_TIMEZONE` | `Africa/Cairo` | Local time for booking requests and time-of-day filters |
  | `CHAT_MAX_MESSAGE_CHARS` | 2000 | |
  | `CHAT_MESSAGES_PER_HOUR` | 30 | Per patient |
  | `CHAT_HISTORY_MESSAGES` | 20 | Turns sent to the model |

- The system prompt lives in `app/prompts/chat.py` with
  `PROMPT_VERSION`; every assistant message stores the version that
  produced it. Change the version whenever the prompt changes.

## Consent

Before a patient's first conversation they tick one box: the chat is
preliminary guidance, not a diagnosis, and messages are processed by an
AI service. It's stored as two versioned `patient_consents` rows
(`medical_advice_disclaimer`, `data_processing`, version
`chat-2026-09-v1`). Changing `CHAT_CONSENT_VERSION` asks everyone again.

## Escalations

Every flagged message creates a `safety_events` row. Admins list and
resolve them at `GET /safety-events` and `PATCH /safety-events/{id}`
until the admin dashboard exists (Sprint 14). There is no automatic
notification to staff yet (Sprint 15).

## Not done yet

- ~~A real conversation evaluation set~~ — done in Sprint 16: English and
  Arabic suites for red-flag screening, extraction, booking and retrieval,
  with thresholds that gate a release (`docs/evaluation.md`). Red-team
  prompts and groundedness scoring are still open, and the model itself has
  not been run against a real OpenAI key in this environment (the
  provider's request shape is unit-tested with a stub).
- Streaming replies (the patient sees a typing indicator meanwhile).
- Attaching the consultation summary to a booking, so the doctor sees it
  (with the doctor dashboard, Sprint 12).
