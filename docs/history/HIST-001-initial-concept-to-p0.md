# HIST-001 — 초기 데이터 파이프라인 구상에서 폐기형 P0 결정까지

- 문서 성격: 정제된 역사 기록, 비권위 자료
- 기록 범위: 최초 구상부터 M0 Project Bootstrap까지
- 작성일: 2026-08-16
- Raw 대화 원문 포함 여부: 포함하지 않음

## 이 기록을 남기는 이유

CosmaSignal의 현재 구조는 처음부터 한 번에 정해진 것이 아니다. 데이터 수집기와 정규화기라는 비교적 단순한 출발점에서 시작해 데이터 신뢰성, 실행 주체, 버전 관리, 재현성, 기술 스택, Dashboard, 개발 방법론을 차례로 검토하면서 범위가 구체화되었다.

이 문서는 그 과정에서 어떤 생각이 유지되고, 변경되고, 보류되었는지를 설명한다. 현재 구현 기준을 찾기 위한 문서는 아니며, 현재 기준은 [`Project State`](../project-state.md), [`Decision Packets`](../decisions/README.md), 향후 작성될 versioned contract에서 확인해야 한다.

## 1. 최초 구상: 수집과 정규화를 두 영역으로 나누다

`[역사적 맥락]`

최초 구상은 외부 데이터를 수집하는 영역과 수집된 데이터를 정규화하는 영역을 분리하는 것이었다.

수집 영역에는 다음 역할이 있었다.

- 외부 REST API에서 원천 Raw 데이터를 가져오는 stateless collector
- Raw 데이터를 저장하고 조회하는 database/API 계층
- collector의 실행 주기, 수집 범위, 병렬 처리를 조정하는 상위 collection service

정규화 영역에도 비슷한 역할 구분이 있었다.

- Raw 입력에 지정된 정규화를 수행하는 normalizer
- 정규화 결과를 저장하고 조회하는 database/API 계층
- 정규화 방식, 실행 범위, 병렬 처리를 조정하는 normalization service

그 위에는 두 흐름을 파이프라이닝하고 전체 주기와 상태를 관찰하는 관리 서비스가 필요하다고 보았다.

이 시점의 핵심 문제의식은 worker가 stateless하더라도 작업 범위와 실행 상태를 관리하는 상위 계층은 필요하다는 것이었다. 다만 component 이름과 물리적 service boundary는 아직 검증되지 않은 구상이었다.

## 2. Raw를 단순 중간 데이터가 아니라 독립적인 증거로 보다

`[현재 유지]`

논의가 진행되면서 collector는 단순히 source-specific JSON을 저장하는 역할로는 부족하다는 점이 분명해졌다. 서로 다른 source를 공통 시스템으로 다루려면 다음 두 층이 동시에 필요했다.

1. source, 수집 작업, 원천 식별자, 수집 시각, payload hash 같은 공통 envelope
2. 원천 의미를 손실하지 않는 source-specific payload

공통 schema를 최대한 크게 만들어 미래의 모든 source를 미리 표현하는 방향은 피하기로 했다. 지나치게 큰 generic schema는 아직 존재하지 않는 요구사항을 추측하게 만들기 때문이다. 공통 envelope는 안정적으로 유지하되 원본 payload를 함께 보존하는 방향이 선택되었다.

Raw는 다음 정규화 단계가 실패하거나 변경되어도 다시 사용할 수 있어야 하므로 논리적으로 append-only이며, provenance와 observation history를 보존하는 데이터로 보게 되었다.

현재 관련 결정과 가설은 [`Project State`](../project-state.md)에 정리되어 있다.

## 3. 저장소와 데이터베이스 선택

`[현재 유지]`

초기에는 Raw와 Normalized 저장소를 물리적으로 분리할 필요가 있는지, RDBMS와 NoSQL 중 무엇이 적절한지 검토했다.

초기 prototype에서는 운영 복잡도를 줄이기 위해 하나의 PostgreSQL 안에서 기능과 schema를 논리적으로 분리하는 방향이 적절하다고 판단했다. Raw payload에는 JSONB를 사용할 수 있고, job state, lineage, version, transaction, 관계 조회는 relational model의 장점을 활용할 수 있기 때문이다.

NoSQL이나 object storage가 잘못된 선택이라고 판단한 것은 아니다. 향후 payload 크기, 보존 비용, 처리량, 다중화 요구가 실제로 관찰되면 저장 backend를 다시 검토할 수 있도록 identity와 contract를 특정 저장 기술에 종속시키지 않는 것이 중요하다고 보았다.

PostgreSQL은 P0의 primary database로 확정되었지만, 미래의 전체 저장 topology까지 확정한 것은 아니다.

## 4. Spring과 Python을 비교하다

`[변경됨]`

초기에는 database와 backend control 영역에 Spring을 사용하는 방안이 강하게 검토되었다. Spring이 transaction, security, configuration, policy, secret, profile, observability, MSA 운영에 익숙한 선택이라는 점과 개인적인 선호가 이유였다.

이후 다음 항목을 기준으로 Spring과 Python을 비교했다.

- transaction과 저장 일관성
- worker 병렬 처리와 scale-out
- logs, metrics, tracing과 전체 관측성
- policy, profile, API key와 token 관리
- backend security
- MSA와 service boundary
- data processing, normalization, ML/LLM 생태계와의 호환성

검토 결과 Python이 transaction이나 병렬 처리에서 본질적으로 열등한 것은 아니며, 정확성은 언어보다 transaction boundary, idempotency, retry, lease, database constraint와 운영 설계에 좌우된다는 결론에 도달했다.

Spring Control Plane과 Python Worker를 함께 쓰는 polyglot 구조도 검토했지만, 현재 규모에서 두 stack을 동시에 운영할 이유가 충분히 증명되지 않았다. 최종적으로 P0 backend stack은 Python으로 결정되었다.

`[기각됨]` Spring 자체가 부적절하다는 결론은 아니다. 현재 P0에서 추가 운영 복잡도를 감수할 만큼의 우위가 확인되지 않았다는 의미다.

현재 결정은 [`DP-002`](../decisions/DP-002-project-identity-and-stack.md)에 기록되어 있다.

## 5. 수집과 정규화의 실행 생명주기를 완전히 분리하다

`[현재 유지]`

초기 구상에는 수집 이후 정규화가 하나의 연속 pipeline처럼 보이는 부분이 있었다. 이후 정규화는 수집 직후 자동으로 따라가는 단계가 아니라, 독립적으로 생성하고 실행하며 재실행할 수 있는 작업이어야 한다는 요구가 분명해졌다.

현재 유지되는 원칙은 다음과 같다.

- collection 성공은 normalization 성공에 의존하지 않는다.
- collection은 normalization을 암묵적으로 시작하지 않는다.
- normalization run은 외부 Dashboard에서 사용자가 명시적으로 생성한다.
- 필요하면 Dashboard에서 schedule을 설정할 수 있지만 수동 실행과 같은 contract를 사용한다.
- normalization 실패는 이미 저장된 Raw를 무효화하지 않는다.
- normalizer provider는 rule, ML model, LLM API 등 구현 방식과 독립적인 versioned interface를 가진다.

이 분리는 장애 복구, 정규화 버전 비교, 비용 제어, human review, 실험 반복을 독립적으로 수행하기 위한 것이다.

## 6. Dashboard가 단순한 화면에서 Control Plane으로 확장되다

`[현재 유지]`

Dashboard는 결과를 보여주는 부가 UI가 아니라 작업을 만들고 운영 상태를 확인하는 외부 Control Plane으로 정의되었다.

P0에서 Dashboard가 다루어야 할 범위에는 다음이 포함된다.

- source와 dataset import
- collection job과 normalization run 생성
- 필요 시 schedule 설정
- Raw와 normalized result 탐색
- job state와 retry
- logs, metrics, error와 debugging evidence
- version과 lineage 확인

초기 Dashboard의 목적은 시각적 완성도가 아니라 system behavior를 관찰하고 실패 원인을 찾는 것이다. mobile rendering은 responsive하게 고려하지만 native mobile product를 만드는 것은 현재 범위가 아니다.

Frontend는 React와 TypeScript를 사용하고 Backend contract는 versioned OpenAPI/schema를 통해 연결하는 방향으로 결정되었다. 구체적인 UI library와 framework 세부 조합은 P0 evidence에 따라 바뀔 수 있다.

## 7. Raw가 영원히 불변이라는 가정을 제거하다

`[현재 유지]`

Raw를 append-only로 설계하더라도 normalizer가 미래의 database migration, 다중화, 운영 실수, projection 변경까지 무조건 신뢰해서는 안 된다는 문제가 제기되었다.

이에 따라 normalization run이 처리할 정확한 입력을 materialize하고 봉인하는 sealed snapshot 경계가 추가되었다.

snapshot은 적어도 다음 정보를 보존하는 방향으로 논의되었다.

- 선택된 정확한 Raw observation 집합
- normalizer가 소비한 canonical input
- item과 manifest hash
- 선택 기준과 생성 시각
- 관련 schema와 normalizer version
- Raw에서 snapshot item, normalized result로 이어지는 lineage

`[보류]` snapshot을 PostgreSQL, filesystem artifact 또는 object storage 중 어디에 저장할지와 정확한 manifest 구조는 P0에서 검증해야 한다. 관련 질문은 [`OQ-004`](../open-questions/OQ-004-snapshot-boundary.md)에 있다.

## 8. 기존 dataset import를 정식 acquisition mode로 추가하다

`[현재 유지]`

REST API뿐 아니라 이미 만들어진 dataset도 Raw ingestion 대상으로 포함하기로 했다. Kaggle과 같은 외부 배포 dataset은 구조가 정리되어 있더라도 품질, 결측치, 중복, 생성 과정, 정규화 기준을 신뢰할 수 없으므로 Raw로 취급한다.

dataset import에서 중요하게 본 항목은 다음과 같다.

- 파일 전달과 import 경로
- format, encoding, row identity와 duplicate 처리
- 원본 파일과 import batch의 hash
- license와 redistribution 권리
- dataset version과 생성 시점
- 원천 producer와 distributor의 구분
- invalid row와 partial failure 처리

source를 하나의 enum으로 분류하는 방식은 충분하지 않다고 보았다. acquisition mode, temporal mode, data nature, content channel, usage scope, rights status 등을 서로 다른 facet으로 기록하는 방향이 제안되었다.

`[보류]` 최종 vocabulary는 실제 REST source와 dataset을 조사한 이후 확정해야 한다.

## 9. 정규화 구현보다 정규화 protocol을 먼저 다루다

`[현재 유지]`

정규화는 단순한 format 변환부터 dictionary/rule, record context extraction, canonical entity resolution, hybrid 판단과 human review까지 다양한 복잡도를 가질 수 있다.

그러나 구현이 복잡하다는 사실이 정규화 품질이 높다는 뜻은 아니다. 따라서 어떤 ML model이나 LLM을 사용할지보다 다음을 먼저 정의해야 한다고 판단했다.

- provider input과 output
- validation과 error behavior
- schema와 provider version
- provenance와 confidence
- human review 상태
- deterministic replay 가능 여부
- 정규화 단계 또는 capability를 어떻게 보고할지

D0–D4 형태의 선형적인 정규화 단계도 후보로 논의되었다.

```text
D0  구조·형식 정규화
D1  사전·규칙 기반 의미 정규화
D2  레코드 문맥 기반 의미 추출
D3  Canonical Entity Resolution
D4  Hybrid 판단과 Human Review
```

`[보류]` 이 단계 모델은 실제 데이터와 normalizer를 통해 검증하기 전까지 보편적인 품질 척도로 확정하지 않는다. method, depth, quality, review 상태가 서로 다른 축일 가능성도 유지한다.

P0에는 비교 기준이 되는 deterministic `rule-baseline@0.1` 하나를 포함한다. 관련 탐색은 [`OQ-003`](../open-questions/OQ-003-normalization-protocol.md)에 기록되어 있다.

## 10. 최종 제품 의미를 의도적으로 보류하다

`[보류]`

프로젝트가 단순히 “트렌드를 안다”는 표현만으로는 전체 데이터를 어떻게 바라봐야 할지 결정하기 어렵다는 문제가 확인되었다.

최종적으로 누구의 어떤 판단을 개선하는지, 어떤 evidence와 uncertainty를 제공해야 하는지, human review가 어디에 위치하는지가 정해져야 `Normalized Schema 1.0`과 최종 quality metric을 확정할 수 있다.

현재 단계에서는 Raw ingestion과 dataset import를 목적 중립적으로 설계하고, 실제 source sample을 확보해 provisional Schema 0.x를 실험한다. 최종 Product Decision Contract는 별도 Open Question으로 유지한다.

관련 질문은 [`OQ-002`](../open-questions/OQ-002-project-decision-contract.md)에 있다.

## 11. Monorepo와 contract 중심 결합을 선택하다

`[현재 유지]`

초기 prototype 단계에서는 Backend와 Dashboard를 하나의 monorepo에 두는 것이 변경을 함께 추적하고 end-to-end 실행을 빠르게 검증하는 데 적절하다고 판단했다.

Backend와 Frontend가 공유 implementation code에 의존하는 것이 아니라, repository 안의 versioned API와 schema contract를 통해 결합하는 방향을 선택했다.

현재 repository에는 다음 경계가 반영되어 있다.

- `contracts/`: versioned API와 schema
- `experiments/`: 폐기 가능한 source probe와 P0 구현
- `tests/`: P1로 승격 가능한 fixture와 acceptance scenario
- `docs/`: 현재 상태, Open Question, Decision Packet, Architecture Synthesis

## 12. 개발 방법론을 불확실성 중심으로 재구성하다

`[현재 유지]`

프로젝트의 주요 위험이 coding 난이도보다 source와 schema, 제품 의미, architecture boundary에 대한 불확실성에 있다는 점에서 다음 흐름을 적용하기로 했다.

```text
Explore → Decide → Specify → Execute → Observe/Evaluate → 필요 시 Reopen
```

이 과정에서 다음 원칙을 사용한다.

- 사실, 측정, 추론, 가설, 결정을 구분한다.
- 증거가 부족한 문제를 구현자가 암묵적으로 확정하지 않는다.
- consequential decision은 Open Question과 Decision Packet으로 관리한다.
- 최소 실험으로 가설을 공격한다.
- test failure를 implementation, specification, assumption, evaluation, goal failure로 분류한다.
- implementation agent는 local choice를 자율적으로 처리하지만 결정 경계를 바꾸지 않는다.

이 방법론은 전체 프로젝트를 한 번에 통과하는 Waterfall이 아니라 source, normalization, snapshot, operations 같은 vertical slice마다 반복되는 cycle로 사용한다.

## 13. 지속형 prototype에서 폐기형 통합 P0로 방향을 수정하다

`[변경됨]`

한때는 첫 통합 prototype을 실행 가능한 기준 구현으로 만들고, 이후 계속 관찰하면서 고도화하는 방향을 고려했다.

그러나 현재는 실제 source, schema, snapshot, job concurrency, dashboard operation이 아직 검증되지 않았다. 이 상태에서 첫 구현을 장기 기반으로 삼으면 우연한 구조가 architecture decision으로 굳을 위험이 있다고 판단했다.

최종적으로 다음 lifecycle이 선택되었다.

```text
Source와 normalization exploration
→ 폐기 예정 통합 prototype P0
→ Evidence와 Architecture Synthesis
→ PoC Contract 0.1
→ P1 clean reconstruction
→ 관측, debugging, hardening
```

P0는 장난감이 아니다. 실제 REST와 dataset, Raw 저장, 독립 job, snapshot, rule normalizer, Dashboard, logs, metrics, retry, failure injection을 포함하는 축소 통합 시스템이다.

다만 P0에서 P1로 자동 승격하는 것은 구현 코드가 아니라 다음 자산이다.

- 검증된 evidence
- Decision Packet
- versioned contract
- redistributable fixture
- acceptance scenario
- error taxonomy
- Architecture Synthesis

현재 결정은 [`DP-001`](../decisions/DP-001-p0-lifecycle.md)과 [`P0 Charter`](../p0-charter.md)에 기록되어 있다.

## 14. CosmaSignal이라는 이름과 M0 저장소가 만들어지다

`[현재 유지]`

초기에는 `COSMAI`라는 이름을 고려했지만 GitHub organization 이름을 사용할 수 없어 대안을 검토했다. 프로젝트의 문제를 나타내면서도 특정 AI 구현에 종속되지 않는 `CosmaSignal`을 선택했다.

이 이름은 cosmetics 영역의 signal을 수집하고 근거와 함께 해석한다는 방향을 나타낸다. GitHub organization은 `CosmaSignal`, local directory는 `cosma-signal`로 정했다.

M0에서는 실행 코드를 바로 만들지 않고 다음 기반을 먼저 작성했다.

- Project State와 decision state
- P0 Charter와 종료 조건
- source, product decision, normalization, snapshot, operations, concurrency Open Questions
- Decision Packet template
- experimental contract 경계
- P0와 P1의 코드 승격 금지 원칙
- fixture와 acceptance scenario 보존 원칙

현재 기술과 저장소 결정은 [`DP-002`](../decisions/DP-002-project-identity-and-stack.md)에 기록되어 있다.

## 현재 시점의 요약

### 현재 유지되는 방향

- Python backend, PostgreSQL, React와 TypeScript Dashboard
- Backend, Dashboard, contract, experiment, test를 포함하는 monorepo
- REST API와 기존 dataset import를 모두 지원
- 외부 dataset을 포함한 모든 source input을 신뢰하지 않는 Raw로 취급
- Raw provenance와 원본 payload 보존
- collection과 normalization 실행 생명주기의 분리
- sealed snapshot을 통한 normalizer input 고정
- versioned normalized result와 lineage
- Dashboard 기반 control과 observability
- deterministic rule normalizer를 포함하는 폐기 예정 통합 P0
- Architecture Synthesis 이후 P1 clean reconstruction

### 아직 architecture hypothesis인 것

- FastAPI와 세부 Python library 조합
- API/control, collector worker, normalizer worker의 정확한 process boundary
- PostgreSQL job table과 `FOR UPDATE SKIP LOCKED` 기반 queue
- snapshot manifest의 정확한 schema와 storage backend
- 두 source에 공통으로 적용할 Schema 0.x
- source taxonomy의 최종 vocabulary

### 아직 열려 있는 질문

- 실제로 사용할 REST API와 dump dataset, 그리고 이용 권리
- 최종 제품이 개선할 decision과 evidence 기준
- normalizer provider protocol과 provisional schema
- snapshot의 정확한 materialization boundary
- Dashboard operator contract
- parallel worker, retry, lease와 transaction boundary

### 현재 범위에서 보류하거나 선택하지 않은 것

- Spring과 Python을 동시에 운영하는 polyglot P0
- 첫 P0 코드를 그대로 지속 고도화하는 방식
- 세분화된 MSA와 Kafka, Kubernetes 같은 scale infrastructure
- production secret manager와 identity provider 제품 선택
- 특정 ML 또는 LLM normalizer
- 최종 `Normalized Schema 1.0`
- D0–D4를 보편적인 품질 점수로 확정하는 것

## 다음 역사 기록이 필요한 시점

다음 기록은 M1 Source Capability Exploration 또는 P0 Architecture Synthesis처럼 프로젝트의 판단 경계가 실제 증거로 바뀌는 시점에 추가하는 것이 적절하다.

단순 구현 진행 상황은 history에 반복해서 적지 않는다. 새로운 증거가 기존 가정을 바꾸거나, 중요한 대안이 채택·기각되거나, 프로젝트 lifecycle이 변경될 때만 별도 `HIST-XXX` 문서를 만든다.
