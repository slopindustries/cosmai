# Branching and merge strategy

- 문서 지위: 활성 프로젝트 convention
- 최종 수정일: 2026-08-18

## 브랜치

```text
<area>/<what>   작업 단위. 하나의 개발 영역 안에서 하나의 일.
      ↓         --no-ff merge
     dev        통합 지점. 일상적인 작업이 모이는 곳.
      ↓         PR + --no-ff merge
     main       수락 경계에서만 움직인다.
```

**`main`은 게이트와 수락된 Decision Packet에서만 움직인다.** 이것이 `dev`를 의례가
아니게 만드는 규칙이다.

`[추론]` `dev`의 고전적 근거는 "main은 배포된 것, dev는 통합"인데 **P0는 폐기형이고
배포되지 않는다.** 릴리스가 없으면 `dev`는 기능 브랜치가 이미 하는 격리를 한 번 더
하는 것뿐이고, 헌장이 답하라는 *"쓸모 있는 경계인가 의례인가"* 질문에 걸린다.

`main`을 수락 경계에 묶으면 다른 일을 한다. [P0-A Completion Gate](../experiments/integrated-p0/PLATFORM-CORE-GATE-2026-08-17.md)처럼
게이트는 **특정 리비전이 특정 증거를 만들었다**고 주장하고, 그 주장은 검증 가능해야
한다. `main`이 그런 리비전만 담으면 그 검증이 `main`에서 성립한다. `[확인 사실]` 그
주장은 실제로 한 번 깨졌고([증거 README](../experiments/integrated-p0/evidence/2026-08-17-f83fe3c/README.md)에
기록), 이 규칙은 같은 일이 반복되지 않게 하는 값싼 방법이다.

## 병합

**모든 병합은 merge commit이다. squash도, rebase도, fast-forward도 쓰지 않는다.**

```sh
git merge --no-ff <branch>
```

`[결정]` 이 프로젝트에서 **커밋 메시지는 결정 기록의 일부다.** 왜 그렇게 했는지,
무엇을 일부러 하지 않았는지, 어떤 실패를 어떻게 분류했는지가 거기 적혀 있다. squash는
그것을 지우고, rebase는 어느 커밋이 어느 작업 단위였는지를 지운다.

`merge.ff = false`가 로컬에 설정되어 있지만 **git config는 저장소를 따라 이동하지
않는다.** 새 체크아웃에서 다시 설정하거나, 명령줄에 `--no-ff`를 명시한다. 후자가 설정에
의존하지 않으므로 더 낫다.

## 무엇이 강제되고 무엇이 관례인가

**섞어 읽으면 안 되므로 나눠 적는다.**

### 서버가 강제하는 것

`[확인 사실]` 2026-08-18부터 `main`에 브랜치 보호가 걸려 있다.

- **강제 푸시 금지** (`allow_force_pushes: false`)
- **삭제 금지** (`allow_deletions: false`)
- **관리자에게도 적용** (`enforce_admins: true`) — 관리자가 예외면 이 저장소의 유일한
  관리자에게 규칙이 없는 것과 같다

`[확인 사실]` 이것이 가능해진 것은 저장소를 **공개로 전환**했기 때문이다. 비공개
저장소의 브랜치 보호는 GitHub Pro를 요구하고, 그 전에 시도했을 때
`403 Upgrade to GitHub Pro`로 거부됐다. 권한 문제가 아니라 요금제 제약이었다.

### 관례일 뿐인 것

**`main`으로의 병합은 PR을 거친다 — 그러나 강제되지 않는다.** PR 필수도 리뷰 필수도
일부러 걸지 않았다. 이 프로젝트의 리뷰 권한은 게이트, Decision Packet, adversarial
review에 있고, PR 승인을 얹으면 **두 번째의 더 약한 리뷰 기구**가 생긴다.

**`--no-ff`도 관례다.** `merge.ff = false`는 로컬 설정이고 git config는 저장소를 따라
이동하지 않는다. 명령줄에 `--no-ff`를 명시하는 편이 설정에 의존하지 않아 낫다.

`[결정]` 로컬 `pre-push` hook은 일부러 설치하지 않았다. `--no-verify`로 우회되고 이
체크아웃에서만 유효하므로 **보호처럼 보이면서 보호가 아니다.** 실제보다 강해 보이는
통제는 기록된 부재보다 나쁘다. 이제 강제 푸시와 삭제는 서버가 막으므로 hook이 다룰 일도
남아 있지 않다.

## 브랜치 이름

`<area>/<what>` — `<area>`는 [개발 영역](areas/README.md)의 이름이다.

```text
platform/lease-recovery
domain/snapshot-sealing
addon-api/multi-part-credential
addons/collector-naver-blog
dashboard/source-form
```

`[추론]` 이름이 영역을 담으면 브랜치 목록이 곧 "지금 어느 영역이 움직이고 있는가"가
된다. 여러 에이전트가 동시에 일할 때 그것이 충돌을 예측하는 가장 싼 방법이다.

한 브랜치는 한 영역 안에 머문다. 영역을 넘는 변경은 보통 두 개의 변경이고, 가끔은
경계가 잘못됐다는 신호다 — 후자라면 기록할 증거이지 우회할 대상이 아니다.

## 동시 작업

영역이 파일에서 겹치지 않고 [방향 가드](../tests/environment/test_addon_layer_direction.py)가
그것을 강제하므로, **다른 영역의 두 에이전트는 한 브랜치에서도 충돌하지 않는다.**
브랜치가 필요해지는 것은 격리 때문이 아니라 **따로 병합하고 싶을 때**다.

같은 파일을 건드릴 수밖에 없다면 git worktree로 격리한다.

## 고립되어 보존 중인 브랜치

### `feat/agent-operating-model`

`[확인 사실]` 에이전트 운영 모델 — orchestrator / planner / worker / attacker 역할 분리,
task packet과 attack report 템플릿, project-memory convention. 2026-08-18에 작성됐고
한때 PR #1로 `main`에 병합되어 있었다.

`[결정]` **관계자 합의 하에 `main`에서 되돌리고 이 브랜치로 고립시켰다.** 버려진 작업이
아니다. 병합 전에 검토할 것이 남아 있어 흐름에서 잠시 빼둔 것이며, `dev`에도 병합되어
있지 않다.

`[확인 사실]` 되돌릴 때 확인된 사실 하나: 그 브랜치의 Decision Packet 번호가
`DP-006`이었고, 같은 번호를 [DP-006 — P0-A platform foundation choices](decisions/DP-006-p0a-platform-foundation.md)가
이미 쓰고 있다. 후자가 하루 먼저(2026-08-17) 수락됐고 문서·코드 주석·게이트 기록 전반에서
번호로 참조된다. **재병합 시 번호를 정리해야 한다.**

`[확인 사실]` GitHub의 PR #1은 여전히 "merged"로 표시되지만 그 커밋은 `main`에 없다.
GitHub에서 지울 수 없는 기록상의 모순이며, 여기 적어 두는 것이 유일한 정정 수단이다.

### 그 밖

`origin/sooho` — `00a30bb`을 가리키는 오래된 브랜치. 이 작업과 무관하다.
