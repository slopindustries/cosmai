# Service register

- 문서 지위: 활성 프로젝트 기록. **결정이 아니라 후보 목록이다.**
- 최종 수정일: 2026-08-19

## 이 문서가 로드맵이 아닌 이유

`[확인 사실]` [DP-011](decisions/DP-011-p0b-product-and-delivery-scope.md)은 P0의 잠정 소비자,
출력 단위, 증거 경계와 두 제품 범위를 결정했다. 장기 예측 목표와 서비스 경계는 여전히
결정하지 않았다.

`[추론]` 따라서 결정론적 P0 기준선과 장기 ML/예측 서비스는 같은 항목이 아니다. 전자는
DP-011의 수락 범위이고, 후자는 학습 표적과 평가자료가 정해지기 전까지 후보로 남는다.

이 문서는 대신 각 후보에 대해 **무엇을 먹고, 무엇을 내고, 어떤 add-on kind이며, 무엇이 막고
있는지**를 적는다. 내용은 로드맵과 거의 같지만, 하나는 결정을 조용히 내리고 하나는 내리지 않는다.

후보가 실제로 채택되면 Decision Packet을 통해야 하며, 그때 이 표의 지위가 `[가설]`에서
`[결정]`으로 바뀐다. DP-011이 채택한 항목은 아래에 별도로 표시한다.

## 후보

### 1. 수집기 어댑터 — 독립 REST 서비스

- 지위: **P0 수락됨**. [DP-012](decisions/DP-012-independent-scraper-services.md)의 애드온
  kind `collector`.
- 입력: 독립 스크래퍼 서비스가 자체 저장 후 제공하는 버전된 export endpoint. 플랫폼이
  등록된 service profile로 요청을 조립한다.
- 출력: `raw_envelope` + `raw_item`, 그리고 COSMAI cursor 전진.
- 경계: 스크래퍼 코드·스케줄·1차 저장소는 외부 서비스가 소유한다. 어댑터는 서비스 DB를
  읽거나 스크래퍼 모듈을 import하지 않는다.
- 복구: 분산 트랜잭션 대신 재생 가능한 `batch_id + record_id`를 사용한다. COSMAI 쪽 Raw,
  cursor, job completion만 하나의 트랜잭션이다.
- 막는 것: 서비스별 export schema, 실행 가능한 commit, 원 소스 사용 근거와
  [OQ-001](open-questions/OQ-001-source-capability.md)의 선택.

### 2. 데이터셋 임포터

- 지위: **예정** (B3). 애드온 kind `importer`.
- 입력: 등록된 로컬 입력. 네트워크 없음.
- 출력: 수집기와 동일.
- 막는 것: [OQ-001](open-questions/OQ-001-source-capability.md)의 데이터셋 선택.

### 3. 구조 정규화기

- 지위: **존재함** — `addons/normalizer.conformance`. 애드온 kind `normalizer`.
- 입력: 봉인·해시 검증된 snapshot.
- 출력: 버전이 붙은 정규화 결과.
- 규칙: **구조적인 것만** — trim, 키 소문자화, 빈 값 제거, 정렬. 필드의 *의미*를 해석하지 않는다.
- 막는 것: 없음. 의미를 해석하지 않기 때문이다.

### 4. `rule-baseline@0.1`

- 지위: **P0 계획됨**. DP-011이 수락한 결정론적 기준선이며 애드온 kind `normalizer`.
- 3번과의 차이: **필드가 무엇을 뜻하는지 해석한다.**
- 막는 것: OQ-002는 해결됐다. 실제 source sample, Schema 0.x, snapshot 경계가 필요하다.
- 계약 변경: 없을 것으로 보인다. `NormalizeContext`가 이미 필요한 것을 준다.

### 5. 트렌드 분석기

- 지위: **P0의 결정론적 결과는 수락됨**, 장기 분석 서비스와 예측모델은 `[가설]` 후보.
- 입력: **정규화된 결과.** Raw도 snapshot도 아니다.
- 출력: P0에서는 DP-011의 근거 추적형 R&D 기회 카드. 장기 서비스 출력은 미정.
- **P0 구현 경계:** 저장된 정규화 결과를 읽는 폐기형 실험 evaluator로 먼저 측정한다. 새 add-on
  kind나 platform dependency를 먼저 만들지 않는다.
- **장기 계약 후보:** `[추론]` 현재 어떤 context도 정규화 결과를 읽지 못한다.
  `NormalizeContext`는 snapshot을 읽고 결과를 낸다. 결과를 *소비하는* 것은 새 capability
  (`read_results` 같은 것)이고, [DP-008](decisions/DP-008-addon-architecture.md) D3의 규칙상
  능력 추가는 계약 **minor 상승**이다. 새 `kind`가 필요할 수도 있다.
- 막는 것: P0 기준선은 실제 source sample과 Schema 0.x. ML/예측 서비스는 별도의 학습 표적,
  시간 누수 없는 평가셋과 수락 기준.
- `[추론]` 이 후보는 애드온 아키텍처의 좋은 시험이기도 하다. 플랫폼 코드를 늘리지 않고
  새 서비스를 더할 수 있다는 주장이 여기서 실제로 검증된다.

### 6. 근거 해석기

- 지위: **선택적 stretch**. 필수 경로가 통과한 뒤에만 시작한다.
- 입력: 완성된 기회 카드와 그 카드가 지목한 `evidence_id` 자료.
- 출력: 근거 ID를 문장별로 붙인 한국어 설명, 또는 `REVIEW_REQUIRED`.
- 제한: trend class와 canonical entity를 만들거나 바꾸지 않는다. 벡터 DB는 필수가 아니다.
- 막는 것: 결정론적 카드 경로의 수락. LLM 없이도 전체 데모가 동작해야 한다.

## 후보를 추가할 때

각 항목에 다음을 적는다. 하나라도 답할 수 없으면 그것이 곧 이 후보를 막는 것이다.

- 무엇을 입력으로 먹는가 (Raw / snapshot / 정규화 결과 / 그 외)
- 무엇을 출력하는가
- 어떤 애드온 kind인가, 아니면 새 kind가 필요한가
- 어떤 계약 변경이 필요한가, 그것이 minor인가 major인가
- 어떤 Open Question이 막고 있는가
