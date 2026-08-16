# Test Fixtures

Fixtures are among the few assets eligible for promotion from P0 to P1.

Storage class and agent access are governed by [Data Handling](../../docs/conventions/data-handling.md):

- [`public/`](public/README.md): small, redistributable, reviewable fixtures committed to Git;
- [`local/`](local/README.md): Git-ignored, non-redistributable fixtures that may be processed by an agent only when the recorded basis permits it;
- `private/`: Git-ignored sensitive material that agents are denied from reading and tests must not require.

Every fixture must document:

- source or generator;
- capture or generation time;
- license or redistribution basis;
- agent-processing basis;
- original content hash;
- redaction or transformation performed;
- schema or contract version;
- why the sample is representative;
- expected edge cases.

Use [FIXTURE-METADATA-TEMPLATE.md](FIXTURE-METADATA-TEMPLATE.md) for every fixture or local-only fixture manifest. Extension alone does not decide whether an artifact can be committed.
