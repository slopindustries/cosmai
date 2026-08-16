# Experiments

Experiments reduce named uncertainty. They do not become production dependencies.

- Create the record from [EXPERIMENT-TEMPLATE.md](EXPERIMENT-TEMPLATE.md).
- Keep source-specific probes under [`source-probes/`](source-probes/README.md).
- Keep the disposable integrated P0 under [`integrated-p0/`](integrated-p0/README.md).
- Apply [Data Handling](../docs/conventions/data-handling.md) to every input and artifact.

Commit completed records, sanitized summaries, hashes, reproduction instructions, and eligible public fixtures. Keep raw downloads, local databases, runtime logs, restricted data, and caches outside Git. An ignored artifact used as evidence must still have a recorded identity, hash, retention responsibility, and retrieval or generation procedure.
