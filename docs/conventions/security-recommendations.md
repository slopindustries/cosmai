# Security Recommendations Register

- 문서 지위: 활성 프로젝트 registry — **선택적 후속 구현 후보의 등록부**
- 적용 범위: P1 재구축 이후 보안 통제 후보
- 최종 수정일: 2026-08-21

## 이 문서가 하는 일과 하지 않는 일

`[결정]` 이 문서는 **선택적 후속 구현 후보의 등록부**다. 어떤 항목이 여기에 있다는 것은
"P1이 이 통제 없이 동작한다"는, 이미 수락된 결정을 뜻한다. 항목이 여기 실려 있다는 사실
자체가 향후 구현을 약속하지 않으며, 반대로 그 통제가 필요 없다고 주장하지도 않는다 — 둘
다 아니고, 셋째: 채택 여부를 미루기로 한 결정이 기록되어 있다는 것뿐이다.

`[결정]` 통제를 주장하는 곳마다 그 통제가 덮지 않는 범위를 함께 기록한다
(`docs/conventions/project-memory.md` 참조). 이 문서에서 그 역할을 하는 것이 아래 표의
**"부재가 의미하는 것"** 열이다. 항목마다 이 열을 채우는 이유는 과대 주장을 막기 위해서다
— "이 통제가 없다"는 문장만으로는 독자가 위험의 범위를 가늠할 수 없고, 정확히 무엇이
커버되지 않는지를 적어야 그 공백이 어디까지인지 알 수 있다.

`[확인 사실]` 각 항목의 출처는 owner의 재구축 선택기준(`plan.md`)이며, 항목 번호는 그
문서의 절 번호("능력 지도" 절)를 그대로 따른다. `plan.md`의 원문을 옮기기 전에 해당
절을 열어 문구를 확인했다.

## 등록부

| id | 항목 | 출처 | 부재가 의미하는 것 |
|---|---|---|---|
| `SR-001` | 미승인 URL 강제 차단 수위 | 능력 지도 §1.4, [plan.md](../../plan.md) §1.4 | outbound 프로파일의 **구조**(엔드포인트 명명, credential 부착에 필요한 골격)는 P1 계약에 그대로 남는다. 이 항목이 이관하는 것은 그 구조가 아니라 강제 **수위** — 전체 주소 범위 검사, `loopback` 플래그 등 P0가 쌓았던 강화 수준을 P1이 처음부터 같은 정도로 재구현할지 여부다. |
| `SR-002` | DNS 실패·재바인딩 대응 | 능력 지도 §1.5, [plan.md](../../plan.md) §1.5 | P0에서도 검증된 적이 없다(`NOT EXERCISED`). 이 항목의 부재는 P0에서 P1로 넘어가며 새로 생긴 공백이 아니라, 한 번도 닫힌 적 없는 공백이 계속 열려 있다는 뜻이다 — 아래 상세 참조. |
| `SR-003` | 삭제 의무 이행 경로 | 능력 지도 §2.6, [plan.md](../../plan.md) §2.6, DP-029 D4 | `raw_item` 행을 삭제해도 `snapshot_item`과 `raw_envelope`에 사본이 각각 하나씩, 도합 두 벌 남는다. 이 항목이 부재하는 동안에는 "삭제했다"는 문장이 성립하지 않는다 — 아래 상세 참조. |
| `SR-004` | 리다이렉트·주소 범위 방어 재구현 | 능력 지도 §7.2, [plan.md](../../plan.md) §7.2 | 등록된 source profile에서만 host·port·path를 구성하고 HTTPS만 허용하는 outbound guard의 최소선은 P1 계약과 보안 baseline에 그대로 남는다. 이 항목이 이관하는 것은 P0가 다섯 차례의 반증·수리를 거쳐 쌓은 강화 수준 전체(모든 redirect의 전면 재검증, 모든 주소 범위의 전면 차단)를 P1이 처음부터 같은 강도로 재구현하는 일이며, 이것이 게이트 통과의 필수조건이 아니라는 결정이다. 승인된 개별 어댑터(DP-031 D3)가 필요로 하는 좁은 예외는 이 항목이 아니라 DP-031이 직접 정한다. |
| `SR-005` | SEC-006 | 능력 지도 §7.3, [plan.md](../../plan.md) §7.3, DP-023 | 이 항목이 여기 있다는 것은 [DP-023](../decisions/DP-023-sec-006-waived-for-p0.md)의 P0 waiver가 P1로 **승계**된다는 뜻이 **아니다**. DP-023의 waiver는 "P1 Entry Gate must not accept a plan that carries this forward"라고 스스로 못박았고 게이트에서 만료된다. SEC-006이 이 등록부에 있다는 사실은 DP-034가 P1 범위를 새로 결정한 것이며, 그 결정은 waiver의 연장이 아니라 독립된 판단이다. |

## 항목별 상세

### `SR-001` — 미승인 URL 강제 차단 수위

`[확인 사실]` P0의 outbound guard(`domain/outbound.py`)는 host·port·path를 등록된 source
profile에서만 구성하고 주소 범위 검사로 loopback·private·link-local·multicast·reserved·
unspecified 대역을 전부 차단한다([DP-026](../decisions/DP-026-p0-closure-scope-and-collector-topology.md)
증거). `[확인 사실]` 같은 함수가 모든 redirect를 재검증한다는 것은 독립 보안 리뷰가 확인했다
([DP-023](../decisions/DP-023-sec-006-waived-for-p0.md)). `SR-001`이 이관하는 것은 이 구조
전체가 아니라 그 **강제 수위**뿐이다 — 구조는 계약에 남는다.

### `SR-002` — DNS 실패·재바인딩 대응

`[확인 사실]`
[`B4-SCENARIO-COVERAGE.md`](../../experiments/integrated-p0/evidence/B4-SCENARIO-COVERAGE.md)의
DNS 행은 `NOT EXERCISED as a failure`로 기록되어 있다: 주소 *범위*는 검사되고 테스트되지만
DNS 자체는 아니다 — 이름이 resolve에 실패하는 경우, 서로 다른 정당성을 가진 여러 주소로
resolve되는 경우, 검사 시점과 connect 시점의 resolve 결과가 달라지는 경우 중 어느 것도 테스트가
없다. transport가 한 번 resolve해 검사한 주소로만 connect한다는 사실이 재바인딩 창을 구조적으로
닫아 두긴 하지만, 그것을 보여주는 테스트는 없다. `SR-002`는 P1이 새로 포기하는 것이 아니라,
P0가 애초에 검증하지 않은 채 남겨둔 공백을 그대로 물려받아 등록한 것이다.

### `SR-003` — 삭제 의무 이행 경로

`[측정]` [TASK-005](../agent-workflow/task-packets/TASK-005-snapshot-evolution-that-discriminates.md)는
`raw_item`의 모든 행을 지우는 disposition purge를 재생 실험에 넣어 측정했다. purge 이후에도
sealed snapshot(`snapshot_item`)은 여전히 검증되고 바이트 그대로 재생되었다 — purge가
`raw_item`에는 도달하지만 `snapshot_item`에는 도달하지 않는다는 뜻이다. `raw_envelope`는
같은 실험에서 삭제 대상이 아니었고, `raw_item`이 참조하는 원본 payload를 별도 행으로 보유한
채 남는다(`experiments/integrated-p0/domain/migrations/0002_domain.sql:139-216`). 즉
`raw_item` 한 테이블만 지워서는 사본 두 벌 — `snapshot_item`과 `raw_envelope` — 이 그대로
남는다.

`[추론]` 따라서 `raw_item` 삭제를 삭제 의무의 이행으로 보고하면 과대 주장이 된다. 이 격차를
닫는 경로(`snapshot_item`·`raw_envelope`까지 함께 지우는 절차, 또는 봉인된 스냅샷과 삭제
의무가 애초에 어떻게 공존해야 하는지의 설계)는 P1에서 **미설계** 상태로 남으며, 그 처분이
[DP-029](../decisions/DP-029-p1-snapshot-identity.md) D4가 기록하는 결정이다.

### `SR-004` — 리다이렉트·주소 범위 방어 재구현

`[확인 사실]` DP-023은 P0의 outbound guard가 하루 사이 다섯 개의 결함(byte bound 오차,
deadline 밖 쓰기, dot-segment redirect 우회, page limit 부재, 빈 `path`의 redirect 범위
확대)을 거쳐 지금 형태에 이르렀다고 기록한다. `SR-004`는 이 강화 과정 전체를 P1이 처음부터
같은 강도로 다시 밟는 일을 가리키며, 승인된 개별 어댑터가 필요로 하는 좁은 예외(예: 특정
loopback 주소 허용)는 DP-031이 이 항목과 별도로 정한다.

### `SR-005` — SEC-006과 DP-023 waiver의 관계

`[확인 사실]` DP-023은 waiver를 "면제는 유지하되... P1 Entry Gate에 올라간다"고 스스로
기록했고, "Obligations this decision creates" 1항에서 "The P1 Entry Gate must not accept a
plan that carries this forward"라고 명시한다. 그러므로 이 게이트를 통과하는 문서 중 어느
것도 "DP-023의 waiver가 P1에도 적용된다"고 쓸 수 없다.

`[결정]` SEC-006을 이 등록부(`SR-005`)에 올리는 행위 자체가 새로운 결정이며,
[DP-034](../decisions/DP-034-p1-credential-entry.md)가 그 범위를 정한다. waiver는 여기서
연장되는 것이 아니라 종료되고, 그 자리를 새 결정이 대신한다.

## 항목을 추가할 때

각 항목에 다음을 적는다. 하나라도 답할 수 없으면 아직 이 등록부에 올릴 준비가 되지 않은
것이다.

- 어떤 능력 지도 절 또는 결정에서 나왔는가
- 이 항목이 없을 때 정확히 무엇이 커버되지 않는가 ("부재가 의미하는 것")
- 이 항목과 겹치거나 경계를 나누는 다른 결정이 있는가
- 채택될 경우 어떤 계약·코드 변경이 필요한가 (선택, 이 등록부 단계에서는 미필수)
