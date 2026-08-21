# Real-data captures — NAVER API Hub

`[결정]` **No payload is committed here, and none will be.** The usage basis for these
captures is the operator's personal research and study. `docs/conventions/data-handling.md`
keeps **agent-processing permission** and **redistribution permission** as separate
decisions, and the first does not imply the second: collecting and normalizing someone's
blog post is not a basis for publishing it in a repository. So the sources are registered
`data_class = "local"`, and `AGENTS.md`'s rule for that case applies — *"store hashes and
retrieval instructions"*.

This directory is those hashes and those instructions.

## What was captured

`[측정]` Three collectors have run against the live API. Two of the three captures are still
in the local database and their digests are recorded below; the third is not, and that is
stated rather than filled in.

### Search Trend — `POST /search-trend/v1/search`

| | |
|---|---|
| Provider | NAVER Cloud Platform · NAVER API HUB |
| Endpoint | `https://naverapihub.apigw.ntruss.com/search-trend/v1/search` |
| Documentation | `https://api.ncloud-docs.com/docs/naver-api-hub-search-trend` (fetched 2026-08-19) |
| Captured | 2026-08-19T06:33:59.480295+09:00 |
| Add-on | `collector.naver.searchtrend@0.1.0` |
| Status | `200` |
| Body | 757 bytes, `sha256:70adcc03d5c57dde6296614747075dcc7782a81671caaea7809d8248535eca94` |
| Items extracted | 14 (2 keyword groups × 7 weekly points) |
| Snapshot | `01f9732a-0830-4440-a0f7-668556a61721`, manifest `sha256:03b9b9a0ac7a5d9574fe6f5f372307d3c044b2395710e547b17af579879484a0` |
| Normalized | 14 records, `normalizer.naver.trend@0.1.0`, output contract `0.2` |

### Shopping Insight — `POST /shopping/v1/categories`

| | |
|---|---|
| Provider | NAVER Cloud Platform · NAVER API HUB |
| Endpoint | `https://naverapihub.apigw.ntruss.com/shopping/v1/categories` |
| Documentation | `https://api.ncloud-docs.com/docs/naver-api-hub-shopping-insight-categories` (fetched 2026-08-19) |
| Captured | 2026-08-19T06:34:01.455942+09:00 |
| Add-on | `collector.naver.shoppinginsight@0.1.0` |
| Status | `200` |
| Body | 423 bytes, `sha256:af9505b3cbf1948e66dee1962f822eb53e6ea5cd08d21e1469df9eef4325312e` |
| Items extracted | 7 (1 category × 7 weekly points) |
| Snapshot | `edfd90ff-1dce-49a6-8f0a-7b4d560c11d7`, manifest `sha256:9120748df7b402cb14d75a92f4dfaeec80e5602d00dea03dcc79ca249954429f` |
| Normalized | 7 records, `normalizer.naver.trend@0.1.0`, output contract `0.2` |

### Blog Search — `GET /search/v1/blog` — **digest not recorded**

`[확인 사실]` A capture happened on 2026-08-19 at about 00:28 KST: two envelopes, ten items,
normalized to ten Schema 0.1 documents, and the observation is recorded in
`experiments/integrated-p0/README.md`. **Its digest is not here, because the bytes are
gone** — a later run of the DataLab scenario cleared the domain tables before collecting,
and the hash was never written down while the rows existed.

`[결정]` Recorded as a gap rather than back-filled. A digest computed from a *second* capture
would not be the digest of the run that was measured, and labelling it as though it were is
the kind of claim this repository treats as a defect. The retrieval procedure below
reproduces an equivalent capture; it does not reproduce that one.

`[추론]` The lesson is procedural and belongs with the evidence: **a capture's digest has to
be taken while the rows exist**, not at the end of a session. The scenario scripts clear the
database on the way in, so anything not written down before the next run is unrecoverable.

## Usage basis

| | |
|---|---|
| Stated basis | Personal research and study, stated by the operator on 2026-08-18 |
| Covers | Retrieval, storage in the local database, and processing by this pipeline |
| Does **not** cover | Redistribution — publishing payloads in this repository or anywhere else |
| Recorded as | `source.data_class = 'local'` on every NAVER source row |
| Quota consumed | Search: 2 of 25,000/day. Data Lab: 2 of 50,000/month |

`[추론]` `local` rather than `public` is the conservative reading and the reversible one. If
a redistribution basis is later established, a source row can be re-registered `public` and
fixtures committed then; the reverse — un-publishing content already committed to a Git
history — is not a change anyone can make cleanly.

## Retrieval procedure

These captures can be reproduced, and reproducing them is the intended substitute for
committing them.

**Prerequisites.** An NCP NAVER API HUB key pair, in a secret store outside the repository:

```sh
mkdir -p ~/.config/cosmai && chmod 700 ~/.config/cosmai
printf 'COSMA_SRC_NAVER_BLOG_CLIENT_ID=<id>\nCOSMA_SRC_NAVER_BLOG_CLIENT_SECRET=<secret>\n' \
  > ~/.config/cosmai/env
chmod 600 ~/.config/cosmai/env
```

**The gated scenario.** `tests/test_naver_real_data.py` registers the blog source, collects,
seals, normalizes, and asserts on the result. It is opt-in twice, because it opens a real
connection and spends a real quota:

```sh
./scripts/with-secret-source.sh ./scripts/with-database.sh \
  uv run pytest --run-network --run-credential -q \
  -k "TestTheCollectorReachesTheRealApi or TestTheDocumentedAssumptions or TestTheNormalizerRunsOnRealData"
```

**Recording a digest.** After a capture, and *before* anything clears the tables:

```sh
./scripts/with-database.sh psql -c \
  "select source_id, endpoint_ref, body_sha256, octet_length(body), retrieved_at from raw_envelope order by retrieved_at"
./scripts/with-database.sh psql -c \
  "select source_id, id, item_count, manifest_sha256 from snapshot order by created_at"
```

**What will not match.** A re-run produces different bytes and therefore a different digest:
blog search returns whatever was posted most recently, and DataLab's `ratio` is relative to
the requested window's maximum. The digests above identify **one capture**, not a fixture to
compare against. What a re-run does reproduce is the *shape* — and the shape is what the
scenario asserts.

## Environment

| | |
|---|---|
| Python | 3.13.14 |
| PostgreSQL | 18.4 |
| Repository revision at capture | `c0a266d` plus the uncommitted P0-B working tree |
| Contract version | `addon_api` 1.1 |
| Platform | Linux 6.18 (WSL2) |
