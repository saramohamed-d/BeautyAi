# Evaluation datasets

Hand-written test cases for the AI features, in English and Arabic
(Modern Standard and Egyptian colloquial). One JSONL file per suite; run
them with:

```bash
cd backend
python -m app.evaluation.cli run              # every suite, against the configured provider
python -m app.evaluation.cli run --suite safety
```

See `docs/evaluation.md` for what each suite measures and the thresholds
a run must meet.

**These cases were written by the development team, not by a clinician.**
The safety cases in particular encode what *should* be treated as an
emergency; a dermatologist must review them (and the rules they test)
before launch.
