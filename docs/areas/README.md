# Development areas

An agent or a person starting work here needs to know **which part of the system they
are in**, because the rules differ by part and some of them are enforced by tests that
will otherwise fail without explaining themselves.

`[가설]` These five areas are the useful component boundaries. That is a hypothesis and
not a settled fact: one of the questions the [P0 Charter](../p0-charter.md) requires P0
to answer is *"which component and process boundaries are useful rather than
ceremonial"*, and this file is the current draft of that answer. P0-B's synthesis
records which of these earned their keep and which turned out to be ceremony.

## The five areas

| Area | Directory | What it owns | Read before working here |
|---|---|---|---|
| **Platform core** | `experiments/integrated-p0/platform_core/` | Jobs, claims, leases, retries, the API and worker lifecycle, logging, metrics, redaction | [DP-006](../decisions/DP-006-p0a-platform-foundation.md), [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md) |
| **Domain foundation** | `experiments/integrated-p0/domain/` | What a registered source, a cursor, Raw, and a snapshot *are* | [DP-008](../decisions/DP-008-addon-architecture.md) D5, [OQ-004](../open-questions/OQ-004-snapshot-boundary.md) |
| **Add-on boundary** | `addon_api/`, `addon_host/`, `addon_kit/` | The contract, the host that loads against it, and the authoring tools | [DP-008](../decisions/DP-008-addon-architecture.md) |
| **Add-ons** | `experiments/integrated-p0/addons/*` | Collectors, importers, normalizers — one directory each | `docs/conventions/addon-authoring.md` |
| **Operator surface** | `experiments/integrated-p0/dashboard/` | The screens an operator uses | [DP-006](../decisions/DP-006-p0a-platform-foundation.md) D6, [OQ-005](../open-questions/OQ-005-operations-contract.md) |

## The one rule that spans all of them

Dependencies point one way, and a test enforces it:

```text
platform_core   ← domain   ← addon_host →   addon_api   ← addons/*
                                            ↑
                                        addon_kit
```

- `addon_api` imports nothing else in the project. It is the contract both sides depend
  on, so a dependency of its own would become a dependency of every add-on.
- **Nothing imports `addons` by name.** They are discovered by scanning a directory and
  loaded by path. A static import would mean the platform knows an add-on exists, which
  is the coupling the add-on layer removes.
- `platform_core` gains nothing from the add-on layer, which is what keeps the P0-A
  gate's evidence standing.

`tests/environment/test_addon_layer_direction.py` fails the build on a violation and
names the file, the line, and the rule. If you are fighting it, you are probably in the
wrong area rather than up against a bad rule.

## Which area is a piece of work in?

Ask what would have to change if the answer were different:

- *Would this change if we picked a different source?* → not platform core.
- *Would this change if the add-on contract's version changed?* → not domain.
- *Does this need the network, a credential, or the database?* → not an add-on. Every
  one of those is the platform's, and an add-on receives none of them.
- *Is this what a source, an observation, or a snapshot **is**?* → domain foundation.
- *Is this how an author writes and checks an add-on?* → add-on boundary (`addon_kit`).

## Two areas that do not exist yet

Recorded so that work does not start in the wrong place by default.

- **A P1 application.** Nothing lives under `apps/` and nothing may until the P0-B P1
  Entry Gate accepts `PoC Contract 0.1`, the artifact disposition, and the
  reconstruction plan. See [DP-005](../decisions/DP-005-two-part-pre-p1-execution.md).
- **Analysis services** such as a trend analyser. These are candidates, not commitments;
  see the [service register](../service-register.md) for what each would need and what
  currently blocks it.
