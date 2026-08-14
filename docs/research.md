# Research notes and source decisions

## Company and challenge interpretation

Pretty Good AI describes a voice-first operating layer for healthcare practices, including
scheduling, prescription refills, insurance verification, escalation, auditability, and per-call
quality review. Its careers material emphasizes comfort with ambiguity, customer-facing problem
solving, production debugging, APIs, and Python/JavaScript. Those signals shaped the repository:
the implementation is runnable rather than a notebook, scenarios exercise practical clinic
workflows and safety boundaries, and every call leaves evidence a reviewer can trace.

The supplied challenge document makes natural conversation the first gate, followed by bug quality,
working code, design reasoning, and iteration. It requires at least ten complete 1–3 minute calls,
MP3 or OGG recordings, both-side transcripts, a public repository, a concise architecture summary,
a bug report, and two short public videos. It also fixes the only allowed destination at
`+18054398008` and asks for one E.164 caller number. The live-call and video requirements cannot be
truthfully substituted with mocks, so the repository keeps them as explicit completion gates.

## Technical sources used

| Source | Decision supported |
|---|---|
| https://prettygoodai.com/ | Healthcare workflow and QA context |
| https://prettygoodai.com/careers/ | Engineering and customer-ownership expectations |
| https://openai.github.io/openai-agents-python/realtime/guide/ | Realtime session and playback tracking design |
| https://github.com/openai/openai-agents-python/tree/main/examples/realtime/twilio | Official Twilio relay pattern |
| https://developers.openai.com/api/docs/models/gpt-realtime-2.1 | Current realtime model selection |
| https://developers.openai.com/api/docs/models/gpt-4o-transcribe-diarize | Independent speaker-labelled transcription |
| https://www.twilio.com/docs/voice/media-streams | Bidirectional stream messages, marks, and clear |
| https://www.twilio.com/docs/voice/api/call-resource | Recording, time limit, and call parameters |
| Supplied programming-language report and spreadsheet | Python, strict runtime validation, dict lookup, buffers, built-in operations, and worst-case security review |

## Open-source use

No third-party example code was copied into the implementation. The official OpenAI example was
read as API reference. Runtime dependencies are used through their documented public interfaces;
their own licenses and hosted-service terms continue to apply. The repository implementation is MIT
licensed.

## Assumptions requiring live confirmation

- The assessment line accepts automated recorded calls during the testing window.
- The selected Twilio account can originate calls to the United States and record dual channels.
- The OpenAI project has Realtime and transcription access and adequate prepaid credit.
- The Athena test account phone field should use the single Twilio caller number for deterministic
  identity matching; confirm this before submitting the intake form.
- Recording consent and publication are permitted by the assessment instructions; otherwise request
  written clarification before publishing audio.
