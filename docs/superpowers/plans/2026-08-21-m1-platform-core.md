# M1 — platform_core 재구축과 공유 DB 프로비저닝 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `apps/platform_core`를 CONTRACT-JOB-0.1 기준으로 재구축(P0 복사·개작)하고, 공유 Docker PostgreSQL에 cosmai 전용 database를 프로비저닝하여 JOB-001~008 시나리오가 새 트리에서 통과하는 상태를 만든다.

**Architecture:** 두 갈래 — (a) DB 프로비저닝: `tubedepth-postgres` 컨테이너(PG 18.6, 127.0.0.1:5433)에 `cosmai`·`cosmai_test` database와 3역할을 DP-032대로 생성; (b) 코드: P0 `platform_core`(23파일, ~4.6k LOC)를 `apps/platform_core`로 복사·개작 — 유닉스 소켓 전용이던 접속을 시크릿 파일 기반 비밀번호의 루프백 TCP로 바꾸는 것이 핵심 편차. 게이트가 M1으로 지참시킨 OQ-006 측정 2건을 재측정으로 마감한다.

**Tech Stack:** Python 3.13, psycopg 3 직접(DP-032 D3), FastAPI+uvicorn, 손수 SQL 마이그레이터, uv, pytest(-xdist), mypy --strict, ruff.

**Spec:** `docs/superpowers/specs/2026-08-21-p1-reconstruction-design.md` §4 + `docs/decisions/DP-032-p1-database-placement.md` + `contracts/experimental/CONTRACT-JOB-0.1.md` + `docs/architecture-synthesis/P1-RECONSTRUCTION-PLAN.md` M1 행. 충돌 시 이 순서의 역순이 우선(계약 > DP > 스펙).

## Global Constraints

- 브랜치 `p1/m1-platform-core` (dev에서 분기), 완료 시 `--no-ff` 병합. push 금지(요청 시에만).
- 커밋: 서술형 문장 + `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` 트레일러.
- **P0 트리(`experiments/`)는 읽기 전용.** 복사·개작 허용, `import` 금지 — P1 코드에 `experiments` 문자열이 import로 등장하면 결함.
- 새 코드는 `apps/` 아래에만. `apps/`는 자체 uv 프로젝트(자체 `.venv`)로, 루트 P0 프로젝트와 패키지로 연결되지 않는다.
- 시크릿 불변식 유지: 비밀번호 값은 저장소·환경변수·로그·출력·이 계획의 산출 문서 어디에도 등장하지 않는다. 생성은 `openssl rand -hex 24` → 즉시 `~/.config/cosmai/env`(mode 600)로. **터미널에 echo 금지.**
- 관리자 DB 접근은 `docker exec -i tubedepth-postgres psql -U fleet ...` 경유(컨테이너 내부 trust, 비밀번호 불요). 샌드박스가 docker 소켓/루프백을 막으면 해당 명령만 샌드박스 해제로 실행.
- 앱/테스트의 DB 접속은 127.0.0.1:5433 TCP — 샌드박스 루프백 차단에 걸리므로 테스트 실행 명령은 샌드박스 해제 필요할 수 있음.
- `[결정]` 초기 타임아웃 기본값: `statement_timeout 30s`, `lock_timeout 5s`, `idle_in_transaction_session_timeout 15s` — 운영 규정의 예시값을 초기값으로 채택, SLO 확정 전까지의 기본. 커넥션 예산 16 = runtime 12(API 4·워커 4·스케줄러 예약 2·여유 2) + migrator 2 + 예비 2.
- 기존 가드 `.venv/bin/python -m pytest tests/environment -q`(저장소 루트, 81개)는 매 태스크 후에도 green이어야 한다. P1 코드 품질 게이트는 `apps/` 안에서 `uv run mypy --strict .` + `uv run ruff check .` + `uv run python -m pytest`.
- 통제를 주장하면 덮지 않는 범위를 같이 기록한다. 계약과 다른 동작은 침묵하지 않고 T11의 편차 기록에 올린다.

---

### Task 1: 브랜치와 apps 스캐폴드

**Files:**
- Create: `apps/pyproject.toml`, `apps/README.md`, `apps/.gitignore`

**Interfaces:**
- Produces: `apps/` uv 프로젝트 — 이후 모든 태스크가 `cd apps && uv run ...`으로 실행.

- [ ] **Step 1: 브랜치 생성**

```bash
git switch -c p1/m1-platform-core dev
```

- [ ] **Step 2: `apps/pyproject.toml` 작성** — 루트 P0 `pyproject.toml`의 구조를 참고하되 새로 작성:

```toml
[project]
name = "cosmai-apps"
version = "0.0.0"
requires-python = ">=3.13"
dependencies = [
    "psycopg[binary]>=3.2",
    "fastapi>=0.115",
    "uvicorn>=0.34",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-xdist>=3.6",
    "mypy>=1.14",
    "ruff>=0.9",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.mypy]
strict = true

[tool.ruff]
line-length = 100
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

- [ ] **Step 3: `apps/README.md`** — 3~5문장: 이 트리는 P1 재구축이며 P0(`experiments/`)를 import하지 않는다는 규칙, 게이트 기록(`../docs/architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md`)과 재구축 계획 링크. `apps/.gitignore`: `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`.

- [ ] **Step 4: 검증** — `cd apps && uv sync && uv run python -c "print('apps ok')"` 성공, 루트 가드 81 passed.

- [ ] **Step 5: 커밋** — `git add apps/ && git commit -m "Open apps/ with its own project: the P1 tree imports nothing from P0"`

---

### Task 2: DB 프로비저닝 (manifest + SQL + 실행)

**Files:**
- Create: `apps/db/service-db.json`, `apps/db/provision.sql`, `apps/db/provision.md`

**Interfaces:**
- Produces: 서버(127.0.0.1:5433)에 `cosmai`·`cosmai_test` database, 역할 `cosmai_owner`(NOLOGIN)/`cosmai_migrator`/`cosmai_runtime`; `~/.config/cosmai/env`에 `COSMA_DB_MIGRATOR`·`COSMA_DB_RUNTIME` 키. Task 3+의 접속 전제.

- [ ] **Step 1: `apps/db/service-db.json`** — tubedepth의 `service-db.json` 패턴을 따라:

```json
{
  "manifest_version": 1,
  "service": "cosmai",
  "database": "cosmai",
  "schema": "cosmai",
  "server": "docker container tubedepth-postgres, 127.0.0.1:5433, PostgreSQL 18.6",
  "roles": {"owner": "cosmai_owner", "migrator": "cosmai_migrator", "runtime": "cosmai_runtime"},
  "cross_service_dependencies": [],
  "required_extensions": [],
  "external_object_stores": [],
  "connection_budget": {
    "total": 16,
    "runtime_connection_limit": 12,
    "runtime_breakdown": {"api": 4, "worker": 4, "scheduler_reserved": 2, "slack": 2},
    "migrator_connection_limit": 2,
    "reserve": 2
  },
  "session_defaults": {"statement_timeout": "30s", "lock_timeout": "5s", "idle_in_transaction_session_timeout": "15s"}
}
```

- [ ] **Step 2: `apps/db/provision.sql`** — 두 부분으로 작성. 부 A(클러스터 수준, psql 변수로 비밀번호 주입, 파일에 값 없음):

```sql
\set ON_ERROR_STOP on
CREATE ROLE cosmai_owner NOLOGIN;
CREATE ROLE cosmai_migrator LOGIN NOINHERIT CONNECTION LIMIT 2 PASSWORD :'mig_pw';
CREATE ROLE cosmai_runtime  LOGIN NOINHERIT CONNECTION LIMIT 12 PASSWORD :'run_pw';
GRANT cosmai_owner TO cosmai_migrator;
CREATE DATABASE cosmai OWNER cosmai_owner;
CREATE DATABASE cosmai_test OWNER cosmai_owner;
```

부 B(database 수준 — `cosmai`와 `cosmai_test` 각각에 접속해 실행; `:dbname` 주석으로 안내):

```sql
\set ON_ERROR_STOP on
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SET ROLE cosmai_owner;
CREATE SCHEMA cosmai;
RESET ROLE;
REVOKE ALL ON SCHEMA cosmai FROM PUBLIC;
GRANT USAGE ON SCHEMA cosmai TO cosmai_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE cosmai_owner IN SCHEMA cosmai
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cosmai_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE cosmai_owner IN SCHEMA cosmai
  GRANT USAGE, SELECT ON SEQUENCES TO cosmai_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE cosmai_owner IN SCHEMA cosmai
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
```

이어서 클러스터 수준으로 돌아가(부 C, 부 A 파일 말미에 포함) 역할별 세션 기본값 — 두 database 모두에:

```sql
ALTER ROLE cosmai_runtime IN DATABASE cosmai SET search_path = cosmai, pg_catalog;
ALTER ROLE cosmai_migrator IN DATABASE cosmai SET search_path = pg_catalog;
ALTER ROLE cosmai_runtime IN DATABASE cosmai SET statement_timeout = '30s';
ALTER ROLE cosmai_runtime IN DATABASE cosmai SET lock_timeout = '5s';
ALTER ROLE cosmai_runtime IN DATABASE cosmai SET idle_in_transaction_session_timeout = '15s';
-- cosmai_test에 동일 5줄 반복
```

- [ ] **Step 3: 실행** — `apps/db/provision.md`에 실행 절차를 기록하며 수행:

```bash
MIG_PW=$(openssl rand -hex 24); RUN_PW=$(openssl rand -hex 24)
docker exec -i tubedepth-postgres psql -U fleet -d postgres \
  -v mig_pw="$MIG_PW" -v run_pw="$RUN_PW" < apps/db/provision.sql        # 부 A+C
docker exec -i tubedepth-postgres psql -U fleet -d cosmai      < apps/db/provision_db.sql  # 부 B
docker exec -i tubedepth-postgres psql -U fleet -d cosmai_test < apps/db/provision_db.sql
printf 'COSMA_DB_MIGRATOR=%s\nCOSMA_DB_RUNTIME=%s\n' "$MIG_PW" "$RUN_PW" >> ~/.config/cosmai/env
unset MIG_PW RUN_PW
```

(부 B를 별도 파일 `provision_db.sql`로 분리해도 됨 — 위 명령이 기준.) 비밀번호는 어떤 단계에서도 stdout에 출력하지 않는다.

- [ ] **Step 4: 부정 검증** — runtime으로 DDL이 거부되는지:

```bash
docker exec tubedepth-postgres psql -U fleet -d cosmai -c "SET ROLE cosmai_runtime; CREATE TABLE cosmai.must_fail(id int);"
```
Expected: `ERROR: permission denied for schema cosmai`. 또한 `SELECT rolname, rolconnlimit FROM pg_roles WHERE rolname LIKE 'cosmai%';` 가 12/2/-1(owner)을 보여야 함.

- [ ] **Step 5: 호스트 경로 검증** — 실제 P1 접속 경로(TCP+비밀번호)로:

```bash
cd apps && uv run python - <<'EOF'
import psycopg, pathlib
env = dict(l.split("=",1) for l in pathlib.Path.home().joinpath(".config/cosmai/env").read_text().splitlines() if "=" in l)
with psycopg.connect(host="127.0.0.1", port=5433, dbname="cosmai", user="cosmai_runtime", password=env["COSMA_DB_RUNTIME"]) as c:
    print(c.execute("show search_path").fetchone(), c.execute("show statement_timeout").fetchone())
EOF
```
Expected: `('cosmai, pg_catalog',) ('30s',)`. (샌드박스 루프백 차단 시 해제하여 실행.)

- [ ] **Step 6: 커밋** — `git add apps/db && git commit -m "Provision cosmai's own database on the shared server, with the roles and limits DP-032 fixed"`

---

### Task 3: 시크릿 리더와 config 복사·개작

**Files:**
- Create: `apps/platform_core/__init__.py`, `apps/platform_core/secrets.py`, `apps/platform_core/config.py`
- Test: `apps/tests/test_config.py`, `apps/tests/test_secrets.py`

**Interfaces:**
- Produces: `load_config() -> Config`(frozen dataclass; 필드는 P0 config.py의 것 + `db_host: str`, `db_port: int`, `db_name: str`, `db_user: str`, `db_password_ref: str`), `resolve_credential(ref: str) -> SecretValue`. Task 4+가 소비.

- [ ] **Step 1: 원본 읽기** — `experiments/integrated-p0/platform_core/config.py`와 `experiments/integrated-p0/domain/secrets.py` 전체를 읽는다. 각 파일 상단의 근거 주석 포함.

- [ ] **Step 2: `secrets.py` 복사·개작** — P0 `domain/secrets.py`에서: 경로 검증(존재·저장소 밖·mode 600/400), 라인 스캔 `resolve_credential(ref)`, `SecretValue`(`repr`/`str` = `SecretValue(<withheld>)`), 캐시 없음. 개작: ref 패턴 검사를 `^COSMA_(SRC|DB)_[A-Z0-9_]+$`로 — DP-032 D4의 제2 키 패밀리 반영(P0는 `COSMA_SRC_`만).

- [ ] **Step 3: `config.py` 복사·개작** — P0 config.py에서. 변경: `COSMA_DB_HOST`(기본 없음→필수)가 유닉스 소켓 디렉터리였던 것을 **TCP 호스트**로, `COSMA_DB_PORT` 추가, `COSMA_DB_PASSWORD_REF` 추가(기본 `COSMA_DB_RUNTIME`; 값이 아니라 ref). 나머지(리스·재시도·폴·API 루프백 강제·exit 78) 유지. 루프백 강제와 시크릿 저장소 트리-내 거부 가드 유지.

- [ ] **Step 4: 실패하는 테스트 → 통과** — P0 `tests/test_config.py`에서 관련 케이스 복사·개작(필수 env 누락 시 refuse, 비루프백 API host refuse, ref 패턴 위반 refuse, mode 644 시크릿 파일 refuse). `cd apps && uv run python -m pytest tests/test_config.py tests/test_secrets.py -q` PASS, mypy·ruff clean.

- [ ] **Step 5: 커밋** — `"Carry config and the secret reader into apps, with COSMA_DB_* as a second credential family"`

---

### Task 4: 연결과 마이그레이터

**Files:**
- Create: `apps/platform_core/db/__init__.py`, `apps/platform_core/db/connection.py`, `apps/platform_core/db/migrate.py`, `apps/platform_core/db/migrations/0001_platform_core.sql`
- Test: `apps/tests/test_migrate.py`

**Interfaces:**
- Produces: `connect(config, *, role="runtime") -> psycopg.Connection`, `apply_migrations(conn, dir) -> list[str]`(적용 버전 반환; version table `cosmai.schema_migrations`). Task 5+가 소비.

- [ ] **Step 1: 원본 읽기** — P0 `db/connection.py`, `db/migrate.py`, `db/migrations/0001_platform_core.sql`(143줄), 그리고 `tests/conftest.py`의 DB 픽스처 부분.

- [ ] **Step 2: `connection.py` 개작** — 유닉스 소켓 → TCP: `psycopg.connect(host=cfg.db_host, port=cfg.db_port, dbname=cfg.db_name, user=..., password=resolve_credential(cfg.db_password_ref).reveal())`. 비밀번호는 connect 호출 인자로만 존재(변수 보관 최소화). migrator 접속은 같은 함수의 `role="migrator"` 분기(user=`cosmai_migrator`, ref=`COSMA_DB_MIGRATOR`) + 접속 직후 `SET ROLE cosmai_owner`.

- [ ] **Step 3: `migrate.py` 개작** — P0 손수 마이그레이터 유지하되: version table을 `cosmai.schema_migrations`로 스키마 한정, 부트스트랩 DDL도 한정, autocommit 검사 유지, 적용은 migrator 접속(owner로 SET ROLE된 세션)에서만.

- [ ] **Step 4: `0001_platform_core.sql` 개작** — P0 DDL 복사 후: 모든 `CREATE TABLE`/인덱스를 `cosmai.` 한정, 시각 컬럼 전부 `timestamptz` 확인(P0가 이미 그렇다면 무변경 확인만 기록), CHECK 제약(상태기계·리스·attempt 예산·terminal_reason) 원문 유지.

- [ ] **Step 5: 테스트** — `apps/tests/conftest.py`: P0 conftest의 DB 픽스처를 개작 — `cosmai_test` database에 migrator로 접속, 테스트 세션 시작 시 `DROP SCHEMA cosmai CASCADE; CREATE SCHEMA cosmai;`(owner 권한) 후 마이그레이션 적용, 테스트는 runtime 접속 사용. `test_migrate.py`: 빈 스키마에서 적용 성공·재적용 no-op·버전 기록 확인. 실행(샌드박스 해제 필요 시 해제): PASS.

- [ ] **Step 6: 커밋** — `"Connect over loopback TCP and migrate schema-qualified, the shared-server way"`

---

### Task 5: obs 계층 (logging·correlation·metrics·redaction)

**Files:**
- Create: `apps/platform_core/obs/{__init__,logging,correlation,metrics,redaction}.py`
- Test: `apps/tests/test_obs.py`

**Interfaces:**
- Produces: P0와 동일 시그니처의 구조적 JSON 로거, `correlation_id` 전파, 카운터, `redact_mapping`/`is_redacted_key`. Task 6~8이 소비.

- [ ] **Step 1: 원본 4파일 읽고 복사** — 개작 포인트는 import 경로뿐이어야 정상. redaction의 키 집합·containment·대소문자 불문 규칙 원문 유지(계약 §Provenance).
- [ ] **Step 2: 테스트** — P0 테스트에서 redaction·logging 케이스 복사·개작, PASS. mypy·ruff clean.
- [ ] **Step 3: 커밋** — `"Carry the observation layer: same JSON lines, same redaction contract"`

---

### Task 6: jobs 코어 (state·store·registry·runner) + errors

**Files:**
- Create: `apps/platform_core/errors.py`, `apps/platform_core/jobs/{__init__,state,store,registry,runner}.py`
- Test: `apps/tests/test_jobs_store.py`, `apps/tests/test_jobs_runner.py`

**Interfaces:**
- Produces: 계약 I1~I5를 지는 클레임/리스/펜싱/완료 트랜잭션 — `JobStore.claim/complete/heartbeat`, `HandlerRegistry`, `run_once(...)`. Task 7·8이 소비.

- [ ] **Step 1: 원본 5파일 + 계약 §Semantics(I1~I5, 상태 전이, 펜싱 규칙)를 나란히 읽기.** 복사·개작 시 SQL은 `cosmai.` 한정으로. 단일 클레임 문·부분 인덱스 활용·완료 시 리스 소유 재확인(펜싱)·`platform_effect` idempotency — 전부 P0 원문 로직 유지.
- [ ] **Step 2: 오류 분류(`errors.py`)** — 5클래스와 psycopg 예외 매핑(08/53/57 → PLATFORM_TRANSIENT) 복사. `[확인 사실]` 계약이 transient 분기 미실행(P0-A)을 기록함 — 여기서도 실행 주장 금지, T11 편차 기록에 유지.
- [ ] **Step 3: 테스트** — P0의 store/runner 단위 테스트 복사·개작(클레임 경합, 리스 만료 회수, 만료 워커의 늦은 완료 거부+카운트, 재시도 백오프, terminal 상태). PASS.
- [ ] **Step 4: 커밋** — `"Rebuild the job core: one claim statement, a fenced completion, an effect key"`

---

### Task 7: worker와 synthetic 핸들러

**Files:**
- Create: `apps/platform_core/worker.py`, `apps/platform_core/handlers/{__init__,synthetic}.py`
- Test: `apps/tests/test_worker.py`

**Interfaces:**
- Produces: `python -m platform_core.worker`(apps에서) 실행 가능한 폴링 워커; synthetic 핸들러(성공/실패/지연/중단) — JOB 시나리오의 대상. Task 9가 소비.

- [ ] **Step 1: 원본 `worker.py`·`handlers/synthetic.py` 복사·개작** (import 경로, config). 안전 종료(시그널 → 진행 중 attempt 마무리) 로직 유지.
- [ ] **Step 2: 테스트** — 워커 1사이클 실행이 PENDING→SUCCEEDED를 만드는 것, 종료 시그널 처리. PASS.
- [ ] **Step 3: 커밋** — `"A worker that polls, claims, completes, and dies cleanly"`

---

### Task 8: API 수명주기

**Files:**
- Create: `apps/platform_core/api/{__init__,app,__main__}.py`
- Test: `apps/tests/test_api.py`

**Interfaces:**
- Produces: 루프백 강제 바인딩의 FastAPI 앱 — 잡 목록/상세/재시도, health, metrics 라우트(P0와 동일 표면). M5 대시보드가 이후 소비.

- [ ] **Step 1: 원본 `api/app.py`(수동 소켓 바인딩, uvicorn 로깅 비활성, JSON 로그) 복사·개작.**
- [ ] **Step 2: 테스트** — P0 `test_api.py`에서 라우트·비루프백 거부·protected debug 필드 redaction 케이스 복사·개작. PASS.
- [ ] **Step 3: 커밋** — `"The platform API returns: loopback-bound, log-quiet, redacted"`

---

### Task 9: 수락 시나리오 JOB-001~008 재현

**Files:**
- Create: `apps/tests/acceptance/test_job_scenarios.py` (+ 필요시 분할)

**Interfaces:**
- Consumes: Task 4~8 전부.
- Produces: 계약의 8개 시나리오가 새 트리에서 실행되는 증거 — T11 기록과 게이트 계보의 연결점.

- [ ] **Step 1: 원본 대조** — `tests/acceptance/`의 JOB-001~008 시나리오 문서와 P0의 대응 테스트(`experiments/integrated-p0/tests/` 안 — grep으로 `JOB-00`을 찾아 파일 확정)를 읽는다.
- [ ] **Step 2: 복사·개작** — 시나리오 id당 최소 1테스트, docstring에 시나리오 id와 계약 절 명기. 중단·중복 전달·만료 리스 주입 로직 원문 유지.
- [ ] **Step 3: 실행** — `cd apps && uv run python -m pytest tests/ -q` 전체 PASS(샌드박스 해제 필요 시 해제). mypy --strict·ruff clean.
- [ ] **Step 4: 커밋** — `"JOB-001 through 008 run again, against the tree that will live"`

---

### Task 10: OQ-006 지참 측정 2건 재측정

**Files:**
- Create: `apps/tests/concurrency/test_job_007_parallel.py`, 측정 스크립트 `apps/tests/concurrency/run_measurements.sh`
- Modify: `docs/open-questions/OQ-006-job-concurrency.md` (측정 결과 덧붙임)

**Interfaces:**
- Consumes: Task 6·7.
- Produces: 게이트가 M1에 배정한 두 측정의 결과 기록 — T11이 인용.

- [ ] **Step 1: JOB-007 재현** — 200잡×4프로세스 시나리오를 새 트리에서 10회 실행, 실패 수 기록(P0: 정상 0/30, CPU 경합 시 1·3·1).
- [ ] **Step 2: F16 재측정** — 상관관계 테스트(P0의 `test_job_002_shares_one_correlation_id_across_both_attempts` 대응 P1 테스트)를 `-n 4`로 20회 반복, 플레이크 여부 기록.
- [ ] **Step 3: OQ-006에 덧붙임** — 날짜 명기, 측정 환경(WSL2·PG 18.6·TCP), 결과, 그리고 결과가 무엇을 말하지 않는지(스케일 밖, 단일 머신). 재발 시 재현 명령 포함.
- [ ] **Step 4: 커밋** — `"Re-measure what the gate carried: JOB-007 at 200x4 and the F16 flake, on the new tree"`

---

### Task 11: M1 기록과 편차 대장

**Files:**
- Create: `docs/p1/M1-RECORD.md`
- Modify: `docs/architecture-synthesis/P1-RECONSTRUCTION-PLAN.md` (M1 행에 완료 링크), `docs/decisions/DP-032-p1-database-placement.md` (Remaining uncertainty 해소 덧붙임)

**Interfaces:**
- Consumes: 전 태스크.
- Produces: M1의 증거·편차 기록 — M2 계획과 적대적 리뷰가 인용.

- [ ] **Step 1: `docs/p1/M1-RECORD.md`** — 필수 절: (a) 프로비저닝 증거(서버 식별: docker `tubedepth-postgres`·PG 18.6·127.0.0.1:5433, 역할·리밋 조회 결과, 부정 테스트 출력 — 비밀번호 없는 출력만); (b) 시나리오 결과표(JOB-001~008 + Task 10 측정); (c) **계약 편차 대장**: ① CONTRACT-JOB-0.1 §Provenance "유닉스 소켓 전용, TCP 리스너 없음"은 P0-A 환경 서술 — P1은 DP-032에 따라 루프백 TCP; DB 리스너는 컨테이너의 것이고 API 루프백 강제는 유지, 이 편차가 덮지 않는 것(비루프백 노출 시 별도 결정 필요)을 명기. ② transient 오류 분기는 여전히 미실행(P0-A와 동일) — 실행 주장 금지. ③ 그 외 개작 중 발견된 모든 계약 불일치. (d) search_path 전략 선택 기록(역할 수준 기본값 + migrator 명시 한정 — 전용 database라 외부 스키마 위험이 구조적으로 낮다는 근거).
- [ ] **Step 2: DP-032 덧붙임** — Remaining uncertainty에 날짜 명기로: 서버 확정(위 식별 정보), 프로비저닝 실행 완료, 증거는 M1-RECORD 링크. 본문 삭제 없음.
- [ ] **Step 3: 재구축 계획 M1 행에** `— done 2026-08-XX, [M1-RECORD](../p1/M1-RECORD.md)` 덧붙임.
- [ ] **Step 4: 루트 가드 + apps 전체 게이트 재실행 후 커밋** — `"Record M1: what was built, what was measured, and where it deviates from the contract's P0-A wording"`

---

### Task 12: 적대적 리뷰와 병합

**Files:**
- Create: `docs/agent-workflow/reviews/REVIEW-M1.md`
- Modify: 발견 수리 대상 파일들

- [ ] **Step 1: adversarial-reviewer 파견** — 과제: "M1 브랜치(dev..HEAD)를 반증하라. 특히 (1) 펜싱·클레임·완료 트랜잭션이 P0 원문과 의미 동등한지 diff 수준에서, (2) 프로비저닝 부정 테스트가 실제로 거부를 증명하는지 재실행으로, (3) M1-RECORD의 모든 주장·명령·수치가 재현되는지, (4) 시크릿 값이 어떤 커밋·문서·로그에도 없는지, (5) apps가 experiments를 import하지 않는지. 수리 금지, PASS/FAIL/BLOCKED 보고."
- [ ] **Step 2: FAIL 발견은 수리 서브에이전트로 수리 후 범위 한정 재검증** (M0 방식 그대로, 최대 5라운드). 보고서를 `REVIEW-M1.md`로 기록·커밋.
- [ ] **Step 3: 오너에게 M1 완료 요약 제시 후** (측정 결과와 편차 대장 포함) **승인 시** `git switch dev && git merge --no-ff p1/m1-platform-core`. push는 요청 시에만.

---

## Self-review 기록

- 스펙 커버리지: 재구축 계획 M1 행(platform_core+DB 기반, DP-032) → T1~T9; 게이트가 M1에 배정한 OQ-006 2건 → T10; DP-032 Remaining uncertainty 해소 → T11; 계약 편차(TCP) → T11(c); 적대적 리뷰 관행 → T12.
- 플레이스홀더 없음: 신규 산출물(provision.sql, pyproject, manifest)은 전문 수록; 복사·개작 태스크는 원본 경로와 개작 항목을 열거함 — 원본이 곧 명세.
- 타입 일관성: `load_config`/`resolve_credential`/`connect`/`apply_migrations` 시그니처가 T3→T4→T6에서 동일하게 인용됨. 예산 산술 12+2+2=16 확인. `cosmai_test`가 T2에서 생성되고 T4 conftest가 소비.
