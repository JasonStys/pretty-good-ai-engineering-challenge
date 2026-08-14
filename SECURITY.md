# Security policy

## Reporting

Do not open a public issue containing an API key, Twilio token, real patient information, voice
recording, or exploitable account detail. Contact the repository owner privately through the email in
the package metadata and rotate any exposed credential immediately.

For non-sensitive implementation defects, use the repository's bug-report template with synthetic
run identifiers and the smallest safe reproduction.

## Supported scope

The current `1.x` assessment implementation receives security fixes. It is restricted to Pretty Good
AI's published challenge number and synthetic patient scenarios. It is not approved for production
healthcare data or calls to any other destination.

## Required controls

- Keep `.env` local and enable Twilio signature validation.
- Place TLS termination and rate limiting in front of the public WebSocket.
- Use least-privilege OpenAI and Twilio projects, spending alerts, and credential rotation.
- Run CI, CodeQL, Bandit, pip-audit, and the artifact secret gate before publication.
- Review every audio, transcript, screenshot, and video for sensitive content before committing.
