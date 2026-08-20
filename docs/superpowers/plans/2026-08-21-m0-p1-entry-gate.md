# M0 — P1 Entry Gate 닫기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 브레인스토밍에서 확정된 결정들을 Decision Packet으로 공식화하고, P1 Entry Gate를 개최·수락시켜 `apps/` 개발을 열 수 있는 상태를 만든다.

**Architecture:** 순수 문서 마일스톤이다 — 코드 없음. DP 6건 + 등록부 2건을 쓰고, 기존 게이트 산출물 2건(P1 재구축 계획, project-state)을 갱신하고, 게이트 기록을 채워 적대적 리뷰를 통과시킨 뒤 오너 수락으로 닫는다. 이후 마일스톤(M1~M7)은 여기서 수락된 DP를 인용한다.

**Tech Stack:** Markdown 문서, `git`, `uv run pytest tests/environment` (저장소 구조 가드), `adversarial-reviewer` 서브에이전트.

**Spec:** `docs/superpowers/specs/2026-08-21-p1-reconstruction-design.md` — 이 계획은 스펙 §2(처분표)·§3(확정 결정 12건)·§9(M0 행)을 구현한다.

## Global Constraints

- 작업 브랜치 `p1/entry-gate` (dev에서 분기), 완료 시 `git merge --no-ff`로 dev 병합. squash·rebase 금지.
- 커밋 메시지는 저장소 관례대로 서술형 문장 (conventional-commit 접두사 없음). 매 커밋에 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` 트레일러.
- push는 오너가 요청할 때만.
- 모든 새 문서는 기존 결정 문서의 관례를 따른다: 영어 본문 + `[확인 사실]`/`[측정]`/`[추론]`/`[가설]`/`[결정]` 라벨, 상대경로 링크.
- DP는 `docs/decisions/DP-TEMPLATE.md`의 섹션 전부를 유지한다 (Decision question / Candidates / Hypotheses and falsification / Experiment / Evidence / Decision / Rejected alternatives / Tradeoffs and risks / Remaining uncertainty / Required changes).
- 오너 확인 필드: `CONFIRMED (project owner, 2026-08-21, brainstorming session — docs/superpowers/specs/2026-08-21-p1-reconstruction-design.md)`. 스펙이 커밋된 오너 답변 기록이다.
- 통제를 주장하는 곳마다 **그 통제가 덮지 않는 범위를 함께 기록**한다 (`docs/conventions/project-memory.md`).
- 각 태스크 끝에서 `uv run pytest tests/environment -q` 실행 — 저장소 구조 가드가 깨지지 않았는지 확인 (기대: 전부 PASS).
- P0 문서를 수정할 때 역사 문장을 삭제하지 않는다 — 정정은 덧붙여 기록한다 (기존 문서들이 그렇게 한다).

---

### Task 1: 브랜치 생성

**Files:** 없음 (git 조작만)

**Interfaces:**
- Produces: 브랜치 `p1/entry-gate` — 이후 모든 태스크가 이 브랜치에서 커밋.

- [ ] **Step 1: dev 최신 상태 확인 후 분기**

```bash
git -C /home/user1/github_prj/Main/service/cosmai status --short   # plan.md 외 깨끗해야 함
git -C /home/user1/github_prj/Main/service/cosmai switch -c p1/entry-gate dev
```

- [ ] **Step 2: 가드 테스트 기준선 확인**

Run: `uv run pytest tests/environment -q`
Expected: 전부 PASS (실패 시 기준선 문제 — 진행 전에 오너에게 보고).

---

### Task 2: 보안 추천목록 등록부

**Files:**
- Create: `docs/conventions/security-recommendations.md`

**Interfaces:**
- Produces: 항목 id `SR-001`~`SR-005` — DP-029 D4, DP-034가 링크.

- [ ] **Step 1: 등록부 작성**

필수 내용 (서문 + 표):
- 서문: 이 문서는 **선택적 후속 구현 후보의 등록부**이며, 항목이 여기 있다는 것은 "P1이 이 통제 없이 동작한다"는 수락된 결정을 뜻한다고 명시. 각 항목에 "부재가 의미하는 것" 열을 두어 과대 주장 방지.
- 표 (id / 항목 / 출처 / 부재가 의미하는 것):
  - `SR-001` 미승인 URL 강제 차단 수위 — 능력 지도 1.4, plan.md §1.4. outbound 프로파일 **구조**는 계약에 남고(엔드포인트 명명·credential 부착에 필요), 여기로 오는 것은 강제 수위(전 주소 범위 검사·loopback 플래그 등의 재구현 여부).
  - `SR-002` DNS 실패·재바인딩 대응 — 능력 지도 1.5. P0도 미검증(`NOT EXERCISED`).
  - `SR-003` 삭제 의무 이행 경로 — 능력 지도 2.6, DP-029 D4. 부재의 의미: `raw_item` 삭제 후에도 `snapshot_item`·`raw_envelope`에 사본 2개가 남아 "지웠다"고 말할 수 없음 (TASK-005 측정).
  - `SR-004` 리다이렉트·주소 범위 방어 재구현 — 능력 지도 7.2.
  - `SR-005` SEC-006 — 능력 지도 7.3. **DP-023 waiver의 승계가 아니라 DP-034의 P1 범위 결정**임을 명시 (waiver는 게이트에서 만료).

- [ ] **Step 2: 링크 검증**

Run: `grep -c "SR-00" docs/conventions/security-recommendations.md`
Expected: 10 이상 (5개 항목 id가 표와 서문에 존재).

- [ ] **Step 3: 커밋**

```bash
git add docs/conventions/security-recommendations.md
git commit -m "Open the security recommendations register, where absence is a recorded decision"
```

---

### Task 3: DP-029 — P1 스냅샷 정체성과 재생

**Files:**
- Create: `docs/decisions/DP-029-p1-snapshot-identity.md`
- Modify: `docs/open-questions/OQ-004-snapshot-boundary.md` (Status 갱신 + 해결 문단 추가)

**Interfaces:**
- Consumes: `SR-003` (Task 2)
- Produces: `DP-029` D1~D4 — Task 10·11·12와 M2 계획이 링크.

- [ ] **Step 1: DP-029 작성**

템플릿 전 섹션 유지. Status `ACCEPTED_FOR_POC`. Related Open Questions: OQ-004 (resolves for P1). 결정 내용:
- **D1** P1 스냅샷은 **실체화(materialized)**: 봉인 시점에 멤버 바이트를 스냅샷 테이블로 복사. 근거 `[측정]`: TASK-005의 4단계(additive migration → 후속 수집 → purge) 바이트 동일 재생, 참조 설계는 3단계 분기·4단계 무반환.
- **D2** 동일 `item_key` 다중 관측의 선택은 `raw_item`의 **단조 증가 bigint 시퀀스** 최대 행. `emitted_at`(트랜잭션 타임스탬프) 동률 문제와 `uuid4` 낙하(12회 재봉인에서 3키 중 2키가 낡은 payload 선택)를 근거로 인용 — `P1-INHERITED-DEFECTS.md` §5(a)의 수리.
- **D3** 매니페스트 멤버 정렬은 **UTF-8 바이트 순(bytewise)** 고정 — collation 비의존. DP-019 D5의 미명세(로케일만 다른 두 클러스터가 다른 digest)를 근거로 인용 — §5(b)의 수리. DP-019 D5를 좁히는 것이지 뒤집는 것이 아님을 명시.
- **D4** 삭제 의무는 P1에서 **미설계** — `SR-003`으로 이관. Remaining uncertainty에 "이 결정이 덮지 않는 것": 향후 권리자 삭제 요청·외부 발행 시점(OQ-015)의 처리.
- Rejected alternatives: 참조 설계(측정이 반증), `observed_at` 우선 선택(소스마다 시각 필드 필요 — 세션에서 기각), collation 미고정(비용 0으로 고칠 수 있는데 방치할 이유 없음).
- Required changes: M2 domain 마이그레이션(`raw_item.seq`), 스냅샷 봉인 구현, project-state §4 등재.

- [ ] **Step 2: OQ-004 갱신**

Status를 `RESOLVED`로. 파일 하단에 해결 문단 추가: "Resolved for P1 on 2026-08-21 by [DP-029]. D1이 실체화를, D2가 동률 선택을, D3가 정렬 collation을 닫는다. 본문의 측정 기록은 그 근거로 보존된다." 기존 본문은 삭제하지 않는다.

- [ ] **Step 3: 검증**

Run: `grep -n "DP-029" docs/open-questions/OQ-004-snapshot-boundary.md && grep -n "RESOLVED" docs/open-questions/OQ-004-snapshot-boundary.md && uv run pytest tests/environment -q`
Expected: 두 grep 모두 매치, 테스트 PASS.

- [ ] **Step 4: 커밋**

```bash
git add docs/decisions/DP-029-p1-snapshot-identity.md docs/open-questions/OQ-004-snapshot-boundary.md
git commit -m "Decide what a P1 snapshot is, and close OQ-004 with the two identity gaps repaired on paper"
```

---

### Task 4: DP-030 — P1 정규화 범위

**Files:**
- Create: `docs/decisions/DP-030-p1-normalization-scope.md`

**Interfaces:**
- Produces: `DP-030` D1~D5 — Task 10·12와 M2·M4 계획이 링크.

- [ ] **Step 1: DP-030 작성**

Status `ACCEPTED_FOR_POC`. Related Open Questions: OQ-003 (부분 — 프로토콜 자체는 계약 1.3 재구축에 남음). 결정 내용:
- **D1** 결정적 정규화는 P1 계약 요구에서 **제외**. 정규화 시점 메타데이터(애드온 id·버전, 실행 시각, snapshot id)를 `normalized_result`에 보존해 보조. `[확인 사실]` P0는 강한 형태로 측정 성립했으나, 오너는 향후 LLM/ML 정규화기를 고려해 계약 요구로 승격하지 않기로 함 (plan.md §3.1).
- **D2** **레코드 단위 불량 내성은 P1 요구사항**: 레코드 실패 시 결측치 치환 + 레코드 `notes`에 `normalize_error {field, reason}` 기록, 실행 계속, 실행 요약에 에러 레코드 수 집계. `P1-INHERITED-DEFECTS.md` §1(고립 서로게이트 한 행이 실행 전체 중단)의 수리.
- **D3** 규칙 기반 품질 판정과 `clean` 자기 보증은 하지 않음 — `normalizer.rule.baseline` 미승계 (plan.md §3.4·3.5).
- **D4** Schema 0.3(봉투 + `record_type` 유니온) 승계. 새 record_type은 마일스톤 등록 (Task 9).
- **D5** host의 멤버 순서 보증은 요구하지 않음 — D1과 일관 (plan.md §4.4).
- Remaining uncertainty: D1이 덮지 않는 것 — 재현 가능한 정규화 결과를 요구하는 미래 계약; 유니온 멤버 증가 반증 조건(멤버 수가 소스 수에 근접) 유지.

- [ ] **Step 2: 검증 후 커밋**

Run: `uv run pytest tests/environment -q`
```bash
git add docs/decisions/DP-030-p1-normalization-scope.md
git commit -m "Scope P1 normalization: fault-tolerant per record, deterministic by metadata only, judged by nobody"
```

---

### Task 5: DP-031 — 수집기 위상 수정

**Files:**
- Create: `docs/decisions/DP-031-p1-collector-topology.md`

**Interfaces:**
- Produces: `DP-031` D1~D4 — Task 10·12와 M4 계획이 링크.

- [ ] **Step 1: DP-031 작성**

Status `ACCEPTED_FOR_POC`. 결정 내용:
- **D1** **DP-026 D2를 수정**: 이후 추가 수집기 전부에 어댑터 위상을 요구하던 구속을, "무거운 주기 수집은 외부 서비스+어댑터, 경량 소스는 내부 수집기 허용"으로 완화 (plan.md §1.1). DP-026 D2를 SUPERSEDED로 바꾸지 않고 이 DP가 좁힌다고 양쪽에 기록 (DP-026에 전방 링크 한 줄 추가는 Task 10에서).
- **D2** NAVER 수집기들은 내부 직접 호출로 재구축. P0의 3종은 `ARCHIVE_REFERENCE_ONLY` 유지 — 참조·복사 원본이지 의존성이 아님.
- **D3** 어댑터 대상 2종 확정: **trend-radar 1.0.0** (`http://127.0.0.1:8000/api/v1`, 무인증, 시간버킷+PK 필터 수집) / **tubedepth** (`http://127.0.0.1:8080`, `X-API-Key`, artifacts 증분 경로). tubedepth 기준점은 `release/2026-08-21-postgres-cutover` = `5bce7f6`이며 **작업 중 새 릴리즈 태그가 생기면 그 태그로 전환** — plan.md의 "0.1.0"은 오너가 착오로 확인 (1.0.0 의도). `[측정]` 2026-08-21 라이브 인스턴스가 release 전용 라우트를 서빙.
- **D4** 데이터 교환은 REST API로만 — 스크래퍼 DB 직접 읽기 금지 (DP-012 보존). 수집 스케줄은 COSMAI의 스케줄러가 collect 잡 생성으로 수행.
- Tradeoffs: 내부 수집기 허용은 P1이 두 이음매(직접 호출·어댑터)를 계속 지는 것 — DP-026이 이미 기록한 하이브리드의 연장.

- [ ] **Step 2: 검증 후 커밋**

Run: `uv run pytest tests/environment -q`
```bash
git add docs/decisions/DP-031-p1-collector-topology.md
git commit -m "Amend the collector topology: light sources collect in-process, heavy ones stay behind adapters"
```

---

### Task 6: DP-032 — 데이터베이스 배치

**Files:**
- Create: `docs/decisions/DP-032-p1-database-placement.md`

**Interfaces:**
- Produces: `DP-032` D1~D4 — M1 계획(프로비저닝·마이그레이터)이 링크.

- [ ] **Step 1: DP-032 작성**

Status `ACCEPTED_FOR_POC`. 결정 내용:
- **D1** P1은 **공유 PostgreSQL 서버의 전용 database `cosmai`** 를 소유 (스키마 분할 아님). 내부는 schema `cosmai` 하나, `public` 비움. 오너 제공 공유 DB 운영 규정(저장소 밖 문서)의 구속 지점을 DP 본문에 **요약 수록**: 역할 3분리(`cosmai_owner` NOLOGIN / `cosmai_migrator` / `cosmai_runtime`), runtime 타임아웃(`statement_timeout`·`lock_timeout`·`idle_in_transaction_session_timeout`), startup DDL 금지, cross-service FK·shared table 금지, instant는 `timestamptz`.
- **D2** 커넥션 예산 **16** (API 4, 워커 4, 스케줄러 2, 마이그레이션 1, 여유 5), `CONNECTION LIMIT`로 고정. `service-db.json` manifest + 프로비저닝 SQL은 M1 산출물.
- **D3** DB 접근 스택은 **psycopg3 직접 + SQL 파일 마이그레이터** (P0 복사·개작). version table은 `cosmai` 스키마 안, 모든 DDL schema-qualified. Rejected alternative: SQLAlchemy Core (검증된 트랜잭션 경계 로직의 재검증 비용).
- **D4** DB 크리덴셜은 시크릿 파일의 `COSMA_DB_*` 키로 (공유 서버라 비밀번호 존재 — P0의 무비밀번호 로컬 소켓과 달라지는 점을 명시).
- Remaining uncertainty: 공유 서버의 실제 주소·프로비저닝 권한 절차는 M1 시작 시 오너에게 확인.

- [ ] **Step 2: 검증 후 커밋**

Run: `uv run pytest tests/environment -q`
```bash
git add docs/decisions/DP-032-p1-database-placement.md
git commit -m "Place P1 on the shared PostgreSQL server as its own database, with the operating rules it must keep"
```

---

### Task 7: DP-033 — 운영자 표면 확장

**Files:**
- Create: `docs/decisions/DP-033-p1-operator-surface.md`

**Interfaces:**
- Produces: `DP-033` D1~D5 — Task 12와 M5·M6 계획이 링크.

- [ ] **Step 1: DP-033 작성**

Status `ACCEPTED_FOR_POC`. Related Open Questions: OQ-005 (부분 답 — P1 화면 집합), OQ-008 (미해결 유지 명시). 결정 내용:
- **D1** 대시보드 화면 6종: 수집기 도메인 화면(도메인당 수집기 하나가 관리 단위 — plan.md 목표 6), 자료 브라우저, 다운로드, 정규화 관리, 잡 모니터링, 헬스·메트릭.
- **D2** **운영자 Raw payload 열람 허용** — P0의 열람 거부(`domain/store.py:632`의 근거 기록)를 뒤집는 결정. 경계 근거: loopback 운영자 경계 안, redaction 경로 유지. 이 결정이 덮지 않는 것: 외부 노출 시의 데이터 클래스 재판정.
- **D3** 다운로드: Raw는 JSONL 기본 + CSV 옵션(메타데이터 컬럼 + payload 문자열), 정규화 결과는 CSV 평탄화. 범위조건: source, 기간, `item_key` 접두사. 스트리밍.
- **D4** 대시보드 스택: **MUI + React Router + TanStack Query 채택** — project-state §Technology constraints의 등재 기본값 채택 (DP-006의 P0 거절과 반대 방향이며, 화면 수 증가가 채택 근거).
- **D5** 수집 정기화: `schedule` 테이블 + 스케줄러가 collect 잡 생성. 정규화는 수동 시작 유지 + 선택적 스케줄 (기수락 원칙 그대로).

- [ ] **Step 2: 검증 후 커밋**

Run: `uv run pytest tests/environment -q`
```bash
git add docs/decisions/DP-033-p1-operator-surface.md
git commit -m "Widen the operator surface: six screens, raw payloads readable, exports streamable, collection on a schedule"
```

---

### Task 8: DP-034 — 크리덴셜 입력 경로와 보안 처분

**Files:**
- Create: `docs/decisions/DP-034-p1-credential-entry.md`

**Interfaces:**
- Consumes: `SR-001`~`SR-005` (Task 2)
- Produces: `DP-034` D1~D3 — Task 10(재구축 계획 Phase 0.3 충족 표시)·Task 12가 링크.

- [ ] **Step 1: DP-034 작성**

Status `ACCEPTED_FOR_POC`. Related Open Questions: OQ-007 (부분 — 대시보드 쓰기 경로만; 워커 해소 범위는 미해결 유지 명시). 결정 내용:
- **D1** 대시보드 수집기 화면에서 크리덴셜 **값 입력 허용**. API가 `~/.config/cosmai/env`(저장소 밖, mode 600)에 `COSMA_SRC_<SOURCE_ID>_<PURPOSE>=값`으로 기록. **쓰기 전용**: 값 재표시·응답 에코·로그 금지, 화면에는 ref 이름과 설정 여부만.
- **D2** 이것은 기존 불변식("대시보드·API 프로세스는 값에 접촉하지 않는다")의 **좁은 완화**다: 완화 범위는 "입력 요청 1회의 쓰기 경로"뿐이고, 나머지 전부 유지 — 저장소 트리·DB·환경변수·Raw·로그·화면 반입 금지, 워커 경계 요청 수명 해소, 미해소 시 `CONFIGURATION_INVALID`, protected header 부착 체계(DP-018). 이 완화가 덮지 않는 것: 입력 순간 API 프로세스 메모리의 값 존재 — 기록한다.
- **D3** SEC-006·리다이렉트 방어·URL 강제 수위·삭제 의무는 `security-recommendations.md`(SR-001~005)로 이관 — **DP-023 waiver의 연장이 아니라 P1 범위의 명시적 결정**. 재구축 계획 Phase 0.3("waiver가 아닌 P1 범위 결정")을 이것으로 충족.
- Required changes: `docs/conventions/secret-setup.md`와 `p0-security.md`에 이 DP로의 전방 링크 한 줄씩 추가 (본문 역사 보존).

- [ ] **Step 2: 전방 링크 추가**

`docs/conventions/secret-setup.md`와 `docs/conventions/p0-security.md` 각각의 문서 상단 메타 블록 아래에 한 줄: "P1 scope amendment: dashboard write-only credential entry and the security disposition are decided in [DP-034](../decisions/DP-034-p1-credential-entry.md)."

- [ ] **Step 3: 검증 후 커밋**

Run: `grep -l "DP-034" docs/conventions/secret-setup.md docs/conventions/p0-security.md && uv run pytest tests/environment -q`
Expected: 두 파일 모두 출력, 테스트 PASS.
```bash
git add docs/decisions/DP-034-p1-credential-entry.md docs/conventions/secret-setup.md docs/conventions/p0-security.md
git commit -m "Let the dashboard write a credential once, and say exactly which invariant that bends"
```

---

### Task 9: 로드맵 후보 등록부

**Files:**
- Create: `docs/roadmap-candidates.md`

**Interfaces:**
- Produces: 항목 id `RC-001`~`RC-007` — Task 10·12가 링크. M7에서 GitHub issue로 전환 검토.

- [ ] **Step 1: 등록부 작성**

서문: 필수 구현이 아닌 기능 후보의 등록부. `docs/service-register.md`와 역할 구분 명시(서비스 후보가 아니라 기능 후보). GitHub issue 전환은 M7 정합성 점검에서 일괄 수행. 항목:
- `RC-001` 카드·트렌드 화면 (능력 지도 5.3, DP-026 D1의 P1 첫 마일스톤 이동분)
- `RC-002` 선크림·토너 기회 카드 (6.1 — plan.md: 기능 후보로 등록)
- `RC-003` 결정적 트렌드 분류 (6.3)
- `RC-004` 성분 완전성 판단 (6.4)
- `RC-005` 새 record_type 설계: trend-radar rank/review 계열, youtube video 계열 (DP-030 D4)
- `RC-006` tubedepth 잡 생성 트리거 (수집이 읽기 전용을 넘어 수집 요청까지)
- `RC-007` 대시보드 인증 (loopback 밖 노출 전제조건)

- [ ] **Step 2: 검증 후 커밋**

Run: `grep -c "RC-00" docs/roadmap-candidates.md` — Expected: 14 이상.
```bash
git add docs/roadmap-candidates.md
git commit -m "Register the feature candidates P1 defers, so deferral stays a record and not a leak"
```

---

### Task 10: P1 재구축 계획 갱신

**Files:**
- Modify: `docs/architecture-synthesis/P1-RECONSTRUCTION-PLAN.md`
- Modify: `docs/decisions/DP-026-p0-closure-scope-and-collector-topology.md` (전방 링크 1줄)

**Interfaces:**
- Consumes: DP-029~034, SR·RC 등록부
- Produces: 게이트가 수락할 갱신판 재구축 계획 — Task 12가 링크.

- [ ] **Step 1: 재구축 계획 갱신**

2026-08-19판(113줄)을 다음과 같이 갱신 (역사 문장은 보존, 갱신 문단은 날짜 명기로 덧붙임):
- 헤더에 갱신 기록: "Updated 2026-08-21 from the owner's selection criteria (spec: `docs/superpowers/specs/2026-08-21-p1-reconstruction-design.md`) and DP-029..DP-034."
- **Phase 0 상태 표기**: 0.1 OQ-014 → DP-012·DP-026으로 닫힘 / 0.2 OQ-013 clause C → **명시적으로 열린 채 P1이 지참** (contract 1.3 문언 그대로 재구축, 반증 시 재개) / 0.3 SEC-006 → DP-034 D3로 충족 / 0.4 계약 문서 → 완료 기존 기록 유지.
- **Phase 1~4를 스펙 §9의 M1~M7 표로 대체**하는 절 추가: M1 `platform_core`+DB 기반, M2 `domain`(DP-029 수정 3건 포함), M3 애드온 3층+conformance suite, M4 애드온 5종(워크트리 병렬), M5 대시보드, M6 스케줄러·다운로드, M7 통합 시연·정합성 점검·main 병합·v0.1.0. 기존 Phase 구조와의 대응을 한 줄씩 명시 (Phase 1→M1·M2, Phase 2→M3·M4, Phase 3→M5·M6, Phase 4는 어댑터 실소스 검증으로 M4에 흡수).
- 2026-08-20 산출물 반영: `P1-INHERITED-DEFECTS.md`를 계획이 명시 인용 — **§1(불량 행 중단)은 DP-030 D2로, §5(스냅샷 정체성)는 DP-029 D2·D3로 P1 요구사항화**, 나머지 항목은 해당 마일스톤에서 재현 금지 목록으로 참조.
- "What P1 must not reproduce" 6항목은 그대로 유지하고 M별 적대적 리뷰 대상(outbound 가드, 스냅샷 봉인, 시크릿 경로)을 명시.

- [ ] **Step 2: DP-026 전방 링크**

DP-026의 D2 절 아래 한 줄: "Narrowed 2026-08-21 by [DP-031](DP-031-p1-collector-topology.md): adapters bind heavy periodic collection; lightweight sources may collect in-process."

- [ ] **Step 3: 검증 후 커밋**

Run: `grep -n "DP-031" docs/decisions/DP-026-p0-closure-scope-and-collector-topology.md && grep -c "M[1-7]" docs/architecture-synthesis/P1-RECONSTRUCTION-PLAN.md && uv run pytest tests/environment -q`
```bash
git add docs/architecture-synthesis/P1-RECONSTRUCTION-PLAN.md docs/decisions/DP-026-p0-closure-scope-and-collector-topology.md
git commit -m "Bring the reconstruction plan up to the owner's criteria, and say what each old phase became"
```

---

### Task 11: project-state 갱신 (게이트 전)

**Files:**
- Modify: `docs/project-state.md`

**Interfaces:**
- Consumes: DP-029~034, OQ-004 해결
- Produces: 게이트가 검토할 현재 상태 문서.

- [ ] **Step 1: §4 결정 목록에 DP-029~034 6줄 추가**

각 줄은 기존 관례대로 `[결정]` 라벨 + 한 문장 요약 + 링크. DP-029 줄에는 가설 4(스냅샷) 관련 §5 문단과의 연결을, DP-030 줄에는 가설 5·6과의 연결을 한 구절로 명시.

- [ ] **Step 2: §6 OQ 표 갱신**

OQ-004 행: `OPEN` → `RESOLVED`, Question 열 유지, Blocks 열을 "Resolved for P1 by DP-029; measurements preserved as rationale"로.

- [ ] **Step 3: §1 상태 문단에 게이트 진행 기록 추가**

"Two acts remain" 문단 아래 덧붙임: "2026-08-21: the gate record is being prepared on `p1/entry-gate` from the owner's recorded selection criteria; acceptance remains the owner's act."

- [ ] **Step 4: 검증 후 커밋**

Run: `grep -c "DP-03" docs/project-state.md` — Expected: 6 이상. `uv run pytest tests/environment -q` PASS.
```bash
git add docs/project-state.md
git commit -m "Carry DP-029 through DP-034 into the standing record before the gate reads it"
```

---

### Task 12: 게이트 기록 작성

**Files:**
- Create: `docs/architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md` (템플릿 `P1-ENTRY-GATE-TEMPLATE.md` 복사에서 시작)

**Interfaces:**
- Consumes: 앞선 전 태스크의 산출물
- Produces: Status `DRAFT`의 완성된 게이트 기록 — Task 13이 공격, Task 14가 수락.

- [ ] **Step 1: 메타 블록 기입**

Status `DRAFT`, Reviewed P0 revision = `git rev-parse HEAD` 값, Review date = 2026-08-21 (KST), Reviewers = "project owner (acceptance); Claude (preparation); adversarial-reviewer (attack, Task 13에서 링크 추가)".

- [ ] **Step 2: Required outputs 표 7행 기입**

각 행에 증거 링크와 **Blocking limitation을 정직하게** 기입:
- Charter exit-criteria review: 12개 기준을 각각 PASS/제한과 함께 나열한 부속 절을 본문에 추가. 근거는 architecture-synthesis Part 6 표 + DP-027(데이터셋: 경로 실증·제품 증거 0행 명시) + B4-SCENARIO-COVERAGE(명명된 갭).
- Architecture Synthesis / PoC Contract 0.1 / Disposition Register / P1 reconstruction plan: 4건 모두 "ACCEPTED (this gate, 2026-08-21)" — 이 게이트의 수락이 곧 그 문서들의 수락임을 명시.
- Promoted acceptance and fixture inventory: 계약의 acceptance 시나리오 목록(JOB/OPS/SEC)과 DP-022 생성 픽스처 원칙을 링크.
- Open Question and blocker inventory: OPEN으로 남는 OQ (001·003 일부·005·006·007·008·010·013·015)와 각각을 P1이 지참하는 방식 한 줄씩.
- [ ] **Step 3: P0 isolation checks 5항목 기입**

각 체크에 근거 한 줄: 의존성 없음(계약 기준+복사·개작, import 금지 — 스펙 §3.7), 모든 P1 행동의 계약/OQ 링크(갱신된 재구축 계획), archive-only 처분(P0-ARTIFACT-DISPOSITION), 보존·삭제 책임(disposition register의 Operator 지정 + SR-003), 태그 준비 완료(태그명 `p0-archive` 제안, Task 14에서 생성).

- [ ] **Step 4: Decision 블록은 Outcome 빈칸으로 두고 커밋**

오너 수락 전이므로 Outcome은 기입하지 않는다 — `DRAFT`가 그 상태다.
```bash
git add docs/architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md
git commit -m "Draft the P1 Entry Gate record with its evidence named and its outcome left to the owner"
```

---

### Task 13: 적대적 리뷰

**Files:**
- Create: `docs/agent-workflow/reviews/REVIEW-GATE-M0.md` (adversarial-reviewer가 작성 — 리뷰어는 읽기+Bash만 가능하므로 보고서 파일은 오케스트레이터가 받아 적음)
- Modify: Task 2~12 산출물 중 지적된 파일

**Interfaces:**
- Consumes: 게이트 기록과 DP 전체
- Produces: `PASS`/`FAIL` 공격 보고서 — 게이트 기록이 링크.

- [ ] **Step 1: adversarial-reviewer 서브에이전트 파견**

과제 문안: "docs/architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md와 DP-029~DP-034를 반증하라. 특히: (1) 게이트 표의 각 증거 링크가 실재하고 주장을 실제로 지지하는가, (2) DP가 주장하는 통제마다 '덮지 않는 범위'가 기록되어 있는가, (3) charter 12개 종료 기준 중 게이트 부속 절이 과대 주장한 항목이 있는가, (4) OQ 목록에서 누락된 OPEN 항목이 있는가, (5) project-state와 DP 사이의 모순. 재현 가능한 근거와 함께 PASS/FAIL/BLOCKED로 보고하라. 수리는 하지 말 것."

- [ ] **Step 2: 보고서를 `docs/agent-workflow/reviews/REVIEW-GATE-M0.md`로 기록**

보고서 형식은 기존 `docs/agent-workflow/reviews/` 문서 관례를 따름. FAIL 발견은 항목별로 수리 커밋 후 재공격 (수리는 이 세션이, 공격은 새 서브에이전트가 — 독립성 유지).

- [ ] **Step 3: 게이트 기록에 리뷰 링크 추가 후 커밋**

Reviewers 줄에 보고서 상대경로 링크 추가.
```bash
git add docs/agent-workflow/reviews/REVIEW-GATE-M0.md docs/architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md
git commit -m "Attack the gate record before the owner reads it, and keep what the attack found"
```

---

### Task 14: 오너 수락과 마감

**Files:**
- Modify: `docs/architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md` (Decision 블록)
- Modify: `docs/project-state.md` (Phase 전환)

**Interfaces:**
- Consumes: 공격을 통과한 게이트 기록
- Produces: 수락된 게이트, dev 병합, `p0-archive` 태그 — M1 계획의 진입 조건.

- [ ] **Step 1: 오너에게 게이트 제시**

채팅으로 요약 제시: 7행 상태, isolation 체크 5항, 공격 보고서 결과, 지참 OQ 목록, 제안 Outcome(`GO`), 제안 태그명(`p0-archive`). **명시적 수락을 기다린다 — 수락 없이 진행 금지.**

- [ ] **Step 2: 수락 반영**

Outcome `GO`, `[결정]` 줄에 수락자·일시 기입, Status를 `GO`로. project-state: Phase를 `P1 — Clean Reconstruction`으로, §1 "Two acts remain" 문단에 완료 덧붙임 기록, Next gate를 "P1 charter (미작성)"으로.

```bash
git add docs/architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md docs/project-state.md
git commit -m "Record the owner's GO: P0 closes against its charter and P1 opens"
```

- [ ] **Step 3: dev 병합 (--no-ff)**

```bash
git switch dev
git merge --no-ff p1/entry-gate -m "Merge branch 'p1/entry-gate' into dev — P1 Entry Gate accepted GO"
```

- [ ] **Step 4: 아카이브 태그 생성**

오너가 Step 1에서 태그명을 승인한 경우에만:
```bash
git tag -a p0-archive -m "P0 archive: charter-closed, gate GO 2026-08-21. P0 code is reference only."
```

- [ ] **Step 5: 최종 검증**

Run: `uv run pytest tests/environment -q && git log --oneline -3 && git tag`
Expected: 테스트 PASS, 병합 커밋 존재, `p0-archive` 태그 존재. push는 오너 요청 시에만.

---

## Self-review 기록

- 스펙 커버리지: 스펙 §9 M0 행의 4개 항목(DP 작성, 재구축 계획 갱신, 게이트 개최·수락, 아카이브 태그)이 Task 2~14에 모두 대응. §3의 결정 12건 → DP-029(1·2·3·4번), DP-030(스펙 §2.3), DP-031(9번+§2.1), DP-032(5·11번), DP-033(12번+§7), DP-034(6번), 7·8·10번은 게이트 기록과 재구축 계획 갱신에 반영.
- 플레이스홀더 없음: 각 문서 태스크에 실제 결정 문안과 근거 인용처를 명시함.
- 일관성: DP 번호(029~034), SR·RC id, 게이트 파일명, 태그명 `p0-archive`가 태스크 간 동일함을 확인.
