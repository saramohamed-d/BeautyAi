# Privacy

## Status: Sprint 17 — data rights implemented, formal review outstanding

BeautyAI handles health-related information about identifiable people in
Egypt, so **Law 151/2018 (the Personal Data Protection Law, "PDPL")**
applies, together with the Ministry of Health's rules for clinics.

**This document is a developer's working review, not legal advice.** A
lawyer familiar with the PDPL and its executive regulations must review
the platform before it serves real patients. The open questions are
listed at the end.

## What the platform holds

| Data | Where | Why |
|---|---|---|
| Name, phone, email, city, date of birth | `patients` | Identifying a patient and contacting them |
| Skin/hair concerns, symptoms, duration, the AI's preliminary assessment | `intakes`, `conversations`, `messages` | The consultation itself |
| Appointments | `appointments` | The booking, and the clinic's record of care |
| Payments (amount, status, gateway reference) | `payments` | Money taken, refunds, accounting |
| Messages sent (reminders, receipts, aftercare) | `notifications` | Proof of what was sent, and when |
| Doctors' licences, degrees, ID documents | `doctor_documents` + `UPLOAD_DIR` | Verifying that doctors are real |
| Consents | `patient_consents` | Recording what was agreed, and when |
| Administrator decisions | `audit_events` | Accountability |

**Card details are never held.** Payment happens on the gateway's own
page; the platform stores an amount, a status and the gateway's reference
(docs/payments.md).

## Rights, and how they work here

| PDPL right | In the product |
|---|---|
| Be informed | The consultation shows what it is and isn't before it starts; every article shows its reviewer |
| Access and portability | **Profile → Your data → Download my data** (`GET /auth/me/data`) returns one JSON document with everything above |
| Rectification | Patients edit their profile; clinics correct their own records |
| Erasure | **Profile → Delete my account** (`POST /auth/me/delete`) — see below |
| Withdraw consent | Notification channels are switched off per channel; the AI consultation can be declined, and the platform is usable without it |
| Object to automated decisions | The AI makes no decision: it suggests a specialty and offers times, a person books, and a doctor diagnoses |

### What deletion actually does

Deleting an account:

- **Erases** the login, the profile's personal details (name, phone,
  email, date of birth, gender, city), and every conversation, message
  and notification belonging to that patient.
- **Keeps, de-identified**, the appointments and payments: a clinic has
  its own obligation to keep records of care given and money taken, and
  the accounts must still balance. The rows stay attached to a profile
  whose identifying fields have been cleared.
- Is **recorded in the audit log**, with what was kept.

The response tells the person exactly how many appointments and payments
were kept, rather than claiming everything was erased.

## Protections in place

- Passwords hashed with bcrypt; refresh tokens and one-time links stored
  only as hashes; access tokens kept in memory in the browser, never in
  `localStorage` (docs/security.md).
- Patients' records are private to them: asking for someone else's
  returns 404, not 403, so the API doesn't confirm it exists.
- Verification documents are never served from a public URL and only
  reach their owner or a platform admin.
- Conversations are private between the patient and the platform;
  doctors and clinics see appointments, not chat transcripts.
- AI requests are sent with a pseudonymous identifier, and the provider
  is asked not to retain them (`store=False`).
- TLS everywhere in production, HSTS, restrictive security headers.

## Retention

Nothing expires automatically yet — that is the main gap. Proposed, to be
confirmed with a lawyer and the clinics:

| Data | Proposed retention |
|---|---|
| Conversations and AI assessments | 24 months after the last message |
| Appointments and payments | 5 years (financial and medical record-keeping) |
| Notifications | 12 months |
| Audit events | 5 years |
| Verification documents | While the doctor is active, plus 12 months |

## Open questions for legal review

1. Does the platform act as controller, processor, or joint controller
   with each clinic? The answer changes what the contracts must say.
2. Whether a data protection officer and registration with the Data
   Protection Centre are required at this scale.
3. Whether the AI consultation content counts as "health data" needing
   explicit separate consent (the platform asks for it anyway).
4. Cross-border transfer: OpenAI and the payment gateway process data
   outside Egypt. The PDPL restricts transfers; what safeguards are
   required?
5. Breach notification timelines and the exact notice wording.
6. The minimum age for using the service without a guardian (the chat
   flags under-18s today, but nothing enforces an age limit).
