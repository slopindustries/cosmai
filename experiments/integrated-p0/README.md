# Integrated P0

This directory will contain the disposable full-flow Architecture Discovery Prototype.

Do not start implementation until OQ-001 selects one REST and one dataset candidate with usable fixtures. When implementation begins, keep backend, dashboard, and orchestration inside this boundary so none can be mistaken for P1 application code.

P0 must follow `docs/p0-charter.md`. It may optimize for observability and experimental clarity over long-term maintainability, but it must not compromise source rights, secret handling, provenance, or result labeling.

Create each integrated experiment from [`experiments/EXPERIMENT-TEMPLATE.md`](../EXPERIMENT-TEMPLATE.md). Keep the completed record beside its code and artifacts.
