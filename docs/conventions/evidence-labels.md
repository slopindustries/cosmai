# Evidence Labels

- 문서 지위: 활성 프로젝트 convention
- 적용 범위: 조사, 실험, Open Question, Decision Packet, Architecture Synthesis, 운영 보고
- 최종 수정일: 2026-08-16

## 목적

CosmaSignal은 실제 source, 실험 결과, 해석, 미검증 주장, 프로젝트 선택을 함께 다룬다. 이들을 구분하지 않으면 한 에이전트의 추측이 다음 에이전트에게 확정된 사실로 전달되거나, 프로젝트의 선택이 기술적으로 증명된 결론처럼 보일 수 있다.

Evidence label은 문장의 신뢰도 점수가 아니라 **문장이 프로젝트에서 수행하는 역할을 나타내는 type**이다.

```text
[확인 사실] + [측정] → Evidence
[추론]               → Interpretation
[가설]               → Testable uncertainty
[결정]               → Chosen action
```

신뢰도가 높은 `[가설]`이나 잘못 수행된 `[측정]`도 있을 수 있다. Label만으로 품질을 보장하지 않으며, 출처와 방법을 함께 기록해야 한다.

## 다섯 가지 정의

### `[확인 사실]`

신뢰할 수 있는 출처나 직접 확인한 artifact로 독립적으로 검증할 수 있는 상태다.

필요한 근거:

- authoritative document, source page, API specification 또는 license
- repository file과 필요한 경우 line 위치
- 직접 확인한 database schema, payload field 또는 current system state
- 확인 시점이 결과에 영향을 준다면 날짜와 시간

예시:

```text
[확인 사실] 공급자 API 문서에는 cursor pagination을 사용한다고 명시되어 있다.
[확인 사실] 수집한 sample payload에는 `updated_at` field가 존재하지 않는다.
```

주의할 점:

- 출처가 주장한 내용과 실제 동작을 같은 것으로 취급하지 않는다.
- 외부 dataset 설명에 “정제 완료”라고 적혀 있다는 사실은 확인할 수 있지만, 실제 결측치가 없다는 의미는 아니다.
- 현재 시점에만 참인 정보에는 확인 날짜를 기록한다.

### `[측정]`

명시된 입력, 환경, 절차, 도구를 통해 이번 작업에서 얻은 관찰값이다.

필요한 metadata:

- 측정 시각
- input과 sample 크기 또는 fixture identity
- 실행 환경과 관련 version
- 사용한 절차 또는 재현 가능한 command
- 단위, 집계 방식과 오차 또는 한계

예시:

```text
[측정] 2026-08-16에 1,000개 sample row를 검사한 결과 `published_at` 결측률은 18.4%였다.
[측정] 동일 fixture를 세 번 처리했을 때 normalized output hash가 세 번 모두 같았다.
```

주의할 점:

- 한 sample에서 얻은 값이 전체 모집단에도 적용된다고 자동으로 일반화하지 않는다.
- 실행 결과가 수치가 아니어도, 정해진 절차에서 관찰한 behavior라면 측정으로 기록할 수 있다.
- 측정 결과의 원인을 설명하는 문장은 별도의 `[추론]`이다.

### `[추론]`

확인 사실이나 측정으로부터 도출했지만 원자료에 직접 적혀 있지는 않은 해석이다.

필요한 근거:

- 추론을 지지하는 `[확인 사실]` 또는 `[측정]`
- 결론까지 이어지는 reasoning
- 다른 설명이 가능하다면 alternative와 불확실성

예시:

```text
[추론] 두 수집에서 원천 ID가 유지되었으므로 P0의 duplicate key 후보로 사용할 수 있을 가능성이 높다.
[추론] 현재 부하 측정에서는 PostgreSQL job table이 P0 처리량에 충분해 보인다.
```

주의할 점:

- “가능성이 높다”, “충분해 보인다”는 표현을 제거해 사실처럼 만들지 않는다.
- 하나의 추론 안에 새로운 미검증 전제가 들어가면 그 전제를 `[가설]`로 분리한다.
- source가 직접 주장한 내용을 단순히 요약하는 것은 추론이 아니라 `[확인 사실]`이다.

### `[가설]`

아직 충분히 검증되지 않았으며 반증 조건과 실험이 필요한 주장이다.

필요한 정보:

- 왜 검증할 가치가 있는지
- falsification condition
- minimum experiment
- 관찰할 evidence와 exit condition

예시:

```text
[가설] 하나의 작은 Raw envelope로 첫 REST source와 dataset import를 정보 손실 없이 표현할 수 있다.
[가설] worker를 두 개로 늘리면 duplicate side effect 없이 처리량이 증가할 것이다.
```

주의할 점:

- 단순히 모르는 항목을 모두 가설이라고 부르지 않는다. 질문만 있는 경우 Open Question으로 기록한다.
- 반증할 수 없는 희망이나 목표는 가설이 아니다.
- 구현 편의를 위해 임시로 선택한 default는 `[결정]`이며, 그 선택의 타당성은 별도 `[가설]`일 수 있다.

### `[결정]`

증명된 사실이 아니라 특정 범위와 시점에서 채택하기로 한 선택이다.

필요한 정보:

- decision scope와 status
- 결정 날짜와 owner
- 근거가 된 evidence
- rejected alternative와 tradeoff
- 재검토 조건 또는 reversibility
- consequential decision이라면 Decision Packet 링크

예시:

```text
[결정] P0 primary database로 PostgreSQL을 사용한다.
[결정] OQ-001의 REST probe 후보로 Provider A를 선택한다. 이 선택은 P0 범위에만 적용한다.
```

주의할 점:

- `[결정]`은 해당 기술이 객관적으로 가장 우수하다는 뜻이 아니다.
- 결정으로 선택된 architecture hypothesis가 자동으로 검증된 사실이 되지는 않는다.
- 범위나 상태를 적지 않으면 P0 선택이 production invariant로 오해될 수 있다.

## `[확인 사실]`과 `[측정]`의 경계

가장 자주 혼동되는 두 label이다.

다음 기준을 사용한다.

- 이미 존재하는 source 또는 artifact의 직접 확인 가능한 속성을 보고하는 경우: `[확인 사실]`
- 정해진 procedure를 실행해 값, 분포 또는 behavior를 얻은 경우: `[측정]`

예시:

```text
[확인 사실] sample file에는 1,000개의 row가 저장되어 있다.
[측정] validation procedure를 실행한 결과 1,000개 중 37개 row가 schema validation에 실패했다.
```

직접 확인한 사실도 확인 방식이 복잡하거나 결과가 procedure에 의존한다면 `[측정]`으로 분류한다.

## 판정 순서

Label이 확실하지 않으면 다음 순서로 판단한다.

1. 프로젝트가 특정 선택을 채택했다는 문장인가? → `[결정]`
2. 아직 검증되지 않았고 반증 가능한 주장인가? → `[가설]`
3. 다른 evidence에서 의미를 도출한 문장인가? → `[추론]`
4. 명시된 procedure를 실행해 얻은 값이나 behavior인가? → `[측정]`
5. source나 artifact에서 직접 독립 검증할 수 있는 상태인가? → `[확인 사실]`

어느 항목에도 맞지 않으면 label을 억지로 붙이지 말고 문장을 질문, 요구사항, 목표 또는 설명으로 다시 분류한다.

## 하나의 문장에 역할을 섞지 않는다

다음 문장은 피한다.

```text
[확인 사실] API는 cursor pagination을 사용하므로 대규모 수집에도 충분하다.
```

앞부분은 사실이지만 뒷부분은 추론이다. 다음처럼 분리한다.

```text
[확인 사실] API 문서는 cursor pagination을 사용한다고 명시한다.
[추론] cursor가 안정적으로 유지된다면 offset 방식보다 반복 수집 중 누락 위험이 낮을 가능성이 있다.
[가설] 해당 cursor는 수집 도중 source update가 발생해도 안정적으로 다음 page를 가리킨다.
```

## 프로젝트 예시: REST source 평가

```text
[확인 사실] Provider A는 인증 없이 JSON API를 제공하며 공식 문서에 분당 60회 제한을 명시한다.

[측정] 동일 IP에서 61번째 요청을 보냈을 때 HTTP 429 응답이 발생했다. 측정 시각과 request sequence는 probe log에 기록했다.

[추론] P0 collector에는 source별 rate limiter와 429 retry policy가 필요하다.

[가설] `Retry-After`를 준수하면 추가 차단 없이 1,000개 record를 완료할 수 있다.

[결정] Provider A를 OQ-001 REST probe의 `CONDITIONAL GO` 후보로 유지한다.
```

## 프로젝트 예시: PostgreSQL job queue

```text
[확인 사실] P0 primary database는 PostgreSQL로 결정되어 있다.

[가설] `FOR UPDATE SKIP LOCKED`, lease와 idempotent write로 두 worker의 at-least-once 처리를 감당할 수 있다.

[측정] worker 두 개로 duplicate delivery와 process interruption을 주입한 결과 uncontrolled duplicate effect는 발생하지 않았다.

[추론] 관찰한 P0 부하와 failure scenario 범위에서는 별도 message broker가 필요하지 않다.

[결정] PoC Contract 0.1 후보에 PostgreSQL-backed job model을 포함한다.
```

## 권장 기록 형식

Label은 주장 바로 앞에 붙이고 근거는 가능한 한 가까이 둔다.

```text
[측정] invalid row 비율은 3.7%였다.

- fixture: `fixture-id`
- procedure: `command or test ID`
- environment: `relevant versions`
- captured_at: `timestamp`
- limitation: `known sampling or tooling limit`
```

여러 문장으로 reasoning을 설명해야 한다면 각 문장에 label을 반복할 필요는 없다. 한 bullet 또는 paragraph가 한 역할만 갖도록 작성한다.

## 검토 checklist

문서를 완료하기 전에 확인한다.

- `[확인 사실]`에 출처 또는 직접 확인 가능한 artifact가 있는가?
- `[측정]`에 input, procedure, environment, 시각과 단위가 있는가?
- `[추론]`이 어떤 evidence에서 나왔는지 추적할 수 있는가?
- `[가설]`에 falsification condition과 minimum experiment가 있는가?
- `[결정]`에 scope, status, 근거와 재검토 조건이 있는가?
- 하나의 문장에 사실과 해석을 섞지 않았는가?
- label이 신뢰도나 중요도 표시처럼 사용되지 않았는가?
