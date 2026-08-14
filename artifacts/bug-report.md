# Bug and quality report

No live-call QA reports are present yet. Run the genuine assessment calls, review the generated
recordings and transcripts, and regenerate this report before submission.

## Engineering defect found and fixed

The strict scenario loader initially rejected unquoted ISO date strings because YAML converted them
to date objects before Pydantic validation. The scenario file now quotes every DOB, preserving the
intended string type. The 54-test regression suite passes after the fix. This is an implementation
defect, not a claim about Pretty Good AI's assessment agent.
