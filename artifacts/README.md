# Call artifacts

Each completed run has its own directory under `calls/<run-id>/` with a manifest,
role-labelled transcript, MP3 recording, structured QA report, and resource metrics.

All scenarios use synthetic patient identities. Review every artifact before committing it.
Raw streaming events and temporary WAV files remain ignored because they are unnecessary for
the assessment and can reveal more detail than the final evidence requires.
