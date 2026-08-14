# Pretty Good AI Patient Simulator

A Python voice bot that calls **only** Pretty Good AI's assessment line, behaves like a realistic
synthetic patient, records both sides of each call, produces role-labelled transcripts, and turns
conversation evidence into a prioritized QA report.

The design optimizes for the challenge's first gate: coherent, natural voice interaction. Twilio
provides the outbound call, dual-channel recording, and bidirectional 8 kHz μ-law Media Stream.
OpenAI Realtime 2.1 handles low-latency speech-to-speech behavior with semantic turn detection and
barge-in support. The application forwards encoded audio without transcoding, tracks what Twilio
actually played, and stores only a bounded byte buffer plus the short conversation history. After
the call, it downloads MP3 evidence, generates a diarized transcription, evaluates the role-labelled
transcript against the scenario rubric, and emits reproducible bug entries.

## Safety boundary

The only permitted destination is hard-coded as `+18054398008`. It is checked in configuration and
again immediately before Twilio call creation. There is no CLI flag, API parameter, or environment
variable that can bypass the allowlist. All patient identities in `scenarios/default.yaml` are
synthetic; do not add real protected health information.

## Quick start

Prerequisites:

- Python 3.11–3.13
- An OpenAI API key with Realtime and transcription access
- A paid Twilio account and one voice-capable phone number
- A public HTTPS endpoint for this service (a deployment or a tunnel to port 8000)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

Fill in `.env`, expose port `8000` at the exact `PUBLIC_BASE_URL`, then start the bridge:

```bash
pgai-voicebot serve
```

Check the twelve scenarios without loading credentials:

```bash
pgai-voicebot list-scenarios
```

Run one inexpensive smoke call first, listen to it, and adjust the scenario prompt if needed:

```bash
pgai-voicebot call new-patient-scheduling
```

Once the smoke call sounds natural, the complete minimum run is one command:

```bash
pgai-voicebot batch --minimum 10
```

The batch is intentionally sequential. Parallel calls would make listening and cost control harder,
increase the chance of overlapping failures, and provide no scoring benefit.

## Evidence produced per call

```text
artifacts/calls/<run-id>/
├── manifest.json                 # call/recording IDs, status, timestamps, fixed destination
├── recording.mp3                # both sides, challenge-compatible format
├── recording-diarization.json   # independent speaker-labelled ASR evidence
├── transcript.json              # machine-readable, role-labelled conversation
├── transcript.md                # reviewer-friendly conversation
├── qa-report.json               # scores, evidence, issues, and next iteration
└── metrics.json                 # runtime, CPU, RSS, page faults, disk, and hosted-GPU note
```

`artifacts/bug-report.md` aggregates issues across completed calls by severity. Every entry points
back to a run transcript and includes evidence, impact, expected behavior, and reproduction steps.

Before submission, run the same gate used by GitHub Actions:

```bash
pgai-voicebot validate --minimum-calls 10
```

The gate requires ten distinct completed scenarios, one caller number across every call, the exact
assessment destination, an MP3 of plausible size, at least four transcript turns, both conversation
sides, and no common secret formats.

## Scenario coverage

| Scenario | Primary behavior under test |
|---|---|
| `new-patient-scheduling` | Complete scheduling and read-back |
| `reschedule-existing-visit` | Preserve appointment type while moving a visit |
| `cancel-and-waitlist` | Avoid canceling the wrong appointment |
| `routine-refill-request` | Medication/pharmacy accuracy and safe next steps |
| `hours-location-insurance` | Consistent logistics and benefit-verification boundaries |
| `closed-day-boundary` | Reject closed-day scheduling and offer alternatives |
| `urgent-symptom-escalation` | Prompt escalation without diagnosis |
| `privacy-boundary` | Protect another adult's information |
| `interruption-and-correction` | Barge-in, pauses, and date correction |
| `spanish-information-request` | Spanish continuity and interpreter fallback |
| `hearing-accessibility` | Pace, repetition, and plain language |
| `conflicting-demographics` | Privacy-safe identity conflict handling |

## Architecture and design choices

The hot audio path is deliberately small: Twilio sends base64 μ-law packets to FastAPI; the bridge
decodes them into a reusable `bytearray`, flushes roughly 50 ms chunks to the OpenAI Agents SDK, and
base64-encodes returned μ-law audio for Twilio. No resampling, temporary audio files, nested polling
loops, or unbounded queues sit in the conversation path. A hash-indexed scenario catalog gives
expected O(1) lookup, and standard-library/Pydantic models reject invalid states at the network and
configuration boundaries. Cleanup cancels all relay tasks, closes the Realtime session, clears
buffers and playback markers, then writes the final compact transcript.

Twilio Media Streams were chosen over a multi-stage speech-to-text → text model → text-to-speech
pipeline because the rubric prioritizes natural pacing and coherent interruption handling. The
tradeoff is dependency on two paid services and a public WebSocket. Direct SIP was considered, but
Media Streams make the fixed outbound-number policy, dual-channel recording, and evidence download
explicit and easy to audit. See [the detailed architecture](docs/architecture.md),
[security model](docs/security.md), and [research notes](docs/research.md).

## Tests and engineering reports

```bash
python -m pip install -e ".[dev,docs]"
ruff check .
ruff format --check .
mypy src
pytest --cov=pgai_voicebot --cov-report=term-missing --cov-fail-under=90
bandit -c pyproject.toml -r src
python scripts/benchmark.py --output build/reports/performance.json
python scripts/validate_documents.py docs
```

GitHub Actions run these as separate correctness, security, performance, documentation, and
submission-gate workflows. Reports are uploaded as build artifacts and summarized on the workflow
run. The performance report includes wall time, CPU time, peak traced memory, output bytes, empirical
growth, documented Big-O, and the fact that no local GPU is allocated. `metrics.json` also captures
OS page faults where the platform exposes them.

Generated reviewer documents are committed under `docs/`:

| Deliverable | Contents |
|---|---|
| `engineering-report.docx` | Architecture, complexity, efficiency, safety, privacy, and operations |
| `test-validation-report.docx` | Verification results, discovered defect, Actions, and live acceptance |
| `engineering-metrics.xlsx` | Performance, Big-O, resources, complexity, and scenario coverage |
| `test-results.xlsx` | Formula-driven test, security, and CI summaries |
| `performance.md` | Reproducible local benchmark and complexity interpretation |

Current local verification: **54 tests passed**, **91.47% branch-aware coverage**, Ruff clean, mypy
strict clean, Bandit zero findings, dependency audit zero known vulnerabilities, package build pass,
and document/formula validation pass. The live submission gate remains pending until ten genuine
reviewed calls exist; mocked tests are never counted as challenge evidence.

## Cost, privacy, and recording consent

- Twilio and OpenAI usage incurs charges. Run one smoke call before the batch and keep receipts.
- The challenge line is an assessment environment, but call recording laws and Twilio policy still
  apply. Do not repurpose this code for unconsented calls.
- `.env`, raw events, and temporary WAV files are ignored. Never commit credentials.
- Review all recordings and transcripts before publishing. Use only synthetic data.
- The service validates Twilio request signatures by default and exposes only `/healthz` and the
  WebSocket endpoint; interactive API documentation is disabled.

## Primary implementation references

- [OpenAI Agents SDK Realtime Twilio example](https://github.com/openai/openai-agents-python/tree/main/examples/realtime/twilio)
- [OpenAI Realtime Agents guide](https://openai.github.io/openai-agents-python/realtime/guide/)
- [OpenAI GPT-4o Transcribe Diarize](https://developers.openai.com/api/docs/models/gpt-4o-transcribe-diarize)
- [Twilio bidirectional Media Streams](https://www.twilio.com/docs/voice/media-streams)
- [Twilio Call recording options](https://www.twilio.com/docs/voice/api/call-resource)

## License

MIT. The implementation is original and uses the OpenAI Agents SDK and Twilio through their public
APIs; refer to each dependency's license and terms for its own code and service.
