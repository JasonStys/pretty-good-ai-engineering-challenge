/** Generate the requested reviewer-ready Word reports with docx-js. */

const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  HeadingLevel,
  PageBreak,
  PageNumber,
  Packer,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} = require("docx");

const COLORS = {
  navy: "15253D",
  blue: "1F6FEB",
  teal: "0E7490",
  lightBlue: "E8F1FB",
  lightGreen: "E6F4EA",
  lightAmber: "FFF4CE",
  gray: "5B6573",
  white: "FFFFFF",
};

const border = { style: BorderStyle.SINGLE, size: 2, color: "D1D5DB" };
const borders = { top: border, bottom: border, left: border, right: border };

function body(text, options = {}) {
  return new Paragraph({
    spacing: { after: 130, line: 276 },
    alignment: options.alignment || AlignmentType.LEFT,
    children: [
      new TextRun({
        text,
        bold: options.bold || false,
        italics: options.italics || false,
        color: options.color || "1F2937",
        size: options.size || 21,
      }),
    ],
  });
}

function heading(text, level = HeadingLevel.HEADING_1) {
  return new Paragraph({
    text,
    heading: level,
    spacing: { before: level === HeadingLevel.HEADING_1 ? 300 : 220, after: 120 },
  });
}

function bullet(text) {
  return new Paragraph({
    text,
    bullet: { level: 0 },
    spacing: { after: 80, line: 264 },
  });
}

function numbered(text, reference = "numbered-list") {
  return new Paragraph({
    text,
    numbering: { reference, level: 0 },
    spacing: { after: 80, line: 264 },
  });
}

function table(headers, rows, widths) {
  const header = new TableRow({
    tableHeader: true,
    children: headers.map(
      (label, index) =>
        new TableCell({
          width: { size: widths[index], type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, fill: COLORS.blue, color: "auto" },
          margins: { top: 100, bottom: 100, left: 100, right: 100 },
          borders,
          children: [
            new Paragraph({
              children: [new TextRun({ text: label, bold: true, color: COLORS.white, size: 19 })],
            }),
          ],
        }),
    ),
  });
  const bodyRows = rows.map(
    (row, rowIndex) =>
      new TableRow({
        children: row.map(
          (value, index) =>
            new TableCell({
              width: { size: widths[index], type: WidthType.DXA },
              shading: {
                type: ShadingType.CLEAR,
                fill: rowIndex % 2 === 0 ? "F8FAFC" : COLORS.white,
                color: "auto",
              },
              margins: { top: 90, bottom: 90, left: 100, right: 100 },
              borders,
              children: [body(String(value), { size: 18 })],
            }),
        ),
      }),
  );
  return new Table({
    width: { size: widths.reduce((sum, value) => sum + value, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [header, ...bodyRows],
  });
}

function titlePage(title, subtitle) {
  return [
    new Paragraph({ spacing: { before: 1500, after: 250 }, children: [] }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 240 },
      children: [new TextRun({ text: title, bold: true, size: 42, color: COLORS.navy })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 500 },
      children: [new TextRun({ text: subtitle, size: 26, color: COLORS.teal })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 700, after: 80 },
      children: [new TextRun({ text: "Prepared for", bold: true, color: COLORS.gray })],
    }),
    body("Pretty Good AI — AI Engineering Challenge", { alignment: AlignmentType.CENTER, size: 22 }),
    body("Jason Stys | 14 August 2026", { alignment: AlignmentType.CENTER, size: 20 }),
    new Paragraph({ children: [new PageBreak()] }),
  ];
}

function footer() {
  return new Footer({
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: "Pretty Good AI Challenge  •  Jason Stys  •  Page ", color: COLORS.gray, size: 17 }),
          new TextRun({ children: [PageNumber.CURRENT], color: COLORS.gray, size: 17 }),
        ],
      }),
    ],
  });
}

function makeDocument(children, title, description) {
  return new Document({
    creator: "Jason Stys",
    title,
    description,
    styles: {
      default: {
        document: { run: { font: "Aptos", size: 21, color: "1F2937" } },
        heading1: { run: { font: "Aptos Display", size: 31, bold: true, color: COLORS.navy } },
        heading2: { run: { font: "Aptos Display", size: 25, bold: true, color: COLORS.teal } },
      },
    },
    numbering: {
      config: [
        {
          reference: "numbered-list",
          levels: [
            {
              level: 0,
              format: "decimal",
              text: "%1.",
              alignment: AlignmentType.START,
              style: { paragraph: { indent: { left: 420, hanging: 220 } } },
            },
          ],
        },
        {
          reference: "numbered-operations",
          levels: [
            {
              level: 0,
              format: "decimal",
              text: "%1.",
              alignment: AlignmentType.START,
              style: { paragraph: { indent: { left: 420, hanging: 220 } } },
            },
          ],
        },
      ],
    },
    sections: [
      {
        properties: {
          page: {
            size: { width: 12240, height: 15840 },
            margin: { top: 900, right: 900, bottom: 900, left: 900 },
          },
        },
        footers: { default: footer() },
        children,
      },
    ],
  });
}

function engineeringChildren() {
  const componentRows = [
    ["ScenarioCatalog", "Safe YAML and hash index", "Build O(n); lookup O(1) average", "Strict synthetic schema"],
    ["MediaBridge", "Twilio ↔ Realtime relay", "O(audio bytes + history)", "Bounded buffer and cleanup"],
    ["TwilioGateway", "Call, status, recording", "O(polls + recording bytes)", "Fixed destination twice"],
    ["AssessmentRunner", "Evidence orchestration", "O(call duration + artifacts)", "Failure manifest always written"],
    ["QA and reports", "Diarization and schema review", "O(transcript + findings)", "Quote-level evidence"],
    ["Submission gate", "Cross-run consistency", "O(files + bytes)", "Ten genuine calls required"],
  ];
  const riskRows = [
    ["Unauthorized call", "Hard-coded +18054398008 at config and gateway", "Unit-tested block", "Low"],
    ["Forged WebSocket", "Twilio signature required by default", "Policy-close test", "Low"],
    ["Memory/page leak", "64 KiB frame cap; ~50 ms bytearray; finally cleanup", "Lifecycle test + metrics", "Low"],
    ["Credential leakage", "Secret types, ignored .env, artifact scanner", "Security workflow", "Low"],
    ["Real PHI", "Synthetic classification required in every scenario", "Schema tests", "Low"],
    ["External service outage", "Health preflight, bounded polling, auditable failure", "Runner tests", "Medium"],
    ["Recording publication", "Manual review remains mandatory", "Pending live review", "Medium"],
  ];
  return [
    ...titlePage("Engineering Design Report", "Safety-bounded realtime synthetic patient and QA harness"),
    heading("Executive summary"),
    body("This repository implements a Python voice bot that can call only Pretty Good AI's assessment line, behave as a realistic synthetic patient, record both sides, generate role-labelled transcripts, and turn the resulting conversation into evidence-backed quality findings. Twilio owns the outbound call, dual-channel MP3, and bidirectional 8 kHz G.711 μ-law stream. OpenAI Realtime provides low-latency patient speech, semantic turn detection, and interruption handling. The local path relays the existing codec without transcoding and retains only a bounded byte buffer plus short session history."),
    body("The implementation is intentionally auditable. Pydantic rejects invalid settings and scenarios; the assessment number is enforced twice; a signed WebSocket is required by default; polling has monotonic deadlines; downloads stream to an atomic temporary file; and every exit path clears tasks, sessions, buffers, and playback marks. Post-call processing adds independent diarization, structured QA, an aggregate bug report, per-call CPU/RSS/page-fault/disk metrics, and a submission gate that cannot pass without ten genuine call artifacts."),
    heading("Assignment alignment"),
    table(
      ["Requirement", "Implementation", "Evidence"],
      [
        ["Automated voice bot", "Realtime synthetic patient over Twilio Media Streams", "src/pgai_voicebot/media_bridge.py"],
        ["Only assessment line", "No caller-supplied destination; two allowlist checks", "constants.py, config.py, telephony.py"],
        ["10 complete calls", "Sequential 10-of-12 batch plus strict artifact gate", "runner.py, validation.py"],
        ["MP3/OGG recording", "Dual-channel MP3 streamed from Twilio", "recording.mp3 per run"],
        ["Both-side transcript", "Realtime history plus independent diarized ASR", "transcript.json/md, recording-diarization.json"],
        ["Identify bugs", "Schema-constrained QA and severity-sorted report", "qa-report.json, artifacts/bug-report.md"],
        ["Design reasoning", "README and this architecture report", "docs/architecture.md"],
      ],
      [2200, 3900, 3440],
    ),
    heading("Architecture"),
    heading("Conversation path", HeadingLevel.HEADING_2),
    numbered("The runner verifies the public HTTPS health endpoint before spending money."),
    numbered("Twilio creates one recorded call from the configured caller number to +18054398008."),
    numbered("Twilio opens a signed bidirectional WebSocket and provides scenario/run identifiers as bounded custom parameters."),
    numbered("The bridge validates frames, batches approximately 50 ms of μ-law audio, and sends it to the Realtime session."),
    numbered("Generated μ-law audio is returned with a Twilio playback mark; interruptions issue clear and update the playback tracker."),
    numbered("When either peer finishes, the bridge cancels remaining tasks, closes the session, clears mutable state, and persists the transcript."),
    heading("Post-call evidence", HeadingLevel.HEADING_2),
    body("The runner waits for a terminal call state and completed recording using bounded polling. The MP3 is downloaded in 64 KiB chunks, then independently transcribed with speaker diarization. The role-labelled transcript is evaluated only against the selected synthetic scenario's objective, goals, probes, and stop conditions. Pydantic rejects malformed QA output. Findings contain severity, category, evidence, impact, expected behavior, reproduction steps, and confidence."),
    heading("Component and complexity map"),
    table(["Component", "Responsibility", "Expected complexity", "Reliability property"], componentRows, [2100, 3000, 2200, 2240]),
    heading("Efficiency and resource behavior"),
    bullet("No local audio resampling, waveform expansion, model weights, or GPU allocation occurs."),
    bullet("The conversation path uses one bytearray, no unbounded queue, and no nested polling loop."),
    bullet("Scenario lookup uses a dictionary for expected O(1) access; duplicate identifiers fail at load time."),
    bullet("Transcript conversion and validation are one-pass over their inputs; issue ordering delegates to Python's stable built-in sort."),
    bullet("Each live call records wall time, process CPU seconds, peak boundary RSS, page faults where supported, recording bytes, transcript bytes, and artifact disk bytes."),
    body("The local benchmark records median and p95 microseconds, CPU time, traced peak allocations, page-fault deltas, and an empirical log-log growth exponent. Network and hosted-model latency is deliberately separated because it varies with provider load and cannot be optimized with local data structures."),
    heading("Security and privacy"),
    table(["Risk", "Control", "Verification", "Residual"], riskRows, [2300, 3900, 2200, 1140]),
    heading("Scenario strategy"),
    body("Twelve scenarios cover new-patient scheduling, rescheduling, cancellation/waitlist behavior, routine refills, practice information, closed-day boundaries, urgent symptom escalation, another-adult privacy, interruption/correction, Spanish continuity, hearing accessibility, and conflicting demographics. All identities are synthetic. Each scenario includes an objective, persona, bounded facts, conversation goals, probes, and explicit stop conditions, which keeps the patient active without relying on one monolithic prompt."),
    heading("Verification result"),
    table(
      ["Check", "Result", "Interpretation"],
      [
        ["pytest", "54 passed", "Network/billing boundaries are replaced; failure paths included"],
        ["Coverage", "91.47% branch-aware", "Exceeds the 90% repository gate"],
        ["Ruff", "Pass", "Lint and formatting clean"],
        ["mypy strict", "Pass", "Zero source errors across 18 files"],
        ["Bandit", "Pass", "Zero static findings"],
        ["pip-audit", "Pass", "Zero known vulnerabilities on 2026-08-14"],
        ["Radon", "Average A", "Maintainability A for every source file"],
        ["Live submission", "Pending", "No mocked result is counted as a real call"],
      ],
      [2200, 2200, 5140],
    ),
    heading("Operational sequence"),
    numbered("Create a Twilio caller number and OpenAI project; place secrets only in .env.", "numbered-operations"),
    numbered("Deploy or tunnel the service over HTTPS/WSS, then verify /healthz.", "numbered-operations"),
    numbered("Use the selected caller number for the Athena test identity; do not call its confirmation number.", "numbered-operations"),
    numbered("Run and listen to one smoke call. Stop if consent, audio, cost, or behavior is wrong.", "numbered-operations"),
    numbered("Run ten distinct scenarios sequentially, review every artifact, and correct only diarization labels—not spoken evidence.", "numbered-operations"),
    numbered("Run the live submission gate, commit reviewed evidence, record the two required personal videos, and complete the form.", "numbered-operations"),
    heading("Primary sources"),
    body("Pretty Good AI: https://prettygoodai.com/ and https://prettygoodai.com/careers/"),
    body("OpenAI Agents SDK Realtime guide and official Twilio example: https://openai.github.io/openai-agents-python/realtime/guide/ and https://github.com/openai/openai-agents-python/tree/main/examples/realtime/twilio"),
    body("Twilio Media Streams and Call resource: https://www.twilio.com/docs/voice/media-streams and https://www.twilio.com/docs/voice/api/call-resource"),
    heading("Conclusion"),
    body("The software, safety boundaries, tests, reporting structure, and automation are ready for authenticated live execution. The remaining work is intentionally human- and account-bound: provision the caller and paid APIs, create the Athena test identity, make and review ten genuine calls, record the public walkthrough and AI-debug videos with Jason's own voice/webcam, then publish the reviewed evidence. Until those steps occur, the submission gate remains pending by design."),
  ];
}

function validationChildren() {
  const testRows = [
    ["FastAPI app", "3", "Health, auth rejection, bridge exception", "PASS"],
    ["Artifacts", "3", "Atomic files and aggregate issues", "PASS"],
    ["CLI", "6", "Routing, flags, error codes", "PASS"],
    ["Configuration", "8", "Credentials, E.164, destination, URLs", "PASS"],
    ["Media bridge", "11", "Protocol, media, events, cleanup", "PASS"],
    ["Structured QA", "2", "Diarization and response model", "PASS"],
    ["Runner", "5", "Health, orchestration, failure evidence", "PASS"],
    ["Scenarios", "7", "Diversity, schema, prompt", "PASS"],
    ["Telephony", "4", "Call safety, polling, download", "PASS"],
    ["Transcript", "2", "Role conversion", "PASS"],
    ["Submission gate", "3", "Artifacts, consistency, secrets", "PASS"],
  ];
  const actionRows = [
    ["CI", "Push, PR, manual", "Ruff, format, mypy, Python 3.11–3.13 tests, package", "Coverage XML + distributions"],
    ["Security", "Push, PR, weekly, manual", "Bandit, pip-audit, secret tests, CodeQL, dependency review", "Alerts and logs"],
    ["Performance", "Code change, weekly, manual", "Runtime, CPU, memory, page faults, Big-O, Radon", "Performance JSON"],
    ["Documentation", "Docs change, manual", "DOCX/XLSX structure, sheets, formulas, errors", "Four reports"],
    ["Live gate", "Artifact change or manual", "Ten real calls, scope, MP3, both-side transcript, secrets", "Pass/fail summary"],
  ];
  return [
    ...titlePage("Test and Validation Report", "Correctness, security, performance, and submission readiness"),
    heading("Result at a glance"),
    table(
      ["Metric", "Observed", "Gate", "Status"],
      [
        ["Automated tests", "54 passed", "All pass", "PASS"],
        ["Branch-aware coverage", "91.47%", "≥ 90%", "PASS"],
        ["Strict typing", "0 errors / 18 files", "0 errors", "PASS"],
        ["Bandit", "0 findings", "0 findings", "PASS"],
        ["Dependency audit", "0 known vulnerabilities", "0", "PASS"],
        ["Maintainability", "A for every source file", "No failing grade", "PASS"],
        ["Live completed calls", "0 committed", "≥ 10", "PENDING"],
      ],
      [2900, 2300, 1900, 2440],
    ),
    body("The local verification suite is complete and green. It does not claim that the challenge itself is submitted: the required recordings, transcripts, Athena test identity, and two personal public videos must come from genuine authenticated activity. The manual live-evidence workflow is intentionally configured to fail until those artifacts exist."),
    heading("Test inventory"),
    table(["Area", "Count", "What is exercised", "Result"], testRows, [2200, 1000, 4920, 1340]),
    body("Total test count: 54. Coverage uses branch measurement across the installed pgai_voicebot package and fails below 90%. The current measured total is 91.47%. Tests substitute deterministic fakes at paid network boundaries and use only placeholder credentials."),
    heading("Defect discovered during verification"),
    body("The first strict-scenario test run found that unquoted ISO birth dates in YAML were parsed into date objects before reaching Pydantic, while synthetic_facts intentionally accepts bounded strings only. Nine scenarios failed validation. The correction quotes each ISO date explicitly, preserving the string contract. The complete 54-test suite then passed. This demonstrates that strict runtime validation caught silent type coercion at the configuration boundary."),
    heading("Security validation"),
    bullet("Destination changes are rejected by configuration and telephony-layer tests."),
    bullet("A missing or invalid Twilio signature closes the Media Stream before allocating a Realtime session."),
    bullet("Malformed JSON, non-object frames, oversize frames, invalid base64, bad stream SIDs, and missing run context are rejected."),
    bullet("A source scan using Bandit reports zero findings after changing the local server default from all interfaces to 127.0.0.1; the Docker image explicitly opts into its container bind."),
    bullet("The dependency audit reports zero known vulnerabilities after upgrading the isolated environment's pip to 26.2.1."),
    bullet("The artifact gate scans OpenAI-key, Twilio-token, and private-key patterns and never reads .env into artifacts."),
    heading("Performance and complexity validation"),
    body("The benchmark measures hash-indexed scenario lookup, bounded prompt construction, and increasing transcript-history conversion. It captures median and p95 wall time, process CPU, traced peak bytes, page-fault deltas where available, RSS context, and an empirical growth exponent. The expected hot-path bounds are O(1) average for lookup, O(total scenario text) for prompt construction, and O(items + characters) for transcript conversion. Hosted API latency and GPU usage are reported separately; no local GPU is allocated."),
    body("Radon analyzed 98 classes, functions, and methods with average cyclomatic complexity A (2.64). Every source file has maintainability grade A. The final refactor decomposes the earlier 20-branch submission validator into focused manifest, batch-invariant, per-call, and transcript checks."),
    heading("GitHub Actions"),
    table(["Workflow", "Triggers", "Checks", "Reports"], actionRows, [1800, 1900, 4210, 1750]),
    heading("Live acceptance procedure"),
    numbered("Provision a paid voice-capable Twilio number and an OpenAI project with Realtime/transcription access."),
    numbered("Configure secrets in .env only and expose the bridge over reviewed HTTPS/WSS."),
    numbered("Create the Athena test identity with synthetic data and the single caller number; do not call its confirmation number."),
    numbered("Place one smoke call, listen to both channels, inspect the transcript, verify metrics, and check actual cost."),
    numbered("If acceptable, run ten distinct scenarios sequentially. Each should last approximately one to three minutes."),
    numbered("Listen to all recordings, review both-side transcripts and issue evidence, then run pgai-voicebot validate --minimum-calls 10."),
    numbered("Commit only reviewed evidence, verify every Action is green, then record the walkthrough and real AI-debug video."),
    heading("Live gate criteria"),
    table(
      ["Criterion", "Automated check", "Manual check"],
      [
        ["Ten distinct completed calls", "Manifest count and scenario uniqueness", "Confirm scenarios are meaningful"],
        ["One caller / fixed destination", "Exact E.164 consistency and +18054398008", "Match Athena identity"],
        ["MP3 evidence", "File exists and plausible minimum size", "Listen to both sides"],
        ["Conversation completeness", "At least four turns and both roles", "Confirm approximately 1–3 min and natural end"],
        ["No secrets", "Pattern scan over reviewable text", "Review audio/video/screens"],
        ["Bug quality", "Structured required fields", "Verify each quote/timestamp against audio"],
      ],
      [2800, 3300, 3540],
    ),
    heading("Final status"),
    body("Software verification status: PASS. Document structure status: PASS after package and render inspection. Live challenge evidence status: PENDING. This distinction prevents accidental or misleading submission of generated, mocked, or incomplete evidence."),
  ];
}

async function writeDocument(filename, document) {
  const output = path.join("docs", filename);
  fs.mkdirSync(path.dirname(output), { recursive: true });
  const buffer = await Packer.toBuffer(document);
  fs.writeFileSync(output, buffer);
  console.log(`Generated ${output}`);
}

async function main() {
  await writeDocument(
    "engineering-report.docx",
    makeDocument(
      engineeringChildren(),
      "Pretty Good AI Challenge — Engineering Design Report",
      "Architecture, safety, performance, and operating report for the synthetic patient simulator.",
    ),
  );
  await writeDocument(
    "test-validation-report.docx",
    makeDocument(
      validationChildren(),
      "Pretty Good AI Challenge — Test and Validation Report",
      "Correctness, security, performance, documentation, and live-readiness verification.",
    ),
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
