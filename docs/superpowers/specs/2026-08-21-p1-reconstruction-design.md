# P1 재구축 설계

- 문서 지위: **설계 초안 (DRAFT)** — 2026-08-21 브레인스토밍 세션 산출물
- 이 문서는 수락된 결정 기록이 아니다. `docs/conventions/project-memory.md`에 따라,
  여기 담긴 오너 답변은 **M0에서 Decision Packet으로 공식화된 뒤에야** 제약이 된다.
- 입력: `plan.md`(오너 선택기준), Cosmai P0 능력 지도(Artifact, 2026-08-20),
  P1 Entry Gate 관련 문서 일체, trend-radar(1.0.0)·yt-scrapper(`5bce7f6`) 탐색 보고.

## 1. 배경

`[확인 사실]` P0-B는 헌장 기준 작업 완료 상태이고 P1 Entry Gate는 미개최다. 게이트가
수락하는 네 산출물(Architecture Synthesis, PoC Contract 0.1, 처분 등록부, P1 재구축
계획)은 전부 미수락 초안이며, `apps/`는 게이트 수락 전까지 비어 있어야 한다.
P0 아카이브 태그도 없다.

`[결정]` (plan.md) 오너는 P1 재구축 진입을 지시했고, 능력 지도 32항목에 대한
선택을 내렸다. 이 문서는 그 선택을 설계로 구체화한다.

## 2. 재구축 선택기준 — 능력 지도 처분표

능력 지도 항목 번호를 그대로 쓴다. "오너 선택"은 plan.md와 2026-08-21 세션 답변.

### 2.1 획득

| 항목 | 오너 선택 | P1 처리 |
|---|---|---|
| 1.1 실제 REST 소스 수집 | 경량 소스는 내부 수집기 직접 구현 허용, 무거운 주기 수집은 외부 서비스+어댑터 | NAVER는 내부 수집기로 재구축. **DP-026 D2의 부분 수정을 DP로 기록** |
| 1.2 독립 스크래퍼 어댑터 | 채택 (1.1 기준 적용) | trend-radar·tubedepth 어댑터 신규 (§5) |
| 1.3 데이터셋 파일 Raw 취득 | 채택 | `importer.local.jsonl` 재구축 |
| 1.4 미승인 URL 차단 | 보안 추천목록 이관 | outbound 프로파일 구조는 유지(계약 1.3의 일부), 강제 수위는 추천목록 문서로 |
| 1.5 DNS 실패·재바인딩 | 필요없음 | 미구현으로 기록 |

### 2.2 Raw와 스냅샷

| 항목 | 오너 선택 | P1 처리 |
|---|---|---|
| 2.1 무손실 Raw·출처 보존 | 채택 | PoC Contract 0.1 §2 그대로 |
| 2.2 봉인 스냅샷 변조 탐지 | 채택 | §4 그대로 |
| 2.3 Raw 진화 후 재생 | **실체화 스냅샷 유지** | 봉인 시 바이트 복사를 계약으로. TASK-005 측정이 근거 |
| 2.4 동일 키 동률 선택 | **시퀀스 최신 행** | `raw_item`에 bigint 단조 시퀀스 추가, 동일 `item_key`는 최대 시퀀스 행 선택. P1-INHERITED-DEFECTS §5(a) 수리 |
| 2.5 클러스터 간 매니페스트 | **bytewise 정렬 고정** | 멤버 정렬을 UTF-8 바이트 순으로 고정(collation 비의존). §5(b) 수리 |
| 2.6 삭제 의무 | **보안 추천목록 이관** | 미설계로 기록. 실체화 스냅샷의 사본 2개(snapshot_item, raw_envelope) 문제를 추천목록 항목에 명시 |

### 2.3 정규화

| 항목 | 오너 선택 | P1 처리 |
|---|---|---|
| 3.1 결정적 정규화 | 계약 요구에서 제외 | 정규화 시점 메타데이터(애드온 버전, 실행 시각, snapshot id)로 보조. 향후 LLM/ML 정규화기 고려 |
| 3.2 이질 레코드 한 스키마 | 봉투+유니온 유지 | Schema 0.3 계승, 새 `record_type`은 마일스톤 등록 |
| 3.3 정규화 버전 공존 | 채택 | §5 그대로 (UPDATE 없음, "현재" 플래그 없음) |
| 3.4 규칙 기반 품질 판정 | 하지 않음 | `normalizer.rule.baseline` 미승계 |
| 3.5 clean 자기 보증 | 보증 안 함 | 해당 없음 (3.4 소거로 자동 해소) |
| 3.6 불량 행 내성 | **결측치 치환 + 레코드 단위 에러 표기** | 레코드 실패는 skip하지 않고 결측+`notes`의 정규화 에러로 기록, 실행 계속. P1-INHERITED-DEFECTS §1 수리 — **P1 요구사항** |

### 2.4 실행과 복구

| 항목 | 오너 선택 | P1 처리 |
|---|---|---|
| 4.1 병렬 클레임 안전 | 필요 | CONTRACT-JOB 0.1 재구축 |
| 4.2 재시도·중단·리스 회복 | 필요 | 동일 |
| 4.3 수집·정규화 독립 복구 | 필요 | 별도 잡 도메인 유지 |
| 4.4 host 멤버 순서 보증 | 필요없음 | 3.1 제외와 일관. 미보증으로 기록 |

### 2.5 운영 가시성

| 항목 | 오너 선택 | P1 처리 |
|---|---|---|
| 5.1 DB 없이 실행 상태 확인 | 채택 | 대시보드 §7 |
| 5.2 import 작업 생성 | 필요 | 대시보드에서 생성 |
| 5.3 카드·트렌드 화면 | 마일스톤 | 이슈/마일스톤 등록만 |

### 2.6 제품 판단

| 항목 | 오너 선택 | P1 처리 |
|---|---|---|
| 6.1 기회 카드 | 기능 후보 이슈 등록 | 필수 아님 |
| 6.2 한국 시장 데이터셋 | 이 방식으로 안 함 | Open Beauty Facts 경로는 importer 시연용으로만 |
| 6.3 결정적 트렌드 분류 | 마일스톤 | 등록만 |
| 6.4 성분 완전성 판단 | 마일스톤 | 등록만 |

### 2.7 보안과 권리

| 항목 | 오너 선택 | P1 처리 |
|---|---|---|
| 7.1 시크릿 비저장 | 프로그램 공통 설정으로 유지, 대시보드 입력 | **외부 시크릿 파일 기록** 방식 (§8). 값의 DB·저장소·환경변수 반입 금지 불변식 유지 |
| 7.2 리다이렉트·주소 범위 | 보안 추천목록 이관 | 추후 선택 개발 |
| 7.3 SEC-006 | 보안 추천목록 이관 | **waiver가 아닌 P1 범위 결정**으로 DP 기록 — 재구축 계획 Phase 0.3 충족 |
| 7.4 ODbL 재배포 의무 | 내부 테스트용이므로 의무 없음 | `[확인 사실]` 의무는 **첫 발행 시점에 부착**된다(카드·export·공개 대시보드). 이 결정이 덮지 않는 범위: 향후 외부 발행. OQ-015는 열린 채 유지 |

## 3. 세션에서 확정된 결정 (M0에서 DP화 대상)

1. 실체화 스냅샷 유지 (2.3)
2. 동일 키 동률은 단조 시퀀스 최신 행 (2.4)
3. 매니페스트 멤버 정렬 bytewise 고정 (2.5)
4. 삭제 의무 보안 추천목록 이관 (2.6)
5. DB: 공유 PostgreSQL 서버 + cosmai **전용 database** (스키마 분할 아님)
6. 시크릿: 대시보드 입력 → 외부 시크릿 파일(`~/.config/cosmai/env`) 기록, UI는 쓰기 전용
7. P0 재사용: 계약 기준 재구축 + 복사·개작 허용, import 의존 금지
8. 접근 방식: **B. 충실 재구축** (5영역, 4버전축, conformance suite, addon_kit 재현)
9. yt-scrapper 기준점: release 브랜치 `5bce7f6`, **작업 중 새 릴리즈 태그가 생기면 그 태그로 전환** (plan.md의 "0.1.0"은 착오, 1.0.0 의도)
10. main 병합·v0.1.0 태깅: **P1 시연 완성 후**
11. 백엔드 DB 스택: P0식 psycopg3 직접 (복사·개작)
12. 대시보드: MUI + React Router + TanStack Query 채택 (프로젝트 등재 기본값)

## 4. 아키텍처

### 4.1 저장소 구조 (5영역 미러링)

```text
apps/
  platform_core/   # 잡·클레임·리스·재시도·API 수명주기 — CONTRACT-JOB 0.1
  domain/          # source·cursor·Raw·snapshot·normalized — PoC Contract 0.1
  addon_api/       # 계약 재구축 — CONTRACT-ADDON-1.3.md 기준
  addon_host/      # 발견·로딩·capability 바인딩·버전 게이트
  addon_kit/       # new / run 스캐폴딩과 오프라인 하니스
  addons/          # 디렉터리당 애드온 하나
  scheduler/       # 신규 — 정기 수집
  dashboard/       # React + TS + MUI
```

의존 방향 규칙과 계층 방향 테스트(`test_addon_layer_direction`)를 P1 트리에 재구축한다.
프로세스: API 서버(loopback), 워커, 스케줄러, 대시보드.

### 4.2 데이터베이스

- 공유 서버에 database `cosmai`, schema `cosmai`(`public` 비움). 역할
  `cosmai_owner`(NOLOGIN) / `cosmai_migrator` / `cosmai_runtime` 분리, runtime에
  `statement_timeout`·`lock_timeout`·`idle_in_transaction_session_timeout` 설정.
- `service-db.json` manifest + 프로비저닝 SQL을 둔다 (tubedepth의
  `deploy/postgres-bootstrap.sql` 패턴, 운영 규정의 manifest 요구 충족).
- 마이그레이션: P0의 SQL 파일 적용기를 복사·개작 — version table을 `cosmai` 스키마
  안에, 모든 DDL schema-qualified. startup 경로 DDL 금지.
- 커넥션 예산 초안 16 (API 4, 워커 4, 스케줄러 2, 마이그레이션 1, 여유 5) —
  manifest에 기록하고 `CONNECTION LIMIT`로 고정.
- 테이블: P0 DDL 계승(`job`, `job_attempt`, `platform_effect`, `source`,
  `source_cursor`, `raw_envelope`, `raw_item`, `snapshot`, `snapshot_item`,
  `normalized_result`) + 변경 3건: `raw_item.seq bigint generated always as identity`,
  스냅샷 선택·정렬의 bytewise 규칙, `schedule` 테이블 신규
  (`source_id`, `interval`, `enabled`, `next_run_at`, `last_run_at`).
- 시각 컬럼은 instant 의미면 `timestamptz` (운영 규정 §9).
- DB 접속 크리덴셜(공유 서버라 비밀번호 존재)은 시크릿 파일의 `COSMA_DB_*` 키로.

## 5. 수집기

목표 6에 따라 **수집 도메인당 수집기 하나**가 대시보드 관리 단위다.

### 5.1 `collector.trendradar.rest` — 뷰티 트렌드 도메인

- 대상: trend-radar 1.0.0, `http://127.0.0.1:8000/api/v1`. **무인증** — credential 불필요.
- `[확인 사실]` 델타/커서 export가 없다. PK 컬럼 정확일치 필터만 지원.
- 수집 방식: `/api/v1/runs`(또는 `/health`)로 새 시간 버킷 발견 →
  시간 버킷 테이블(`rank_snapshot`, `price_point`, `review_stats`,
  `review_summary`, `review_topic`)은 `source+board(해당 시)+captured_at` 정확일치로
  페이지 상한(1000) 안에서 수집. 기록 일회성 테이블(`product`, `review`,
  `review_answer`, `new_product`)은 주기 전체 페이징 재수집 — 중복 행은 스냅샷
  봉인의 키별 최신 선택으로 해소되며, Raw 증가 비용은 낮은 주기로 완화한다(알려진 비용).
- 커서: 테이블별 마지막 처리 시간 버킷.
- Raw: API 응답 페이지 하나 = envelope 하나, 레코드 하나 = `raw_item` 하나,
  `item_key`는 해당 테이블 자연키의 결합.
- `[확인 사실]` 미인지 쿼리 파라미터는 조용히 무시된다 — 응답의 `filters` 에코를
  요청과 대조 검증한다.

### 5.2 `collector.tubedepth.rest` — YouTube 도메인

- 대상: yt-scrapper(tubedepth) `release/2026-08-21-postgres-cutover` = `5bce7f6`,
  `http://127.0.0.1:8080`. 새 릴리즈 태그가 생기면 그 태그로 전환.
  `[측정]` 2026-08-21 라이브 인스턴스의 openapi가 release 전용 라우트
  (`/v1/artifacts/{digest}`, `/v1/control`, `/v1/jobs/batch`)를 서빙 — 실행 중인
  코드는 release 브랜치이고 버전 문자열(`0.1.0`)만 미갱신.
- 인증: `X-API-Key`(`ytd_...`) — **credential part로 protected header에 부착**
  (DP-018 체계 그대로). 분당 60 요청 제한 준수.
- 수집 방식: `GET /v1/artifacts?since=<워터마크>` → keyset cursor 페이징 →
  `GET /v1/artifacts/{digest}` 역참조로 payload 취득.
- 커서: 처리 완료한 최대 `fetched_at` 워터마크.
- `item_key = kind|target|fetched_at` (digest는 내용 주소라 관측 식별자가 아님).
- 오류 처리: digest 역참조의 404(보존기간 초과)·409(schema version 미기록)·
  retracted를 구분해 기록. `[확인 사실]` **보존기간 30일** — 스케줄 기본 주기를
  일 단위 이하로 두고 대시보드에 마지막 성공 수집 시각을 표시한다.
- 잡 생성(`POST /v1/jobs`, `/v1/jobs/batch`)은 1차 범위 밖 — 수집은 이미 쌓인
  artifacts를 읽는 것으로 시작. 잡 생성 트리거는 마일스톤 후보.

### 5.3 `collector.naver.blog` / `collector.naver.datalab` — NAVER 도메인

- P0의 세 수집기(blog, searchtrend, shoppinginsight)를 참조해 재구축. 내부 직접
  호출(1.1). datalab 계열 둘은 하나의 수집기로 합칠지 재구축 시 판단(구현 선택).
- 크리덴셜: 기존 `COSMA_SRC_*` 체계, `~/.config/cosmai/env`에 NAVER 키 존재.

### 5.4 `importer.local.jsonl`

- P0 참조 재구축. 데이터셋 파일 Raw 취득 경로(2.1.3 채택)의 시연 대상.

### 5.5 정기 수집 (스케줄러)

- `schedule` 행 기반: enabled 소스에 대해 `next_run_at` 도래 시 collect 잡 생성.
- 정규화는 수동 시작 유지 + 선택적 스케줄(수락된 원칙 그대로).
- 대시보드에서 소스별 주기 설정·활성/비활성.

## 6. 정규화 — 관리 틀 우선

- Schema 0.3(봉투 + `record_type` 유니온) 계승. 새 소스의 record_type
  (trend-radar rank/review 계열, youtube video 계열)은 **마일스톤으로 등록만** 하고
  1차에서는 기존 3종 정규화기(blog document, trend_point, obf product) 수준 재구축.
- 불량 행 내성(2.3.6): 레코드 단위 실패 → 결측치 + `notes`에
  `{normalize_error: {field, reason}}` 기록, 실행 계속. 실행 요약에 에러 레코드 수 집계.
- UI: 스냅샷 선택 → 정규화기·버전 선택 → run 생성 → 결과 버전 열람. 버전 공존 표시.

## 7. 대시보드

MUI + React Router + TanStack Query. 화면:

1. **수집기 도메인 화면** (도메인당 하나): 상태, 스케줄 설정, config 폼(manifest의
   config schema에서 생성), **크리덴셜 입력**(§8), 작업 이력, 마지막 성공 수집.
2. **자료 브라우저**: 도메인별 Raw 아이템 전체 페이지네이션 열람. payload 미리보기.
   `[결정]` P0가 거부하던 운영자 Raw 열람을 허용 — M0에서 DP로 기록
   (로컬 운영자 경계 안이므로, redaction 경로는 유지).
3. **다운로드**: 범위조건(source, 기간, item_key 접두사) → 스트리밍 export.
   Raw는 **JSONL 기본**(payload 무손실, 재임포트 가능) + CSV 옵션(메타데이터 컬럼 +
   payload 문자열 컬럼). 정규화 결과는 CSV 평탄화.
4. **정규화 관리** (§6).
5. **잡 모니터링**: P0 화면 기능 계승(목록·필터·상세·attempt·protected debug·재시도).
6. **헬스·메트릭**: P0 계승 + 스케줄러 상태.

loopback 바인딩·무인증 전제 유지 (SEC-005).

plan.md의 "원하는 목표" 매핑: 목표 1(정기 수집·현황·기록) → §5.5 + 화면 1·5·6 /
목표 2(도메인별 전체 열람) → 화면 2 / 목표 3(Raw 추출·범위 다운로드) → 화면 3 /
목표 4(정규화 관리 틀) → §6 + 화면 4 / 목표 5(시크릿 파악·입력) → §8
(trend-radar 무인증, tubedepth `X-API-Key`, NAVER 키 기존 보유 — 사전 파악 완료) /
목표 6(도메인당 수집기 하나) → §5 관리 단위 + 화면 1.

## 8. 시크릿

- 대시보드 수집기 화면의 크리덴셜 필드 → API가 `~/.config/cosmai/env`
  (저장소 밖, mode 600)에 `COSMA_SRC_<SOURCE_ID>_<PURPOSE>=값` 기록.
- **쓰기 전용**: 값 재표시 없음. 화면에는 ref 이름과 설정 여부만.
- 유지되는 불변식: 값의 저장소 트리·DB·환경변수·로그·화면·Raw 반입 금지,
  워커 경계에서 요청 수명 동안만 해소, 미해소 시 `CONFIGURATION_INVALID`.
- 완화되는 부분(⚠ DP 필요): API 프로세스가 **입력 순간에 한해** 값을 경유한다.
  기존 규약은 대시보드/API의 값 접촉을 전면 금지했다. 완화 범위를 "쓰기 경로
  1회 경유, 로그 금지, 응답 에코 금지"로 좁혀 기록한다.

## 9. 실행 계획

| 마일스톤 | 내용 | 병렬화 |
|---|---|---|
| M0 | DP 작성(§3 전부 + DP-026 수정 + Raw 열람 + 시크릿 완화), 재구축 계획 갱신, 게이트 개최·오너 수락, P0 아카이브 태그 | 직렬 (게이트가 관문) |
| M1 | `platform_core` + DB 프로비저닝·마이그레이션 | — |
| M2 | `domain` (수정 3건 포함) | M1 후 |
| M3 | `addon_api`·`addon_host`·`addon_kit` + conformance suite | M2와 부분 병렬 |
| M4 | 애드온 5종 | **워크트리 병렬** (애드온당 1) |
| M5 | 대시보드 | M2부터 백엔드와 병렬 |
| M6 | 스케줄러·다운로드 | M4·M5와 병렬 |
| M7 | 통합 시연 검증, issue/PR 정합성 점검, main 병합, **v0.1.0 태깅** | 직렬 |

worker/attacker 분리(agent workflow)를 마일스톤 단위로 유지 — 특히 outbound 가드,
스냅샷 봉인, 시크릿 경로는 적대적 리뷰 대상으로 명시한다 (P0에서 결함이 측정된 부분).

## 10. 테스트·검증 (B 수준)

- P0 테스트 계보를 참조해 시나리오를 재현하되, P1 트리에서 새로 작성한다.
- 필수 재현: JOB-001…008, OPS-001…004, SEC 시나리오, 계층 방향 테스트,
  스냅샷 봉인·변조·재생(수정 3건의 회귀 포함), 트랜잭션 경계(연결에 묻기),
  conformance suite.
- 신규: 어댑터 2종의 계약 테스트(응답 fixture 기반 — 실서비스 미기동 시에도 실행),
  스케줄러, 다운로드 스트리밍, 시크릿 쓰기 경로.
- 도구: `mypy --strict`, `ruff` — P0 설정 계승.

## 11. 비범위와 열린 항목

- 비범위: 카드·트렌드 화면(5.3), 제품 판단 전부(6.x — 이슈/마일스톤 등록),
  DNS 대응(1.5), 삭제 의무(2.6), SEC-006·리다이렉트 방어(7.2·7.3 — 추천목록),
  tubedepth 잡 생성 트리거, 인증 있는 대시보드, 스케일 인프라.
- 열린 항목: OQ-010(다중 스트림 커서 — tubedepth kind별 스트림에서 재부상 가능),
  OQ-013, OQ-015(첫 발행 시), 새 record_type 설계.
- `[측정]` trend-radar(1.0.0, :8000)·tubedepth(release 표면, :8080) 모두
  2026-08-21 현재 **실행 중** 확인. PostgreSQL이 :5432·:5433에서 수신 중.
- `[확인 사실]` 에이전트 샌드박스의 루프백 격리 때문에 기본 상태의 셸에서는 두
  서비스 연결이 거부된다 — M4 이후 어댑터 검증 시 로컬 네트워크 접근 허용이
  필요하다는 점을 작업 절차에 명시할 것.
