# Submission completion checklist

## Ready now

- [x] Python package, Docker image definition, CLI, 12 synthetic scenarios, and fixed destination.
- [x] Bidirectional Realtime/Twilio bridge with barge-in, playback marks, bounded buffering, and cleanup.
- [x] Dual-channel MP3 download, both-side transcript, independent diarization, QA, bug aggregation,
  runtime metrics, and secret scan.
- [x] 54 tests passing with 91.47% coverage; Ruff, mypy, Bandit, and dependency audit passing.
- [x] CI, security, performance, documentation, and manual live-submission GitHub workflows.
- [x] Markdown, Word, and Excel engineering/test documentation.

## Requires Jason's authenticated/billable accounts and personal recording

- [ ] Reauthenticate GitHub CLI or authorize creation of the public repository under `JasonStys`.
- [ ] Sign in to Twilio, select one voice-capable E.164 caller number, fund the account, and add it to
  `.env` only.
- [ ] Create or select an OpenAI API project with Realtime/transcription access and add its key to
  `.env` only.
- [ ] Deploy the HTTPS/WSS service or run a reviewed public tunnel; verify `/healthz`.
- [ ] Create the Athena test account using synthetic test details and the chosen caller number; do not
  call the confirmation number.
- [ ] Run one smoke call, review audio and cost, then run at least ten distinct 1–3 minute calls.
- [ ] Review all MP3/transcript/QA artifacts, run the submission gate, and commit only reviewed data.
- [ ] Record the public ≤3 minute walkthrough using Jason's voice/webcam.
- [ ] Record the separate public AI-debug video using a genuine failure.
- [ ] Add both video URLs and the bug-report link to README.
- [ ] Complete the challenge submission form and retain receipts for reimbursement.

Do not check an item merely because a mocked test covers its software path. The live evidence gate is
designed to distinguish real call artifacts from the local verification suite.
