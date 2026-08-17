"""Platform instrumentation for the disposable P0-A core.

Four concerns live here, and each is deliberately one module with one owner:
redaction (the single place a value is masked), correlation (the identifier that
makes a job traceable across processes), structured logging (JSON Lines evidence
the gate can read), and metrics (the counters and durations CONTRACT-JOB@0.1
requires).

The charter calls this experimental instrumentation, not deferred polish. It is
also handler-neutral: nothing here knows what a job means.
"""
