# Secret Setup

- 문서 지위: 활성 프로젝트 convention의 운영 절차
- 적용 범위: P0-A secret-store location guard와 P0-B source credential 로컬 실행
- 최종 수정일: 2026-08-17

[P0 Security Baseline](p0-security.md)이 정의한 credential 제약을 실제로 적용하는 절차다. 제약과 절차가 충돌하면 `p0-security.md`를 따른다.

## 지켜야 할 불변조건

메커니즘은 P0와 함께 폐기되지만 다음 네 가지는 P1으로 승격된다.

1. Repository working tree 안에 credential 파일이 존재하지 않는다.
2. Credential 값이 프로세스 환경변수에 상주하지 않는다. 사용 시점에 해석하고 요청 수명 동안만 보유한다.
3. Source row, job payload, Raw envelope, log, screenshot, fixture에 credential 값이 남지 않는다. `credential_ref`만 저장한다.
4. Credential이 없거나 해석되지 않으면 non-retryable configuration failure로 종료한다. 빈 값이나 fallback으로 계속하지 않는다.

2번이 나머지 셋보다 늦게 추가됐다. 값을 환경변수로 export하면 모든 자식 프로세스가 **모든** credential을 상속한다. P0는 collector worker, normalizer worker, API, dashboard를 동시에 띄우므로 frontend build tool이 credential을 상속받아 번들에 주입하거나, traceback과 error handler가 환경 전체를 덤프하는 경로가 생긴다. 이는 header/payload 로깅 금지와는 다른 채널이라 별도로 막아야 한다.

아래 절차는 이 불변조건을 만족하는 가장 저렴한 방법이며, 그 자체로는 승격 대상이 아니다.

## 최초 설정

```sh
mkdir -p ~/.config/cosmai
touch ~/.config/cosmai/env
chmod 600 ~/.config/cosmai/env
```

`~/.config/cosmai/env`에 `KEY=VALUE` 형식으로 실제 값을 적는다. Key 이름은 [`config/env.example`](../../config/env.example)에 기록된 규칙을 따른다.

다른 위치를 쓰려면 `COSMA_SECRET_SOURCE`로 경로를 지정하고, 그 사실을 experiment record나 Decision Packet에 남긴다.

## 실행

명령을 `scripts/with-secret-source.sh`로 감싼다.

```sh
./scripts/with-secret-source.sh uv run pytest
./scripts/with-secret-source.sh uv run python -m cosma.worker
```

스크립트가 하는 일은 두 가지뿐이다.

- 실행 전에 store를 검증한다: 존재 여부, repository working tree 밖인지, 권한이 `600` 또는 `400`인지.
- 검증된 **경로**를 `COSMA_SECRET_SOURCE`로 export한다.

Credential 값은 읽지도 export하지도 않는다. 따라서 자식 프로세스는 store 위치만 상속하며, 상속만으로 값이 새는 경로가 존재하지 않는다.

## `credential_ref`

- `credential_ref`는 secret store의 **key 이름 문자열**이다. 값이 아니다.
- 명명 규칙은 `COSMA_SRC_<SOURCE_ID>_<PURPOSE>`.
- 이 문자열은 log와 dashboard에 노출해도 된다. 값은 어디에도 노출하지 않는다.
- Worker가 어떤 `credential_ref`를 해석할 수 있어야 하는지는 아직 미결이다. [OQ-007](../open-questions/OQ-007-credential-scope.md)에서 다룬다.

## Stage boundary

P0-A는 store 위치가 repository working tree 밖인지, 권한과 redaction 및 configuration failure가 안전한지만 검증한다. Source용 key, `credential_ref` authorization, credential resolution과 collector worker 사용은 P0-B에서만 구현한다.

## P0-B Worker 구현 규칙

P0-B 구현 시 다음을 지킨다.

- 해석은 사용 시점에 함수 하나로 처리한다: `resolve_credential(ref) -> SecretStr`. 이 함수가 `COSMA_SECRET_SOURCE`의 store를 직접 읽는다.
- `os.environ`에서 credential을 읽지 않는다. Store를 프로세스 환경으로 펼치지 않는다.
- Resolver 인터페이스나 provider 추상화를 만들지 않는다. 두 번째 secret source가 실제로 필요해지기 전까지는 명명된 불확실성을 줄이지 못하는 추상화다. Store backend 교체는 이 함수 하나를 바꾸는 일로 남는다.
- 값은 `repr`이 redact되는 타입으로 감싼다. 남은 주된 누출 경로는 traceback과 문자열 포매팅이다.
- 미해석 시 configuration failure error class로 종료하고 dashboard에서 구분 가능하게 만든다.
- Store 경로가 repository working tree 아래면 기동 시점에 즉시 실패시킨다. 현재 이 검사는 `scripts/with-secret-source.sh`에만 있으므로 런처를 거치지 않는 실행 경로에는 적용되지 않는다. P0-A에서 애플리케이션 기동 경로와 test session 시작 지점에 같은 가드를 추가해야 platform `SEC-001` 증거로 쓸 수 있다.
- Acceptance test는 실제 credential을 요구하지 않는다. 실제 credential이 필요한 probe는 표시하고 기본 실행에서 제외한다.

## 금지

- Working tree 안의 `.env` 또는 이에 준하는 파일 생성.
- Credential 값을 프로세스 환경변수로 export하기. Process manager, container 정의, IDE run configuration도 동일하다. 주입 경로가 둘 이상이 되면 어느 쪽도 불변조건을 보장하지 못한다.
- Credential 값을 job payload, Raw header, fixture, log, screenshot, error message에 포함하기.
- `config/env.example`에 실제 값 기록.
- P0 범위에서 Vault, KMS, 외부 secret manager 제품 도입 또는 rotation 설계. `p0-security.md`의 non-goal이다.

## 확인 checklist

- [ ] `git status`에 credential 파일이 나타나지 않는다.
- [ ] Store 권한이 `600` 또는 `400`이다.
- [ ] 자식 프로세스 환경에 `COSMA_SECRET_SOURCE` 경로만 있고 credential 값은 없다.
- [ ] DB와 job payload에 `credential_ref` 문자열만 있다.
- [ ] 실패 로그와 dashboard error detail에 값이 나타나지 않는다.
- [ ] Credential 없이 실행하면 non-retryable configuration failure로 종료한다.
