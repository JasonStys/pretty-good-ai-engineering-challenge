# Video walkthrough and AI-debug recording guide

## Main walkthrough (target 2:40)

**0:00–0:20 — Outcome.** On camera: “I built a safety-bounded synthetic patient that automatically
calls Pretty Good AI's assessment line, handles interruptions in realtime, and produces a recording,
both-side transcript, resource metrics, and evidence-backed QA report for every scenario.” Show the
best call artifact and play a short natural exchange.

**0:20–0:55 — Architecture.** Show `docs/architecture.md`. Explain Twilio's recorded call and μ-law
Media Stream, the small FastAPI relay, OpenAI Realtime semantic turn detection, and post-call
diarization/QA. Point out that audio is not transcoded and the hot path uses one bounded buffer.

**0:55–1:25 — Safety.** Open `constants.py`, `config.py`, and `telephony.py`. Show the hard-coded
assessment number and the two enforcement points. Mention signed WebSockets, synthetic identities,
message limits, sequential calls, atomic files, and no local GPU/model weights.

**1:25–2:00 — Evaluation.** Show the 12-scenario YAML, then one recording, transcript, QA report, and
the aggregate bug report. Use one concrete issue: evidence, impact, expected behavior, and exact
reproduction.

**2:00–2:30 — Verification.** Show the GitHub Actions page and the spreadsheets. State: 54 tests,
91.47% coverage, strict type check, zero Bandit findings, zero known dependency vulnerabilities,
average cyclomatic complexity A, and performance budgets. Do not imply the live gate passed unless it
actually did.

**2:30–2:40 — Close.** Summarize the strongest result and one next iteration based on the calls.

## Separate AI-debug video

Record a genuine issue discovered during the build or live run. A good current example is the strict
scenario-loader failure: unquoted ISO dates were converted by YAML to date objects, violating the
string-only synthetic-fact schema. Show the failing validation trace, explain why the strict boundary
was correct, show the quoted YAML fix and regression suite, then run the test. For a stronger
conversation-specific video, use a real failed call or poor turn and show the transcript/audio,
hypothesis, prompt or relay change, and before/after result. Never stage a fake live-call failure.

## Recording checklist

- Webcam and Jason's own narration are visible/audible.
- No API key, Twilio token, account SID, browser password, or billing data appears.
- Main video is public and no longer than three minutes.
- Debug video is separate and public.
- Both links are added to README and tested in a private/incognito window.
