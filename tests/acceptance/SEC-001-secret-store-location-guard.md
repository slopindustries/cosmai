# SEC-001 — The platform refuses a secret-store path inside the repository working tree

- Status: `DRAFT`
- Family: `SEC`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md) — "Provenance and security"
- Related Open Question or Decision Packet: [OQ-007](../../docs/open-questions/OQ-007-credential-scope.md)
- Input fixture and metadata: synthetic store files created under `tmp_path` and, for the negative case, under a temporary path inside the working tree that is removed afterwards. No real credential.
- Owner: Project team

## Intent

Close the gap [Secret Setup](../../docs/conventions/secret-setup.md) names explicitly:

> Store 경로가 repository working tree 아래면 기동 시점에 즉시 실패시킨다. 현재 이 검사는 `scripts/with-secret-source.sh`에만 있으므로 런처를 거치지 않는 실행 경로에는 적용되지 않습니다. **P0-A에서 애플리케이션 기동 경로와 test session 시작 지점에 같은 가드를 추가해야 platform `SEC-001` 증거로 쓸 수 있다.**

The test-session half already exists in `tests/conftest.py`. This scenario is the application-startup half. Until it exists, any run that bypasses the launcher — an IDE run configuration, a bare `python -m`, a container entrypoint — has no guard at all, and the launcher's protection is a convention rather than an invariant.

`docs/conventions/p0-security.md` states the wider principle this serves: `.gitignore` and agent permission deny rules are a safety net, not the only line of defence.

## Preconditions

- Initial durable state: irrelevant; the guard must fire before the database is touched.
- Worker or service state: no process running.
- Configuration with secrets excluded: an otherwise valid baseline environment.
- Time, retry, and concurrency assumptions: none.

## Action

For each case, start the worker entrypoint and then the API entrypoint, and observe the exit.

| Case | `COSMA_SECRET_SOURCE` |
|---|---|
| a | unset |
| b | a file outside the working tree, mode `600` |
| c | a file directly inside the repository root |
| d | a file in a nested directory inside the working tree |
| e | a path outside the tree whose resolved target is inside it (symbolic link) |
| f | the repository root directory itself |

## Expected state transitions

| Step | Entity | From | To | Required timestamp or reason |
|---|---|---|---|---|
| a | process | starting | running | P0-A resolves no credential; an unset store is not a configuration error |
| b | process | starting | running | Location is acceptable |
| c–f | process | starting | exited non-zero | `CONFIGURATION_INVALID`, refused before any database connection |

Case a is deliberately permitted. P0-A implements only the location guard, not credential resolution — [OQ-007](../../docs/open-questions/OQ-007-credential-scope.md) assigns resolution to P0-B. Requiring the variable now would invent an obligation the stage boundary does not have.

Case e is the one a naive check fails. The guard must compare **resolved** paths, exactly as `tests/conftest.py` already does with `Path(...).expanduser().resolve()`.

## Expected durable effects

- Created or changed records: none in any case. No migration runs, no connection is opened.
- Effects that must not occur: no file is created inside the working tree; the guard must not read the store's **contents** in order to decide — the location alone is the question, and reading a credential to validate its location would be the leak the rule exists to prevent.
- Idempotency or duplicate expectation: n/a.
- Lineage expectation: none.

## Expected telemetry

- Correlation identifiers: none required; the failure precedes job context.
- Structured event or log fields: one event naming the rejected path and the repository root it fell inside. The path is not a credential value and is safe to print; the store's contents are never read or logged.
- Metrics and units: none required.
- Protected debug behavior: no environment dump. [Secret Setup](../../docs/conventions/secret-setup.md) names that as a prohibited channel.

## Failure classification and recovery

- Expected error class and code: `CONFIGURATION_INVALID`.
- Retryable: no. A restart with the same environment must fail identically.
- Operator-visible explanation: the rejected path, the working-tree root, and a pointer to `docs/conventions/secret-setup.md`.
- Safe retry or final action: move the store outside the working tree and restart.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k sec_001`
- Assertions: the table above; the guard uses resolved paths, proven by case e; no case opens a database connection; no case reads the store's contents, proven by pointing the variable at an unreadable file in case b and observing that startup still succeeds; the same guard is reached by **both** entrypoints, not only one.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/`
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: not executed
- `NOT RUN`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md)
- Known limitation: this guards location only. File permissions are checked by `scripts/with-secret-source.sh` and not re-checked at application startup, so a run that bypasses the launcher gets the location guarantee but not the permission one. Recorded rather than closed, because P0-A never opens the store; P0-B's resolver is where the permission check belongs.
