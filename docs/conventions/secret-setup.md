# Secret Setup

- 문서 지위: 활성 프로젝트 convention의 운영 절차
- 적용 범위: source probe와 disposable integrated P0의 로컬 실행
- 최종 수정일: 2026-08-16

[P0 Security Baseline](p0-security.md)이 정의한 credential 제약을 실제로 적용하는 절차다. 제약과 절차가 충돌하면 `p0-security.md`를 따른다.

## 지켜야 할 불변조건

메커니즘은 P0와 함께 폐기되지만 다음 세 가지는 P1으로 승격된다.

1. Repository working tree 안에 credential 파일이 존재하지 않는다.
2. Source row, job payload, Raw envelope, log, screenshot, fixture에 credential 값이 남지 않는다. `credential_ref`만 저장한다.
3. Credential이 없거나 해석되지 않으면 non-retryable configuration failure로 종료한다. 빈 값이나 fallback으로 계속하지 않는다.

아래 절차는 이 불변조건을 만족하는 가장 저렴한 방법이며, 그 자체로는 승격 대상이 아니다.

## 최초 설정

```sh
mkdir -p ~/.config/cosmasignal
touch ~/.config/cosmasignal/env
chmod 600 ~/.config/cosmasignal/env
```

`~/.config/cosmasignal/env`에 `KEY=VALUE` 형식으로 실제 값을 적는다. 변수 이름은 [`config/env.example`](../../config/env.example)에 기록된 규칙을 따른다.

다른 위치를 쓰려면 `COSMA_SECRET_ENV`로 경로를 지정하고, 그 사실을 experiment record나 Decision Packet에 남긴다.

## 실행

명령을 `scripts/with-secrets.sh`로 감싼다.

```sh
./scripts/with-secrets.sh uv run pytest
./scripts/with-secrets.sh uv run python -m cosma.worker
```

스크립트는 실행 전에 다음을 강제한다.

- Secret 파일이 존재하는지 확인한다.
- Secret 파일이 repository working tree 밖에 있는지 확인한다. 안에 있으면 실행을 거부한다.
- 파일 권한이 `600` 또는 `400`인지 확인한다.

애플리케이션 코드는 secret 파일 경로를 알지 못한다. 경로가 코드에 들어가면 파일을 레포 안으로 옮기려는 압력이 생기므로, 로딩은 프로세스 바깥에 둔다.

## `credential_ref`

- `credential_ref`는 환경변수 **이름 문자열**이다. 값이 아니다.
- 명명 규칙은 `COSMA_SRC_<SOURCE_ID>_<PURPOSE>`.
- 이 문자열은 log와 dashboard에 노출해도 된다. 값은 어디에도 노출하지 않는다.

## Worker 구현 규칙

P0 구현 시 다음을 지킨다.

- 해석은 worker 실행 경계에서 함수 하나로 처리한다: `resolve_credential(ref) -> SecretStr`.
- Resolver 인터페이스나 provider 추상화를 만들지 않는다. 두 번째 secret source가 실제로 필요해지기 전까지는 명명된 불확실성을 줄이지 못하는 추상화다.
- 값은 `repr`이 redact되는 타입으로 감싼다. 환경변수 방식의 주된 누출 경로는 traceback과 문자열 포매팅이다.
- 미해석 시 configuration failure error class로 종료하고 dashboard에서 구분 가능하게 만든다.
- Acceptance test는 실제 credential을 요구하지 않는다. 실제 credential이 필요한 probe는 표시하고 기본 실행에서 제외한다.

## 금지

- Working tree 안의 `.env` 또는 이에 준하는 파일 생성.
- Credential 값을 job payload, Raw header, fixture, log, screenshot, error message에 포함하기.
- `config/env.example`에 실제 값 기록.
- P0 범위에서 Vault, KMS, 외부 secret manager 제품 도입 또는 rotation 설계. `p0-security.md`의 non-goal이다.

## 확인 checklist

- [ ] `git status`에 credential 파일이 나타나지 않는다.
- [ ] Secret 파일 권한이 `600` 또는 `400`이다.
- [ ] DB와 job payload에 `credential_ref` 문자열만 있다.
- [ ] 실패 로그와 dashboard error detail에 값이 나타나지 않는다.
- [ ] Credential 없이 실행하면 non-retryable configuration failure로 종료한다.
