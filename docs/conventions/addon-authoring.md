# Add-on authoring

- 문서 지위: 활성 프로젝트 convention
- 적용 범위: `experiments/integrated-p0/addons/*` 아래의 모든 애드온
- 최종 수정일: 2026-08-18

애드온 하나를 쓰기 위해 알아야 할 전부. [DP-008](../decisions/DP-008-addon-architecture.md)이
결정 기록이라면 이 문서는 작성 지침이다. 결정 기록은 왜 그렇게 정했는지를 적고, 이 문서는
그래서 무엇을 해야 하는지를 적는다.

## 이 문서는 두 부분으로 나뉜다

`[확인 사실]` P0는 폐기형이다([DP-001](../decisions/DP-001-p0-lifecycle.md)). P1은 P0 코드를
다듬는 것이 아니라 **수락된 계약과 승격된 증거로부터 재구성**한다.

`[추론]` 그래서 이 문서의 내용도 두 종류이고, 그 둘은 P1에서 운명이 다르다. 섞어 쓰면 나중에
무엇을 가져가고 무엇을 버릴지 다시 골라내야 하므로, 처음부터 물리적으로 나눈다.

| | 무엇 | P1 처분 |
|---|---|---|
| **1부** | 계약이 요구하는 것 | `PROMOTE` — 살아남는다 |
| **2부** | 지금 P0 구현이 그런 것 | `DELETE` — 사라진다 |

**2부의 내용에 의존하는 코드를 쓰지 마라.** 지금 참이지만 P1에서 참이라는 보장이 없다.

---

# 1부 — 계약이 요구하는 것

`[결정]` 이 절의 규칙은 `addon_api`가 강제하거나 DP-008이 결정한 것이다. P1이 계약을 승격하면
함께 승격된다.

## 애드온이 절대 받지 않는 것

세 가지이고, 예외가 없다.

- **credential.** 어떤 kind의 어떤 context도 credential을 담지 않는다. 플랫폼이 요청 시점에
  해석해서 붙이고, 응답에서 보호 헤더를 제거한 뒤 돌려준다. **애드온은 받은 적 없는 토큰을
  유출할 수 없다.**
- **URL.** `context.fetch(endpoint_ref, params)`는 endpoint **이름**을 받는다. 실제 URL은
  플랫폼이 등록된 source의 승인된 profile에서 만든다.
  `docs/conventions/p0-security.md`의 outbound 의무 전부가 플랫폼 쪽이다.
- **데이터베이스 핸들.** 무엇을 저장할지는 capability로 말하고, 어떻게 저장되는지는 모른다.

## kind마다 받는 것이 다르다

kind는 정도가 아니라 **종류**가 다르다. 수집기는 바깥세상·credential·위치 상태가 필요하고
실패가 부분적일 수 있다. 정규화기는 봉인된 입력만 받고 실패가 부분적일 수 없으며 **결정성이
요구된다.**

| | `collector` | `importer` | `normalizer` |
|---|---|---|---|
| `fetch` | ✓ | — | — |
| `open_input` | — | ✓ | — |
| `read_snapshot` | — | — | ✓ |
| `emit_raw` | ✓ | ✓ | — |
| `emit_result` | — | — | ✓ |
| `advance_cursor` | ✓ | ✓ | — |
| `log` | ✓ | ✓ | ✓ |
| `config` | ✓ | ✓ | ✓ |
| `cursor` | ✓ | ✓ | — |

없는 것은 **의도적으로 보류된 것**이다. 문서로 "쓰지 마시오"라고 적는 것보다 아예 주지 않는
편이 강하다.

## cursor는 지금 스트림 하나뿐이다

`[결정]` `advance_cursor`는 스트림 이름을 받지만 `context.cursor`는 값 하나다. 이 둘이
어떻게 맞물리는지 계약이 말하지 않아서([OQ-010](../open-questions/OQ-010-cursor-stream-read-back.md)),
호스트는 지금 **선언한 스트림 하나**에만 묶는다.

- `[declares].streams`에 이름이 하나면 그 스트림을 읽고 그 스트림에만 쓸 수 있다.
- 하나도 없으면 `default`.
- **둘 이상이면 작업이 거부된다.** 조용히 기본 스트림을 주지 않는다 — 그러면 쓰지도 않는
  스트림을 읽어서 매번 처음부터 다시 수집하고, 그 실패는 아무 데서도 드러나지 않는다.

선언하지 않은 스트림에 `advance_cursor`를 하면 `AddonOutputInvalid`다. cursor 값으로
`None`을 쓰는 것도 마찬가지다 — `None`은 "아직 실행된 적 없음"으로 읽힌다.

`[추론]` 이 절은 처분이 반씩 갈린다. **계약의 비대칭 자체는 P1이 답해야 할 문제**이고,
**둘 이상을 거부하는 것은 지금 호스트의 행동**이다. OQ-010이 닫히면 앞쪽만 남는다.

## 먼저 가져오고, 쓰기는 맡긴다

`[확인 사실]` `emit_raw`와 `advance_cursor`는 **즉시 저장하지 않는다.** 플랫폼이 모아 두었다가
attempt를 완료하는 트랜잭션 안에서 한 번에 쓴다(DP-010). 완료는 그 트랜잭션의 **마지막**이고,
lease를 잃은 워커는 fence에 거부당하면서 쓰기도 같이 롤백된다.

`[추론]` 애드온이 여기서 할 일은 하나다 — **네트워크 작업을 먼저 끝내고, 쓰기는 넘긴다.**
루프 안에서 `fetch`와 `emit_raw`를 번갈아 해도 된다(수집기 예시가 그렇게 한다). 트랜잭션은
네트워크 시간 동안 열려 있지 않다.

그래서 `response.envelope_ref`는 **실행 범위의 손잡이이지 행 id가 아니다.** 애드온이 그 값을
들고 있는 시점에 행은 아직 없다. 애드온이 관측할 수 있는 차이는 없지만, `emit_raw`에 넘기는
`RawItem`은 **이번 실행이 가져온 envelope**을 가리켜야 한다 — 지어낸 값은 거부된다.

`[확인 사실]` 보고한 개수는 검사된다. `CollectOutcome.items_emitted`가 실제로 `emit_raw`한
개수와 다르면 `AddonOutputInvalid`다.

## `endpoint_ref`는 작성자가 정해서 선언하는 이름이다

`context.fetch("blog", params)`의 `"blog"`는 **애드온 작성자가 고르고 manifest의
`[declares].endpoints`에 적는 이름**이다. 설정에서 오는 값이 아니고, 경로 조각도 아니다.
플랫폼이 승인된 outbound profile에서 이 이름을 실제 **경로와 메서드**로 옮긴다.

### POST 엔드포인트와 `body` — 계약 1.1

`[확인 사실]` `fetch`는 인자를 셋 받는다.

```python
context.fetch(endpoint_ref, params=None, body=None)
```

`body`는 [DP-020](../decisions/DP-020-request-method-and-body.md)이 더한 것이고, `params`와
성격이 같다 — **무엇을 묻는가**이지 **어디로 가는가**가 아니다. 규칙이 셋 있다.

- `[확인 사실]` **메서드는 애드온이 고르지 않는다.** endpoint마다 profile이 `GET` 또는 `POST`로
  고정한다. `POST`를 승인받지 않은 endpoint에 `body`를 주면 `METHOD_NOT_ALLOWED`로 거부된다.
- `[확인 사실]` `body`는 `bytes`다. JSON을 보내려면 애드온이 직접 직렬화한다. 애드온은
  `addon_api` 외에 아무것도 import할 수 없지만 `json`은 표준 라이브러리라 쓸 수 있다.
- `[확인 사실]` **크기 한도가 있다.** `Limits.max_request_bytes`(기본 64 KiB)를 넘으면
  `REQUEST_TOO_LARGE`로 거부된다. 이 한도는 요청을 조립하기 **전에** 적용되므로 소켓이 열리지
  않는다.

`[추론]` manifest에는 endpoint 이름만 적는다. 그 이름이 `GET`인지 `POST`인지는 운영자가
승인한 profile이 정하므로, 애드온은 자기가 `POST`를 쓸 것을 **선언할 수는 있어도 허가할 수는
없다**. 이것이 `[declares]`가 요구이지 허가가 아니라는 규칙의 한 사례다.

## importer는 이름으로 파일을 연다 — 계약 1.3

`[확인 사실]` [DP-024](../decisions/DP-024-local-input-registry.md)이 importer를 열었다.
수집기와 같은 모양이고 네트워크만 빠져 있다.

```python
opened = context.open_input("rows")     # "rows"는 manifest의 [declares].inputs에 적은 이름
for line in opened.body.splitlines():   # 파일 전체가 bytes로 온다
    ...
context.emit_raw([RawItem(..., envelope_ref=opened.envelope_ref)])
```

규칙:

- `[확인 사실]` **경로는 절대 애드온의 것이 아니다.** manifest에는 이름만 적고, 그 이름이
  어느 파일인지는 운영자가 승인한 `source.input_profile`이 정한다. 설정 필드에 경로를 두면
  **애드온이 자기 목적지를 짓는 것**이고, 그것이 임의 URL 문제와 같은 것이다.
- `[확인 사실]` **root 밖으로 나갈 수 없다.** `..`, 절대 경로, root 밖을 가리키는 심볼릭 링크는
  전부 거부된다. 심볼릭 링크까지 해석한 **뒤에** 포함 여부를 검사하므로 문자열로는 통과하는
  경로도 잡힌다.
- `[확인 사실]` **`Limits.max_input_bytes`(기본 64 MiB)로 묶인다.** 첫 청크를 읽기 전에
  검사하므로 넘는 파일은 메모리에 올라오지 않는다.
- `[확인 사실]` **`opened.body`는 bytes이지 스트림이 아니다.** 계약의 모든 경계 타입은
  직렬화 가능해야 하고(DP-008 H4), 살아 있는 iterator는 프로세스를 건널 수 없다. 이 절의
  첫 설계가 그래서 거부당했다 — DP-024 D7.
- `[확인 사실]` **importer는 `fetch`를 받지 않는다.** host나 endpoint를 선언하면 로드 시점에
  거부된다. 반대로 `needs_credential`은 합법이다 — 보호된 입력을 여는 데 필요할 수 있다.

⚠️ **거부는 삼킬 수 없다.** `open_input`이 거부되면 예외가 나가고, 애드온이 그것을 잡고
정상 반환해도 그 실행은 실패한다. 수집기의 `fetch`와 같은 규칙이다.

## 상태 코드를 판정하지 않고 끝내면 실패한다 — 계약 1.2

`[확인 사실]` 성공이 아닌 상태 코드를 받고 **아무 판정도 하지 않은 채 애드온이 정상 반환하면
그 실행은 실패 처리된다.** 판정은 둘 중 하나다.

- **예외를 던진다** — 그 상태가 실패라는 판정.
- **`context.accept_status(response, reason)`을 부른다** — 그 상태가 *데이터*라는 판정.

`[추론]` 어떤 API에게 `404`는 "결과 없음"이고 다른 API에게는 "엔드포인트가 틀렸다"이다. 어느
쪽인지는 애드온만 안다. `reason`은 필수이고 로그에 남는다 — 운영자는 누군가 `404`를 데이터로
받았다는 사실만이 아니라 **왜 그렇게 판단했는지**를 봐야 한다.

`[측정]` 이 장치가 생긴 이유는
[ADVERSARIAL-REVIEW-2026-08-19.md](../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-19.md)
F2가 실측한 사건이다. 어떤 수집기가 `401` 응답의 본문에서 항목을 뽑아냈고, 잡은 `SUCCEEDED`로
보고되었으며 `{"errorCode": "SE01"}`이 `raw_item`에 데이터로 저장되었다.

⚠️ **이것은 거부를 삼키는 것과 다르다.** 거부를 삼키면 *실패한다*. 반면 모든 응답에
`accept_status`를 부르면 *성공한다* — 그렇게 하는 애드온은 이 검사가 없애려던 행동을 그대로
되살린 것이다. 플랫폼은 숙고한 수용과 반사적인 수용을 구별할 수 없다. 바뀐 것은 **기본값**이다:
침묵이 성공이었는데 이제 실패다. 옛 행동을 되사는 값은 응답마다 호출 하나와 적힌 이유 하나이고,
둘 다 로그에 남아 셀 수 있다.

⚠️ **`200`으로 오류를 알리는 API는 이 장치가 보지 못한다.** 플랫폼은 상태를 읽지 의미를 읽지
않는다. 그 경우는 전적으로 애드온의 몫이고, 본문을 보고 판단해서 예외를 던져야 한다.

`[확인 사실]` 생성 템플릿은 `base_path`라는 설정 필드를 `fetch`에 그대로 넘기는 예를 보여주는데,
**엔드포인트가 하나뿐인 API에서는 이것이 오히려 오해를 부른다** — 운영자가 설정할 만한 "경로"가
없기 때문이다. 템플릿의 그 부분은 여러 엔드포인트를 가진 API를 가정한 예시이지 규칙이 아니다.

## credential은 조각들의 집합이고, 애드온은 그 중 무엇도 보지 못한다

`[확인 사실]` [DP-018](../decisions/DP-018-credential-parts-and-attachment.md)이
[OQ-009](../open-questions/OQ-009-credential-shape.md)를 P0-B 범위에서 해결했다. credential은
**이름 붙은 조각들의 집합**이고, 각 조각은 secret store의 키 이름 하나이며 보호 헤더 하나를
채운다. 헤더 두 개를 요구하는 소스(예: `X-NCP-APIGW-API-KEY-ID` + `X-NCP-APIGW-API-KEY`)는
조각 두 개로 표현된다.

`[확인 사실]` 이 매핑은 **운영자가 승인한 outbound profile 안에** 있다. manifest가 아니다.
애드온이 적는 것은 `needs_credential = true` 하나뿐이고, 그것은 "나에게 credential을 달라"가
아니라 **"이 source의 요청에는 credential이 붙어야 한다"고 플랫폼에게 알리는 것**이다.

`[확인 사실]` 애드온은 값을 보지 못한다. 키 이름도, 헤더 이름도, 해결된 값도 받지 않는다.
플랫폼이 워커 경계에서 secret store를 읽어 헤더를 채우고, 애드온에게는 응답만 건넨다.

⚠️ 애드온 코드에 헤더 이름이나 키 이름을 적으면 안 된다. `tests/test_addon_credential_hygiene.py`가
설치된 모든 애드온의 실행 코드를 훑어 거부한다. **docstring에 벤더 문서 URL을 인용하는 것은
괜찮다** — 검사는 코드가 무엇을 이름 부르는지를 보지, 산문이 무엇을 설명하는지를 보지 않는다.

`[확인 사실]` 남은 미해결은 OQ-009 H1의 두 경우다: credential이 **쿼리 파라미터**로 가는 소스와
**서명된 요청**을 요구하는 소스. 헤더로 가는 경우는 답이 나왔고, 그 둘은 아니다.

## `[declares]`는 요구이지 허가가 아니다

manifest의 `[declares]`는 애드온이 **필요하다고 말하는 것**이다. 운영자가 승인해서 source
row의 `outbound_profile`에 들어가야 실제 권한이 된다. **애드온은 자기 allowlist를 넓힐 수
없다.**

`needs_credential = true`도 마찬가지다. 이것은 애드온에게 credential을 주라는 뜻이 **아니라**,
이 source의 요청에 credential이 붙어야 한다고 **플랫폼에게** 알리는 것이다.

kind가 감당할 수 없는 선언은 로드 시점에 거부된다. 정규화기가 host를 선언하거나, importer가
endpoint를 선언하면 시작하지 못한다. 조용히 무시하지 않는 이유는 **무시된 선언은 작성자가
발견할 방법이 없기** 때문이다 — 에러도 로그도 동작 변화도 없다.

## 설정 스키마가 표현하지 못하는 것

`[확인 사실]` `[[config.field]]`의 타입은 `string`, `integer`, `boolean` 셋뿐이다. **범위도
enum도 표현할 수 없다.** `display`가 1–100이어야 하거나 `sort`가 `sim`|`date` 중 하나여야 한다면,
그 검증은 애드온이 직접 해야 하고 `help` 텍스트로만 운영자에게 알릴 수 있다.

`[추론]` 그 결과 애드온은 요청을 보내기 전에 스스로 확인해야 한다 — 플랫폼이 대신 거부해주지
않으므로, 잘못된 값이 실제 요청이 되어 나가고 소스가 400으로 돌려주는 것이 현재의 유일한
안전망이다.

## 실패는 종류를 골라서 알린다

`addon_api.errors`의 네 클래스 중 하나를 raise한다. **재시도 여부는 클래스가 정하고, 시도
예산은 플랫폼이 안다.** 애드온은 어떤 종류의 실패인지만 말한다.

| 클래스 | 언제 |
|---|---|
| `AddonTransient` | 같은 호출이 나중에 성공할 수 있다 — rate limit, timeout, 5xx |
| `AddonPermanent` | 재시도가 도움이 안 된다 — 파싱 불가 레코드, 인증 아닌 4xx |
| `AddonConfigInvalid` | 설정이 틀렸고 재시도로 못 고친다 — **401·403은 여기다** |
| `AddonOutputInvalid` | 출력이 선언한 계약을 만족하지 않는다 |

`[확인 사실]` `AddonOutputInvalid`는 보통 애드온이 아니라 **호스트가** 출력을 검증하다 던진다.
그리고 2026-08-18 현재 **그 검증은 존재하지 않는다** — `output_contract_version`은 있는지만
확인되고 쓰이지 않는다. Schema 0.x가 [OQ-003](../open-questions/OQ-003-normalization-protocol.md)에
달려 있기 때문이다. 애드온이 자기 출력을 스스로 검증한다면 이 클래스를 쓰라는 뜻으로 계약에
들어 있다.

`[추론]` 401/403이 `AddonPermanent`가 아닌 이유: credential은 source 설정의 일부이고, 고칠 수
있는 사람은 운영자뿐이다. `p0-security.md`도 해석되지 않는 credential을 non-retryable
configuration failure로 끝내라고 이미 요구한다.

그 밖의 예외를 던져도 애드온이 망가지는 것은 아니다 — 호스트가 영구 실패로 처리하고 예외
타입을 기록한다. 다만 **분류에 대한 발언권을 포기하는 것**이다.

## 자기가 한 일을 정확히 세어서 보고한다

`CollectOutcome(items_emitted=...)`는 애드온이 `emit_raw`로 이미 넘긴 것을 다시 세어서 보고하는
값이다. 중복처럼 보이지만 **교차 확인용**이다 — 자기 작업량을 잘못 세는 애드온은 자기가
생각하는 것과 다른 일을 하고 있다는 가장 싼 신호다.

`[확인 사실]` 2026-08-18 현재 이 교차 확인은 **`addon_kit run` 하네스에만 있다.** capability
레이어(B0.3)가 아직 없어서 `addon_host`는 애드온을 호출하지 않으며, 따라서 세지도 않는다.
`[결정]` 플랫폼이 이 검사를 하고 어긋난 attempt를 실패시키는 것이 DP-008의 의도이고, B0.3이
그것을 구현한다. 그때까지 이 규칙은 계약의 요구이되 강제되지 않는다.

## 정규화기는 결정적이어야 한다

같은 snapshot이 **canonical serialization 후 byte 단위로 동일한** 출력을 내야 한다
([OQ-003](../open-questions/OQ-003-normalization-protocol.md)).

시계, 난수, `config`와 snapshot 밖의 무엇도 읽지 마라 — `NormalizeContext`가 그런 것을 주지
않는다. **키 순서까지 고정해야 한다.** Python dict는 삽입 순서를 유지하므로, 같은 레코드가
다른 키 순서로 들어오면 정렬하지 않는 한 다르게 직렬화된다.

## 버전 축이 넷이고, 각각 실패 방식이 정해져 있다

| 축 | 어긋나면 |
|---|---|
| `requires_contract` | **프로세스 시작 시점에** 로드 거부. job 중에 터지지 않는다 |
| `addon_version` | 결과가 **공존한다.** 덮어쓰지 않는다 |
| `config_schema_version` | source가 `NEEDS_MIGRATION`이 되고 실행을 거부한다 |
| `output_contract_version` | 출력 검증 실패 → 영구 도메인 실패 |

애드온이 아예 없으면 `HANDLER_UNKNOWN`으로 재시도 없이 실패한다.

`[확인 사실]` 네 축 중 **지금 실제로 강제되는 것은 `requires_contract` 하나뿐이다.**
`addon_version`의 결과 공존, `config_schema_version`의 `NEEDS_MIGRATION`, 출력 계약 검증은
모두 아직 구현되지 않았다 — 앞의 둘은 source row와 결과 저장이 필요하고(B0.3, B0.5), 셋째는
Schema 0.x가 필요하다. `[결정]` 계약의 요구로서는 유효하며, manifest에 정확히 적어 두면 구현이
도착했을 때 그대로 동작한다.

## 의존은 `addon_api` 하나뿐

`platform_core`, `domain`, `addon_host`, `addon_kit` 중 어느 것도 import할 수 없다.
`tests/environment/test_addon_layer_direction.py`가 파일과 줄과 규칙을 지목하며 빌드를
실패시킨다.

`platform_core.errors`를 못 쓰는 것도 같은 이유다. 그래서 계약이 자기 taxonomy를 갖고
`addon_host`가 경계에서 번역한다.

---

# 2부 — 지금 P0 구현이 그런 것

`[확인 사실]` 이 절은 **현재 구현의 사실**이지 계약의 요구가 아니다. P1은 계약으로부터
재구성하므로 여기 적힌 것은 보장되지 않는다. **여기 적힌 것에 의존하는 코드를 쓰지 마라.**

## 애드온은 파이썬 파일 하나다

manifest의 `entry` 문법이 `module:callable` 단일 식별자만 허용하므로, 애드온은
`<디렉터리>/<module>.py` 하나다. **상대 import를 쓸 수 없고 여러 파일로 나눌 수 없다.**

`[추론]` 계약이 그것을 요구해서가 아니라, 아직 아무도 필요로 하지 않아서 구현하지 않았다.
필요해지면 계약이 아니라 호스트를 바꾸는 일이다.

## 시작 시점 예외가 두 종류다

manifest가 잘못되면 `ManifestError`, 계약 버전이 안 맞으면 `AddonRefusedError`. **앞의 것은
`PlatformError`가 아니다.** entrypoint가 둘 다 처리해야 한다.

`[추론]` 알려진 거친 부분이고, 어느 쪽으로 정리할지는 기록에 없다.

## 시작 지점을 만드는 방법

```sh
PYTHONPATH=experiments/integrated-p0 .venv/bin/python -m addon_kit \
    new collector.myapi --kind collector
```

`experiments/integrated-p0/addons/collector.myapi/`에 `addon.toml`, `handler.py`,
`README.md`가 생긴다. **생성물은 손대지 않고 그대로 동작해야 한다** — 안 되면 템플릿이 틀린
것이니 보고하라.

## 개발 중에 돌려보는 방법

```sh
PYTHONPATH=experiments/integrated-p0 .venv/bin/python -m addon_kit run \
    experiments/integrated-p0/addons/collector.myapi \
    --fixtures var/samples/myapi \
    --config '{"query":"...","display":10}'
```

fixture 파일 이름이 규약이다: `<endpoint>.<순번>.json`. 한 endpoint의 호출은 순번대로 제공되므로
페이지네이션하는 수집기가 1페이지 다음 2페이지를 본다. fixture가 모자라면 **빈 페이지를 주지 않고
무엇을 추가하라고 이름을 대며 거부한다** — 빈 페이지는 검증되지 않은 애드온을 완료된 것처럼
보이게 만든다.

`--status 429`로 실패 경로를, `--cursor '{"start":11}'`로 이어받기를 시험할 수 있다.

**설정은 manifest의 스키마에 맞춰 검증된다** — 호스트가 하는 것과 같다. 필수 필드가 없으면
애드온에 닿기 전에 거부되고, 선언하지 않은 필드도, `secret = true` 필드를 설정으로 넘기는 것도
거부된다. 마지막 것은 불편이 아니라 배울 점이다: **secret은 저장된 설정에 들어가지 않는다.**

`run_addon(..., validate=False)`로 검증을 끌 수 있고, 용도는 하나다 — **애드온 자신의 방어적
재검사**를 시험하는 것. 호스트는 source row를 쓸 때 검증하지 스키마가 바뀐 뒤 그 row가 job에
도달할 때 다시 검증하지 않으므로, 애드온의 자체 확인은 여전히 값이 있다.

### 하네스가 표현하지 못하는 것

`[확인 사실]` 이 셋은 하네스 API로 도달할 수 없다. 필요하면 `FetchResponse`를 직접 만들어
애드온의 함수를 호출하는 수밖에 없다.

- **응답마다 다른 상태 코드.** `--status`는 한 실행 전체에 하나다. "1페이지는 200, 2페이지는 429"를
  각본으로 쓸 수 없다.
- **응답 헤더.** fixture의 확장자에서 `content-type` 하나만 만들어진다. `Retry-After` 같은 헤더를
  실은 응답을 만들 방법이 없다.
- **여러 엔드포인트를 섞은 실패.** 상태 코드가 전역이므로 한 엔드포인트만 실패시킬 수 없다.

### ⚠️ 하네스를 통과하는 것은 통합의 증거가 아니다

하네스가 보여주지 **못하는** 것 넷:

- **outbound guard** — 여기 `fetch`는 파일을 읽는다. 진짜는 URL을 조립하고 allowlist·redirect·
  DNS·timeout·크기 제한을 걸고 credential을 붙인다. **거부를 만나본 적이 없다.**
- **원자성** — 여기 `emit_raw`와 `advance_cursor`는 리스트에 추가한다. 플랫폼에서는 한
  트랜잭션 안의 문장들이다.
- **재시도·lease·시도 예산** — 여기서 `AddonTransient`는 보고하고 끝난다.
- **영속성** — 아무것도 저장되지 않는다. 다음 실행은 넘긴 cursor에서 시작한다.

통합 증거는 적합성 스위트와 실제 플랫폼 실행에서 나온다.

## 검사하는 방법

```sh
.venv/bin/ruff check experiments/integrated-p0/addons/collector.myapi
.venv/bin/mypy experiments/integrated-p0/addons/collector.myapi
```

전부 검사하려면:

```sh
./scripts/check-addons.sh
```

**애드온을 한 번에 하나씩 검사하는 것은 우회가 아니라 올바른 모델이다.** 애드온은 이름으로
import되지 않고 경로로 로드되는 독립적인 루트이고(DP-008 D2), 모든 애드온의 진입 파일이 관례상
`handler.py`다. 그래서 `mypy experiments/integrated-p0/addons`는 애드온이 둘이 되는 순간
`Duplicate module named handler`로 실패한다. `pyproject.toml`이 전체 검사에서 `addons/`를 제외하는
것은 그 충돌 때문이고, 위 스크립트는 파일 경로를 직접 지정해서 그 제외를 넘어간다 — 제외가
"아무도 검사하지 않음"을 뜻하게 되면 문서로만 남은 검사보다 나쁘기 때문이다.
