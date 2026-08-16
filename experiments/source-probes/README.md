# Source Probes

Use one subdirectory per candidate source. A probe is disposable code used to answer OQ-001, not a production connector.

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
