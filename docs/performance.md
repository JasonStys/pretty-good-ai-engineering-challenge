# Performance and efficiency report

Measured locally on 2026-08-14 with Python 3.12.13 and 22 logical CPUs. The benchmark excludes
Twilio network time and hosted-model latency so local algorithm and allocation changes remain
comparable.

| Operation | Repetitions | Median | P95 | CPU | Peak traced allocation | Expected Big-O |
|---|---:|---:|---:|---:|---:|---|
| Hash-indexed scenario lookup | 10,000 | 0.5 μs | 0.8 μs | 0.03125 s | 325,252 bytes | O(1) average; O(n) adversarial worst case |
| Bounded patient prompt construction | 2,000 | 22.8 μs | 42.9 μs | 0.0625 s | 68,365 bytes | O(total scenario text length) |

Increasing transcript-history samples of 100, 500, and 2,000 items took 0.000274, 0.001075, and
0.005657 seconds. The log-log exponent was 1.006, consistent with the intended linear
O(items + total transcript characters) converter. The benchmark process used 34,009,088 bytes RSS.
Windows exposed 452 and 18 page faults across the lookup and prompt measurement windows. These
counters include interpreter activity and are reported for regression context rather than treated as
application leaks.

The live path allocates no local GPU and loads no model weights; speech/model inference occurs in
hosted APIs. For each genuine call, `metrics.json` records wall time, process CPU, peak start/end RSS,
page-fault delta where supported, recording and transcript bytes, and the total regular-file disk
footprint. The recording download streams in 64 KiB pieces, and the media relay holds a single
approximately 50 ms `bytearray` plus compact conversation history.

Radon analyzed 98 source blocks after the validation refactor. Average cyclomatic complexity is A
(2.64), and every source file has maintainability grade A. The highest remaining block is the media
handshake at C (11); its branches correspond to the bounded Twilio protocol states rather than nested
business decisions. The earlier submission validator was reduced from complexity 20 into focused
manifest, batch, per-call, and transcript checks.

Reproduce with:

```bash
python scripts/benchmark.py --output build/reports/performance.json
radon cc src -s -a
radon mi src -s
```
