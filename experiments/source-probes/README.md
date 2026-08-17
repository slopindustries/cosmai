# Source Probes

Source probes begin only in P0-B after the P0-A Completion Gate. Use one subdirectory per candidate source. A probe is disposable code used to answer OQ-001, not a production connector.

A probe is also not the concrete integrated P0 collector or dataset importer. It may retrieve the bounded sample needed to measure a candidate, but it must not grow into the P0-B acquisition implementation governed by [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md).

Create each probe record from [`experiments/EXPERIMENT-TEMPLATE.md`](../EXPERIMENT-TEMPLATE.md), then add the source-specific fields below. Keep the completed record beside its code and artifacts.

For every candidate, also copy and complete [SOURCE-CAPABILITY-TEMPLATE.md](SOURCE-CAPABILITY-TEMPLATE.md). Compare candidates in [SOURCE-SELECTION-MATRIX.md](SOURCE-SELECTION-MATRIX.md). A score alone cannot override a failed hard gate.

Each probe must record:

- provider and endpoint or dataset page;
- usage rights and redistribution constraints;
- capture time and environment;
- authentication shape with secrets excluded;
- pagination, rate-limit, update, deletion, and identifier behavior;
- schema, null, duplicate, encoding, and payload-size observations;
- replay instructions;
- `GO`, `CONDITIONAL GO`, or `NO-GO` recommendation.

Do not commit large or restricted downloads. Store a checksum and retrieval procedure instead.
