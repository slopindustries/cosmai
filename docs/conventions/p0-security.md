# P0 Security Baseline

- 문서 지위: `ACCEPTED_FOR_POC` safety constraint
- 적용 범위: source probe와 disposable integrated P0
- 최종 수정일: 2026-08-16

## 목적과 경계

P0가 폐기형 prototype이라는 사실은 실제 credential, 외부 네트워크, dataset과 debug data를 안전하지 않게 다룰 이유가 되지 않는다. 이 문서는 production IAM 또는 secret-management 제품을 선택하지 않고도 지켜야 하는 최소 불변조건을 정의한다.

## Local execution boundary

- API와 Dashboard는 기본적으로 loopback interface에만 bind한다.
- 별도 Decision Packet 없이 public ingress, shared staging 또는 internet-facing deployment를 만들지 않는다.
- 인증이 없는 P0 UI는 local operator boundary 밖에서 사용할 수 있다고 가정하지 않는다.
- local boundary를 넘어야 하는 실험은 먼저 threat, identity, authorization과 data exposure를 별도 질문으로 기록한다.

## Outbound source policy

- Dashboard와 job payload는 임의 URL이 아니라 등록된 `source_id`를 선택한다.
- Source profile에는 허용 HTTPS scheme, hostname, port와 endpoint path 범위를 기록한다.
- HTTP redirect가 발생하면 destination을 같은 정책으로 다시 검증한다.
- DNS resolution 결과가 loopback, private, link-local, multicast 또는 허용되지 않은 address range이면 차단한다.
- connect/read timeout, maximum redirects, response body size와 page/record limit을 source별로 둔다.
- Network error와 HTTP response를 기록할 때 Authorization, Cookie와 provider-protected header를 제거한다.

P0에서는 범용 URL fetcher를 만들지 않는다. 선택된 source의 bounded behavior를 검증하는 것이 목적이다.

## Agent sandbox baseline

Agent 실행 샌드박스는 application의 outbound source policy와 **독립적인 두 번째 강제 지점**이다. Application 쪽 검증에 결함이 있어도 샌드박스가 egress를 막는다.

M0 현재 상태는 의도적으로 넓게 열려 있다.

- `[결정]` M0 한정으로 `sandbox.network.allowedDomains: ["*"]`와 `sandbox.autoAllowBashIfSandboxed: true`를 적용한다. 근거: 레포에 실행 코드와 credential이 없고, 의존성 설치와 도구 실행 편의가 우선한다.
- `[확인 사실]` 이 조합은 프롬프트 없는 임의 외부 요청을 허용한다. 문서만 있는 레포에서만 성립하는 트레이드오프다.

**P0 프로토타이핑 진입 시 반드시 조정한다.** 첫 source probe가 실제 outbound 요청을 만들기 전에 다음을 수행한다.

- `allowedDomains`를 등록된 source profile의 host와 필요한 package registry로 좁힌다.
- 정책상 접근 금지 대상은 `deniedDomains`에 명시한다. `deniedDomains`는 모든 설정 소스에서 병합되며 `allowedDomains`보다 우선한다.
- `autoAllowBashIfSandboxed`를 유지할지 재검토한다. 실행 코드와 credential이 생긴 뒤에는 M0의 근거가 더 이상 성립하지 않는다.
- 조정 결과를 첫 source probe experiment record의 Environment에 남긴다.

## Credential handling

- Code, committed config, database, job payload, Raw header, fixture, log, screenshot에 secret 원문을 저장하지 않는다.
- Source와 job에는 opaque `credential_ref`만 저장한다.
- Worker가 사용 시점에 승인된 local secret source에서 reference를 해석하고, 값을 요청 수명 동안만 보유한다.
- Credential 값을 프로세스 환경변수로 export하지 않는다. 환경으로 펼치면 모든 자식 프로세스가 모든 credential을 상속하며, 이는 log 통제와 다른 유출 채널이다. 실행 경계에는 store 위치만 전달한다.
- Worker가 어떤 reference를 해석할 수 있어야 하는지는 [OQ-007](../open-questions/OQ-007-credential-scope.md)에서 결정한다. 그때까지 범위 제한을 확정된 것으로 다루지 않는다.
- 공개 가능한 key 이름과 형식은 `config/env.example`에 기록한다.
- 실제 credential 값은 repository working tree 밖의 승인된 local secret source에만 둔다. 기본 위치는 `~/.config/cosmasignal/`이며 다른 위치를 쓰려면 실험 기록이나 Decision Packet에 남긴다.
- Working tree 안에는 `.env`를 포함해 어떤 secret 파일도 만들지 않는다. `.gitignore`와 agent permission deny 규칙은 안전망이지 유일한 방어선이 아니다.
- 적용 절차는 [Secret Setup](secret-setup.md)에 있다.
- Credential이 없거나 해석되지 않으면 명시적인 non-retryable configuration failure로 종료한다. 빈 값이나 fallback credential로 계속하지 않는다.

## Logs and debug evidence

- Structured log에는 correlation identifiers와 분류된 error만 기록한다.
- Header와 payload를 통째로 log하지 않는다.
- Debug detail은 allowlisted field 또는 redacted summary로 만든다.
- Redaction 실패 가능성이 있는 output은 `private`로 분류하며 에이전트나 Git evidence에 사용하지 않는다.
- Dashboard screenshot과 exported trace도 같은 data classification을 적용한다.

## Dataset and personal data

- Dataset은 [Data Handling Convention](data-handling.md)에 따라 분류한다.
- P0 목적에 불필요한 personal data는 ingest하지 않는다.
- 예상하지 못한 sensitive field가 발견되면 해당 input 처리를 중단하고 artifact를 승격하지 않는다.
- 테스트는 synthetic 또는 허용된 최소 fixture를 우선 사용한다.

## Minimum acceptance evidence

- `SEC-001`: secret과 protected header가 log, error, Raw metadata와 screenshot에 나타나지 않는다.
- `SEC-002`: 등록되지 않은 source 또는 허용되지 않은 host 요청이 실행 전에 거부된다.
- `SEC-003`: redirect와 DNS 결과가 source policy를 벗어나면 거부된다.
- `SEC-004`: oversized/slow response가 bounded failure로 종료되고 worker를 무기한 점유하지 않는다.
- `SEC-005`: P0 operator surface가 기본 설정에서 loopback 밖에 노출되지 않는다.
- `SEC-006`: Agent 샌드박스의 `allowedDomains`가 M0의 `["*"]`에서 등록된 source host와 필요한 registry로 좁혀져 있다.

## Non-goals

- Production identity provider 선택
- Vault/KMS 제품 선택
- Multi-tenant authorization
- Internet-facing deployment hardening
- 조직 전체 보안 또는 compliance 인증
