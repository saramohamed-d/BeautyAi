# AI evaluation

## Status: Sprint 16 complete

A command that answers "does the AI still do its job?" with numbers
instead of a judgement:

```bash
cd backend
python -m app.evaluation.cli run                    # every suite
python -m app.evaluation.cli run --suite safety     # one suite
python -m app.evaluation.cli run --report out.json  # machine-readable report
python -m app.evaluation.cli check                  # validate the datasets only
```

It exits non-zero when a threshold isn't met, so it can gate a release.

## The four suites

| Suite | What it drives | What it measures |
|---|---|---|
| **safety** | `app/workflows/safety.py` (no model, no database) | Emergency recall, overall accuracy, false-alarm rate |
| **extraction** | The configured AI provider | Whether concern, body area, duration and symptoms are taken out of a patient's message |
| **booking** | The provider + `criteria_from_request` | Whether a message is a booking request, and whether the derived criteria are right |
| **retrieval** | The real hybrid search (needs the database and ingested knowledge) | Recall@3 of the right article, and whether anything came back at all |

Every suite runs the **real code path**, not a copy: the same rules, the
same provider, the same search. An evaluation that tests a mock proves
nothing. Cases are in `data/evaluation/*.jsonl`, hand-written in English
and Arabic (Modern Standard and Egyptian colloquial), and reviewed like
code.

## Thresholds

| Suite | Metric | Bar | Why |
|---|---|---|---|
| safety | `emergency_recall` | **1.00** | A missed vascular occlusion can cost a patient their sight. There is no acceptable shortfall here, and no provider gets a lower bar |
| safety | `accuracy` | 0.90 | Getting the level right, overall |
| safety | `false_alarm_rate` | ≤ 0.10 | Alarms on ordinary questions train people to ignore them |
| extraction | `field_accuracy` / `concern_accuracy` | 0.80 / 0.90 | The consultation is useless if the concern is wrong |
| booking | `intent_accuracy` / `field_accuracy` | 0.95 / 0.80 | Mistaking a question for a booking wastes the patient's time |
| retrieval | `recall_at_k` (k=3) / `any_result_rate` | 0.80 / 1.00 | An answer with no source is the thing citations exist to prevent |

**The offline stand-ins get one relaxed bar.** With `AI_PROVIDER=demo`
and the demo embedder, `any_result_rate` is held to 0.80 instead of 1.00:
the demo embedder hashes words instead of understanding them, so a
question phrased in words the article doesn't use ("breakouts" for acne)
returns nothing, where real embeddings would find it. Everything else is
held to the same bar, and the report says which profile was used. Model
quality numbers need a real provider:

```bash
AI_PROVIDER=openai OPENAI_API_KEY=… OPENAI_MODEL=… python -m app.evaluation.cli run
```

## What the first run found

Running these suites for the first time exposed real defects, all now
fixed and covered:

- **Six holes in the red-flag rules**: "my tongue is swollen" (the
  pattern matched "swell", not "swollen"), "black skin" after an
  injection (necrosis), Arabic self-harm phrased as "مش عايزة أعيش",
  Arabic blanching as "بقت بيضا", Arabic "مرضعة" for breastfeeding, and
  symptoms that haven't settled days after a procedure. Emergency recall
  was **0.60**; it is now 1.00 with no false alarms.
- **Fever plus spreading redness after a procedure** is now an emergency
  (`spreading_infection`) rather than a caution. *This is a judgement
  call made by the development team and needs clinical sign-off.*
- **A substring bug in the demo extractor**: "it**chin**g" was read as
  the body area "chin". Keyword matching now respects word edges,
  English plurals and Arabic prefixes/suffixes ("الذقن", "احجزيلي").
- **Arabic punctuation broke word edges**: "؟" sits inside the Arabic
  Unicode block, so "الجيزة؟" never matched "الجيزة".
- **Negated symptoms** ("no pain or itching") were recorded as symptoms.
- Missing vocabulary: hair "falling out", "dark patches", "flushed",
  the area "around the eyes", "see a dermatologist" as a booking intent,
  and a named doctor ("book me with Dr Amira") was never extracted.

## What it does not measure

- **Clinical correctness of the advice.** These suites check that the
  right article is retrieved and the right fields are extracted, not
  that the content is medically right. That needs a clinician.
- **Groundedness / hallucination**: whether the reply sticks to the
  retrieved sources isn't scored yet; it needs either a human rater or a
  model-as-judge, and both belong with a real provider.
- **Latency and cost per conversation.**
- **Multi-turn behaviour**: each case is a single message.
- **The safety cases themselves are not clinically reviewed.** They
  encode what the development team believes should be an emergency.

## Adding a case

Append a line to the relevant `data/evaluation/*.jsonl`, run
`python -m app.evaluation.cli check`, then the suite. A case that fails
is either a defect to fix or an expectation to argue with — both belong
in the pull request.
