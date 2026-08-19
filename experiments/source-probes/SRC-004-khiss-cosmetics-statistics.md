# SRC-004 — KHISS cosmetics industry statistics — Source Capability Profile

`[결정]` **Result: `NO-GO`.** Two independent reasons, either sufficient. Its finest
granularity is a statutory product *class* by year — there is no product, no brand, and no
ingredient — so it cannot carry traceable evidence to a sunscreen or toner claim. And the
data.go.kr entry the execution plan points at **has no file to download**: it is a pointer to
a portal where a person clicks through a statistics-table tree, and the underlying tables sit
behind a KOSIS single-sign-on redirect.

`[확인 사실]` This profile was written because [`SRC-003`](SRC-003-open-beauty-facts.md) is
`NO-GO`. It failed **Korean sunscreen and toner coverage**: zero and zero.

## Identity

- Candidate ID: `SRC-004`
- Acquisition mode: `DATASET_IMPORT`
- Provider or producer: 한국보건산업진흥원 (Korea Health Industry Development Institute, KHIDI),
  정보화전략팀 / 보건산업정보통계센터
- Distributor, if different: 공공데이터포털 `data.go.kr` catalogues it; the file itself is
  distributed from KHIDI's own 보건산업통계 portal (KHISS), and the tables are hosted on KOSIS
- Endpoint or dataset page: `https://www.data.go.kr/data/3081174/fileData.do`; the linked
  source is `https://www.khiss.go.kr/indi?menuId=MENU00348`
- Content channel or domain: Korean cosmetics **industry** statistics — market size,
  production, trade, employment, business performance, R&D
- Related experiment: none.
- Profile captured at: 2026-08-20T07:54+09:00 to 2026-08-20T08:05+09:00

## Rights and processing basis

- Terms or license URL and version/date: `https://www.data.go.kr/data/3081174/fileData.do`
  and its machine-readable twin `https://www.data.go.kr/catalog/3081174/fileData.json`
  (`sha256:11eb95b124512e4bf20c09ed36794dc00353ab49426f82acc251fd8f96139628`), both fetched
  2026-08-20T07:55+09:00
- Permitted experimental use: `YES`
- Redistribution permitted: `YES`. `[확인 사실]` The catalogue's `license` field reads
  `이용허락범위 제한 없음` — "scope of permitted use: no restriction" — and `비용부과유무`
  reads `무료`.
- Agent processing permitted: `YES`, on the same basis.
- Attribution or deletion obligation: `[측정]` **None stated on the catalogue entry.** The
  `legislation` field is empty and no KOGL type mark appears. `[추론]` Absence of a stated
  attribution requirement is not the same as a statement that none exists; naming the
  provider on any derived output costs nothing and is the conservative reading.
- Evidence and unresolved interpretation: `[추론]` The rights position is the cleanest of
  the three dataset candidates profiled and it is the only check this candidate would pass.

## Hard gates

| Gate | Result | Evidence or blocking reason |
|---|---|---|
| G1 — Access and rights permit the recorded P0 experiment. | `PASS` | `이용허락범위 제한 없음`, free, no registration for the catalogue entry. |
| G2 — Data can be handled without exposing prohibited secrets, personal data, or restricted content. | `PASS` | Aggregate industry statistics. No personal data, no credential, nothing to redact. `[추론]` This follows from the aggregation level, which is also why it fails G4. |
| G3 — A representative sample can be retrieved or reconstructed with recorded identity, time, and hashes. | **`FAIL`** | There is no retrievable file. `data.go.kr` entry 3081174 carries no attachment, no preview, and no `distribution` in its catalogue JSON; `제공형태` is `기관자체에서 다운로드(제공데이터URL기재)`. The KHISS page it points to builds its table tree in JavaScript, and the KOSIS table view redirects to `sso.kosis.kr`. A sample can be obtained by a human with a browser; it cannot be retrieved by a recorded command, and no digest of "the CSV" can be taken because no URL yields one. |
| G4 — The sample exercises at least one named P0 architecture question. | **`FAIL`** | The named question is a Korean sunscreen and toner evidence path. The finest granularity available is 화장품 유형 (13 statutory product classes) by year. Sunscreen is not a 유형 at all; toner is inside 기초 화장용 제품류 and is never separated from it. No row can be traced to a product, a brand, or an ingredient. |
| G5 — Required access, volume, rate, and cost fit the P0-B timebox. | `PASS` | 96 rows, free. `[추론]` The volume is trivial; the cost is a person clicking, and that cost is what breaks G3, not G5. |

## B1 hard check

`[확인 사실]` [`p0-execution-plan.md`](../../docs/p0-execution-plan.md) §"B1 bounded candidate
set" sets exactly one hard check on this candidate: *"It is `NO-GO` if its aggregation level
cannot contribute traceable evidence to the selected card or a small shared schema."*

| Hard check | Result | Measurement |
|---|---|---|
| Aggregation level can contribute traceable evidence to the selected card or a small shared schema | **`NO-GO`** | Measured inventory of all 42 cosmetics tables the provider publishes: every one is an annual aggregate over an industry, a country, a trade item class, or a statutory product class. None reaches a product, a brand, or an ingredient. The two DP-011 categories are not addressable: `자외선차단제` (sunscreen) does not appear as a product class in the production series, and `토너` (toner) is subsumed in `기초 화장용 제품류` and never broken out. |

`[추론]` The distinction that decides it: the card's falsification condition in
[DP-011](../../docs/decisions/DP-011-p0b-product-and-delivery-scope.md) is *"any material
claim on the card cannot be traced to stored evidence."* A row saying "기초 화장용 제품류
production in 2021 was X" traces to nothing narrower than a thirteenth of the cosmetics
industry. It could sit on a card as **context**, and a shared schema could hold it — but it
cannot be the evidence for a sunscreen or toner claim, which is what the check asks.

## Dataset capability

- File format and compression: `[확인 사실]` the catalogue states `CSV`, `매체유형 텍스트`,
  `전체 행 96`. `[측정]` **Unverified — no file was obtainable.** Encoding, delimiter, and
  header are `UNKNOWN`.
- Dataset version or release date: `[확인 사실]` `등록일 2021-07-30`, `수정일 2025-09-03`,
  and the entry's own name is `한국보건산업진흥원_화장품 산업 통계_20210228`. One prior version
  is listed, `…_20190729` registered 2019-07-29. `업데이트 주기: 수시 (자동 갱신)`.
  `[추론]` The three dates disagree about what the data is as of, and the underlying tables
  (below) end in 2021 or 2022, so `수정일 2025-09-03` most plausibly records a metadata edit
  rather than new data. That is an inference; the portal does not say.
- Encoding and delimiter: `UNKNOWN`.
- Row identity candidate: `UNKNOWN` — no rows were retrieved. `[추론]` For a statistical
  table of this shape the identity would be `(table, product class, year)`, synthesised the
  way `SRC-001`'s Data Lab series was, because a statistics table has no record identifier.
- Event, publication, and update timestamps: `[측정]` The provider's own indicator API
  reports a period type and a period range per table; every cosmetics table is `연간`
  (annual), `부정기` (irregular), or unmarked. There is no event timestamp finer than a year,
  except the three employment tables, whose period range is written `201703~202202`.
  `[추론]` That format is year-and-month, so those three are presumably monthly; the field
  that would say so is empty on all three.
- Duplicate behavior: `UNKNOWN`.
- Missing and invalid values: `UNKNOWN`.
- Version, correction, and deletion behavior: `UNKNOWN`. `[측정]` The portal exposes one
  superseded version (2019-07-29) through a 주기성 과거 데이터 panel, so *some* history is
  retained; how corrections are expressed is not stated.
- File and representative subset sizes: `[확인 사실]` 96 rows, per the catalogue.

### Measured inventory of what the source actually contains

`[측정]` Retrieved 2026-08-20T07:58:10+09:00 from the provider's own indicator API,
`POST https://www.khiss.go.kr/indi/get/statTable` with `LIST_ID` set to each of the seven
cosmetics nodes. Combined response
`sha256:d41cb1b22e12c347ff1e2021b0d54c48b63e1b289cbb8173f7ef5eb02ed23092`, 28,282 bytes,
**42 tables**.

| Node | Tables | Finest breakdown present | Period type | Latest period |
|---|---|---|---|---|
| 세계 (`358_003_001`) | 9 | country, product class, top-100 company | 5 annual, 3 irregular, 1 unmarked | 2021 |
| 국내 시장규모 (`358_003_002_001`) | 3 | product class; manufacturer and responsible-seller counts | 2 annual, 1 unmarked | 2021 |
| 국내 생산 (`358_003_002_002`) | 16 | statutory product class (`유형`); one table by company | 14 annual, 2 unmarked | 2021 |
| 국내 수출입 (`358_003_002_003`) | 5 | partner country; trade item class | 1 annual, 4 unmarked | 2021 |
| 국내 고용 (`358_003_002_004`) | 3 | industry total | unmarked | `201703~202202` |
| 국내 경영성과 (`358_003_002_005`) | 0 | — | — | — |
| 국내 연구개발 (`358_003_002_006`) | 6 | industry total, by expenditure/degree/major | annual | 2019 |

`[측정]` The 13 statutory product classes that appear as separate production series are:
기초 화장용, 눈 화장용, 두발용, 두발 염색용, 색조 화장용, 손발톱용, 인체 세정용, 체취 방지용,
방향용, 영·유아용, 면도용, 목욕용, 체모 제거용. `[확인 사실]` Neither `자외선차단제`
(sunscreen) nor `토너` (toner) is among them. `[확인 사실]` The provider's own note on
`DT_ICC002_3` records that 체모제거용 products were *reclassified into 기능성화장품* in 2017,
so a 기능성화장품 bucket exists in the classification and the production series does not break
it out. `[추론]` Sunscreen sits in that bucket under Korean cosmetics law; this probe did not
verify the statute, and it does not need to — sunscreen is absent from the series either way.

`[확인 사실]` The one table nearest a product is `DT_PDFIRM_01`, `화장품 업체별 생산실적 추이`
— production by **company**, 2018~2021. `[추론]` A company is not a product and carries no
ingredient, so it does not change the finding.

`[측정]` The latest annual period across every cosmetics table is 2021, except employment at
2022-02 and R&D at 2019. Against a 2026-08 capture that is four to seven years stale.

## Reproduction and artifacts

`[결정]` No payload is committed, and in this case none could be: nothing was retrievable.

### Environment and versions

| | |
|---|---|
| Client | `curl 8.21.0`, `python 3.14.4` |
| Platform | Linux 6.18.33.2 (WSL2) |
| Repository revision | `f85287c` on `dev` |

`[측정]` Both `www.data.go.kr` and `www.khiss.go.kr` failed under `curl -L`, returning no
status and no body on every attempt. Dropping `-L` and issuing each request without automatic redirect
following works. That is a client-side trap worth recording for whoever writes the importer.

### Retrieval procedure

```sh
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36'

# Catalogue metadata — licence, format, row count, dates. Note: no -L.
curl -s -A "$UA" https://www.data.go.kr/catalog/3081174/fileData.json -o khiss-catalog.json

# The portal's own preview / version panel. Returns a version list and no CSV.
curl -s -A "$UA" -X POST \
  -H 'Referer: https://www.data.go.kr/data/3081174/fileData.do' \
  --data-urlencode 'publicDataPk=3081174' \
  --data-urlencode 'publicDataDetailPk=uddi:8f5be366-8c74-4f33-ac91-d33d25b03d69' \
  https://www.data.go.kr/tcs/dss/selectHistAndCsvData.do

# The provider's indicator tree, and the tables under each cosmetics node.
curl -s -A "$UA" -X POST https://www.khiss.go.kr/indi/get/statService -o statService.json
for id in 358_003_001 358_003_002_001 358_003_002_002 358_003_002_003 \
          358_003_002_004 358_003_002_005 358_003_002_006 ; do
  curl -s -A "$UA" -X POST --data "LIST_ID=$id" \
    -H 'Referer: https://www.khiss.go.kr/indi?menuId=MENU00348' \
    https://www.khiss.go.kr/indi/get/statTable
  echo
done > khiss-cosmetics-tables.json

# The table values themselves. This is where it stops.
curl -s -A "$UA" -D - -o /dev/null \
  'https://kosis.kr/statHtml/statHtml.do?orgId=358&tblId=DT_ICC002_3&conn_path=I2'
# -> 302 Location: https://sso.kosis.kr/ksso/sso/pmi-sso2.jsp?...
```

`[측정]` The last command's actual result on 2026-08-20T08:05+09:00: `HTTP 302` to
`sso.kosis.kr`. `https://stat.kosis.kr/statHtml_host/statHtml.do?orgId=358&tblId=DT_ICC002_3`
— the host KHISS itself links to — returned a 915-byte page titled `통계청::error`.

### Digests of what was actually measured

| Artifact | Captured (KST) | Bytes | SHA-256 |
|---|---|---|---|
| `khiss-catalog.json` — data.go.kr catalogue metadata | 2026-08-20T07:55 | 1,542 | `11eb95b124512e4bf20c09ed36794dc00353ab49426f82acc251fd8f96139628` |
| `khiss-cosmetics-tables.json` — 42-table inventory | 2026-08-20T07:58:10 | 28,282 | `d41cb1b22e12c347ff1e2021b0d54c48b63e1b289cbb8173f7ef5eb02ed23092` |

- Original content hash and algorithm: SHA-256 on the two metadata captures above. **The
  dataset itself has no digest, because no command retrieves it.**
- Redistributable fixture or local-only metadata location: none.
- Redaction or transformation: none.

## Recommendation

- Outcome: **`NO-GO`**
- Conditions or blocking gates: G3 and G4 both fail. G4 is the execution plan's own stated
  disqualifier and is not repairable — the aggregation level is a property of the source. G3
  is repairable by a person exporting the CSV by hand, and repairing it would not help,
  because G4 would still fail.
- P0 questions this candidate can test: `[추론]` None that `SRC-002` does not already cover.
  A hand-exported 96-row CSV would exercise the import path and nothing else, which is what
  the self-authored JSONL was accepted for.
- Known representativeness limits: `[추론]` This profiles one catalogue entry and the
  provider's cosmetics indicator tree. KHIDI publishes other cosmetics material — 보건산업통계집
  volumes, 실태조사 microdata — that was not profiled, and this result says nothing about
  those. `[가설]` A KHIDI 실태조사 microdata release could carry firm-level rows; whether any
  reaches product or ingredient level is untested and is the only direction here worth a
  further hour.
- Proposed next action: `[결정]` Report both `NO-GO`s to the orchestrator and stop. Both
  candidates the execution plan named for the dataset half are exhausted, and the plan's own
  rule applies: *"Expanding beyond this table requires recording why every listed candidate
  failed a hard check."* That record is [`SRC-003`](SRC-003-open-beauty-facts.md) and this
  file. Choosing what happens next — expand the candidate set, accept `SRC-002` as the
  charter's dataset with the substitution stated, or change the charter — is an owner
  decision, not a worker's.
