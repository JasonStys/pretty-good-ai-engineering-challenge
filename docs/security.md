# Security, privacy, and abuse-resistance model

## Scope and protected assets

This repository is an assessment harness, not a production healthcare system. The protected assets
are service credentials, the Twilio caller number, call recordings, transcripts, account metadata,
and the assessment line. Scenario identities are marked synthetic and contain no real protected
health information. The bot cannot dial a user-supplied number.

## Controls

| Risk | Control | Verification |
|---|---|---|
| Calls to unintended people | Target is hard-coded and checked in configuration and immediately before call creation | Unit tests reject any other E.164 number |
| Forged Media Stream | Twilio signature validation is enabled by default | WebSocket test expects policy close code 1008 |
| Memory exhaustion | 64 KiB frame limit, approximately 50 ms audio buffer, no unbounded queue | Protocol and buffer-flush tests |
| Malformed media | Strict JSON-object and validated-base64 parsing | Negative protocol tests |
| Credential disclosure | Secret types, sanitized errors, `.env` ignore, artifact secret scanner | Submission gate and GitHub secret scanning patterns |
| Partial/corrupt evidence | Same-directory temporary writes followed by atomic replace | Artifact tests |
| Prompt abuse | Patient-only instruction, synthetic facts, no tool access, no medical advice | Prompt and schema tests |
| Resource leakage | Cancel/gather tasks, close Realtime session, clear buffers/markers in `finally` | Full mocked bridge lifecycle test |
| Dependency vulnerability | `pip-audit`, Dependabot, CodeQL, and Bandit workflows | Security workflow |
| Cross-call data mixing | Concurrency semaphore of one and per-run artifact store | App routing and orchestration tests |

## Data handling

- Store only reviewed MP3, transcripts, manifests, QA, and metrics required by the challenge.
- Never place credentials in call metadata, prompts, transcripts, logs, or committed artifacts.
- Review recordings before publishing because voice can be identifying even when scenario facts are
  synthetic.
- Do not use this harness against any other number or without recording consent and applicable legal
  review. The destination guard cannot be disabled through CLI or environment settings.
- Rotate any credential immediately if secret scanning reports a match.

## Threat boundaries and residual risk

Twilio and OpenAI remain external processors, so their account access, retention settings, regional
processing, and agreements must be configured by the account owner. A public WebSocket is required;
TLS termination, rate limiting, access logs, and service-level denial-of-service controls belong at
the hosting edge. Signature validation prevents ordinary forged Twilio sessions but is not a
substitute for patched dependencies or network controls. The program records evidence only for the
assessment number; adapting it for real patients would require a separate privacy, consent, HIPAA,
BAA, retention, access-control, and incident-response review.

## Security verification result

As of 2026-08-14, local Bandit scanning reports zero findings, strict type checking reports zero
errors, the dependency audit reports zero known vulnerabilities after upgrading project-environment
pip to 26.2.1, and 54 tests pass. GitHub Actions rerun these checks on every relevant change and on a
weekly schedule.
