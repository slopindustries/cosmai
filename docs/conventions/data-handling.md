# Data Handling Convention

- 문서 지위: 활성 프로젝트 convention
- 적용 범위: source probe, fixture, import, Raw runtime data, experiment artifact
- 최종 수정일: 2026-08-16

## 목적

Cosmai은 외부 source와 dataset을 실제로 처리한다. 기술적으로 다운로드할 수 있다는 사실은 Git 재배포나 에이전트 처리를 허용한다는 뜻이 아니다. 모든 입력은 다음 두 질문을 별도로 판단한다.

1. 이 내용을 Git 또는 다른 공유 저장소로 재배포할 수 있는가?
2. 이 내용을 현재 에이전트와 도구가 처리하도록 허용할 수 있는가?

두 질문 중 하나라도 `UNKNOWN`이면 더 넓은 접근 등급으로 올리지 않는다.

## 저장 등급

| Class | Git | Agent access | Intended use |
|---|---|---|---|
| `public` | 허용 | 허용 | 작고 재배포 가능한 review/acceptance fixture |
| `local` | 금지 | 명시적으로 허용 | 재배포는 불가하지만 약관과 데이터 분류상 agent processing이 허용된 P0 input |
| `private` | 금지 | 금지 | 개인정보, credential, 기밀자료 또는 agent processing이 승인되지 않은 내용 |

### `public`

- 위치: `tests/fixtures/public/`
- source/generator, capture time, rights, hash, transformation과 대표성을 기록한다.
- 원본의 일부를 잘랐거나 redaction했다는 사실만으로 재배포 권리가 생기지 않는다.
- 파일 확장자는 분류 근거가 아니다. CSV, JSON, Parquet 등 어떤 형식도 동일한 정책을 따른다.

### `local`

- fixture 위치: `tests/fixtures/local/`
- P0 runtime 위치: `var/`
- Git에서 제외하지만 에이전트가 실험을 위해 읽을 수 있다.
- agent processing을 허용하는 약관 또는 사용 근거를 manifest에 기록한다.
- Git에는 데이터 대신 metadata, content hash, retrieval/generation procedure만 남긴다.

### `private`

- 위치: `tests/fixtures/private/` 또는 `data/private/`
- Git과 에이전트 접근을 모두 금지한다.
- 자동 실험이나 acceptance test가 이 경로의 내용을 필수 입력으로 사용해서는 안 된다.
- private 자료가 필요하다는 사실만 기록하고, 사람이 별도 절차로 검토한다.

## Source와 fixture 승격

Source probe output을 `public` fixture로 승격하려면 다음이 모두 충족되어야 한다.

- redistribution basis가 확인되어 있다.
- credential, personal data, restricted header와 불필요한 identifier가 없다.
- original content hash와 transformation이 기록되어 있다.
- sample이 대표하는 behavior와 대표하지 못하는 범위가 설명되어 있다.
- 연결된 contract와 expected edge case가 기록되어 있다.

조건을 충족하지 못하면 `local`로 유지하거나 hash와 retrieval procedure만 보존한다.

## Experiment artifact 보존

Git에 보존한다:

- 완료된 experiment record
- sanitization된 측정 summary와 manifest
- 작은 `public` fixture와 deterministic expected output
- Decision Packet의 근거가 된 표, hash와 재현 명령

Git에 보존하지 않는다:

- runtime Raw log와 local database
- 다운로드 원본과 restricted dataset
- token 또는 source-protected data가 포함될 수 있는 debug dump
- 재생성 가능한 cache와 임시 output

외부 또는 local-only artifact를 evidence로 사용하면 위치 또는 retrieval procedure, hash algorithm과 value, 생성 시각, 보존 책임을 experiment record에 남긴다.

## 판정 checklist

- Terms 또는 license를 실제로 확인했는가?
- Redistribution과 agent processing을 별도로 판단했는가?
- `UNKNOWN`을 허용으로 해석하지 않았는가?
- Fixture와 metadata의 hash가 일치하는가?
- Secret과 개인정보가 log, screenshot, error, manifest에 유출되지 않았는가?
