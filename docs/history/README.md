# 프로젝트 역사 기록

이 디렉터리는 CosmaSignal의 아이디어와 아키텍처가 어떤 논의를 거쳐 현재 상태에 도달했는지를 사람이 이해할 수 있도록 정리한 공간이다.

역사 기록의 목적은 과거의 모든 문장을 보존하는 것이 아니다. 다음과 같은 판단 맥락을 잃지 않는 것이 목적이다.

- 최초에 해결하려고 했던 문제가 무엇이었는가
- 어떤 대안이 검토되었는가
- 무엇이 확정되고 무엇이 다시 가설로 내려갔는가
- 왜 이전 방향을 변경했는가
- 현재 결정을 다시 검토해야 할 때 어떤 전제가 있었는가

## 이 문서의 지위

`docs/history/`의 문서는 **비권위 자료**다. 현재 requirement, specification, contract 또는 agent instruction으로 사용하지 않는다.

현재 상태를 확인할 때는 다음 문서를 사용한다.

- 프로젝트의 현재 단계와 결정 경계: [`docs/project-state.md`](../project-state.md)
- 결정과 그 효력 범위: [`docs/decisions/`](../decisions/README.md)
- 구현이 따라야 할 계약: [`contracts/`](../../contracts/README.md)
- P0의 목적과 종료 조건: [`docs/p0-charter.md`](../p0-charter.md)

역사 기록과 활성 문서가 충돌할 경우 활성 문서를 따른다.

## 읽는 방법

역사 문서를 모든 작업에서 처음부터 읽을 필요는 없다. 다음과 같은 경우에만 관련 기록을 선택적으로 읽는다.

- 이미 검토했던 대안을 다시 논의하려는 경우
- 현재 결정의 배경과 tradeoff를 이해해야 하는 경우
- 오래된 가정이 현재 구현에 남아 있는지 확인하는 경우
- Architecture Synthesis에서 P0 이전의 판단과 실제 결과를 비교하는 경우
- 새로운 참여자에게 프로젝트가 변화한 이유를 설명하는 경우

각 기록은 다음 상태 표기를 사용한다.

- `[현재 유지]`: 현재 Project State 또는 Decision Packet에서도 유지되는 방향
- `[변경됨]`: 이후 논의에서 다른 방향으로 바뀐 판단
- `[보류]`: 판단에 필요한 증거가 없어 아직 확정하지 않은 내용
- `[기각됨]`: 현재 범위에서는 선택하지 않기로 한 대안
- `[역사적 맥락]`: 당시 논의를 이해하는 데 필요하지만 현재 요구사항은 아닌 내용

위 표기는 역사 문서 안에서 과거 판단의 현재 지위를 설명하기 위한 것이다. 프로젝트 공통 evidence label인 `[확인 사실]`, `[측정]`, `[추론]`, `[가설]`, `[결정]`과는 목적이 다르다. 공통 evidence label의 정의는 [`Evidence Labels`](../conventions/evidence-labels.md)를 따른다.

## Raw 대화 처리 원칙

Raw 대화 원문과 session snapshot은 이 저장소의 working tree 안에 보존하지 않는다. Git으로 추적하는지, `.gitignore`로 제외하는지와 관계없이 동일하다.

- 발화 전체 복사본을 저장하지 않는다.
- API key, token, 개인 경로 또는 비공개 데이터가 포함될 수 있는 session snapshot을 repository 내부에 생성하지 않는다.
- 필요한 판단은 요약·재구성하고 현재 문서와 연결한다.
- 원문이 필요한 특별한 사유가 생기면 repository 밖의 별도 private archive 정책을 먼저 결정한다.
- repository 내부에는 local-only transcript 저장 경로를 예약하지 않는다.

## 기록 목록

- [HIST-001 — 초기 데이터 파이프라인 구상에서 폐기형 P0 결정까지](HIST-001-initial-concept-to-p0.md)
