# DP-007 — Project rename to Cosmai

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-17
- Owners: Project team
- Supersedes: the two naming decisions in [DP-002](DP-002-project-identity-and-stack.md); every other DP-002 decision stands
- Related Open Questions: none

## Decision question

The project owner renamed the project and moved its repository. Which recorded decisions does that supersede, and how far does the rename reach into the code?

## Decision

`[결정]` Display name: **Cosmai**. Repository: `github.com/slopindustries/cosmai`. Local directory name: `cosmai`.

`[결정]` The secret store's default location becomes `~/.config/cosmai/`. `[확인 사실]` The old directory did not exist on the development machine, so nothing had to be migrated; a machine that does have one moves the file itself, since nothing reads it yet — P0-A resolves no credential and [OQ-007](../open-questions/OQ-007-credential-scope.md) assigns resolution to P0-B.

`[결정]` The `COSMA_` environment-variable prefix is **unchanged**, and so is the `COSMA_SRC_<SOURCE_ID>_<PURPOSE>` naming convention for `credential_ref`.

`[결정]` History documents keep the old name. [HIST-001](../history/HIST-001-initial-concept-to-p0.md) and the history README record what was decided when it was decided, and rewriting them would make the record disagree with itself. DP-002 likewise keeps its original decision text; this packet supersedes it rather than editing it.

## Rationale

The prefix is the one part of the rename with a cost worth weighing. It appears about 190 times across thirty files, including `platform_core.config`'s `PREFIX`, every test that builds an environment, both launcher scripts, and the boundary guard's exact-match allowance for `COSMA_SECRET_SOURCE`.

`[추론]` Renaming it buys nothing measurable. It reads as an abbreviation of the new name as readily as the old one, and every occurrence is inside code DP-001 disposes of — so the churn would land on the exact revision the [P0-A Completion Gate](../../experiments/integrated-p0/PLATFORM-CORE-GATE-2026-08-17.md) certified, hours after it was accepted, to change no behaviour. The gate's evidence directory carries the claim that no code changed since its capture revision, checkable with `git diff`; a prefix rename would spend that claim on a cosmetic edit.

`[추론]` The asymmetry runs the other way for the store path. It is a location a human types once and a convention P0-B builds on, so leaving it under the old name would be a small permanent oddity rather than a saved edit.

## Rejected alternatives

- **Rename `COSMA_` to `COSMAI_` as well.** Consistent, and mechanical enough that 520 tests would have caught any miss. Declined for the reason above; revisit at P1, which is reconstructed from contracts and will name its own settings.
- **Rewrite the name in history and in DP-002.** Would leave no trace that the project was ever called anything else, which is the opposite of what a decision record is for.
- **Rename nothing but the remote.** Leaves the display name contradicting the repository in every document a new contributor reads first.

## Tradeoffs and risks

- Benefit: the documents, the repository, and the store path agree, and the record shows what changed and what deliberately did not.
- Cost: the `COSMA_` prefix is now a visible remnant of the old name. Recorded here so it reads as a decision rather than an oversight.
- Risk: the local checkout directory is still `cosma-signal` on the development machine. Moving it is the owner's action; nothing in the repository depends on the directory's name.
- Reversibility: full for the names. The remote move is the owner's and is already done.

## Remaining uncertainty

- Whether P1 keeps `COSMA_` or takes a prefix of its own. Not a P0 question.

## Change record

| Version | Date | Change | Evidence or decision |
|---|---|---|---|
| Accepted | 2026-08-17 | Rename accepted; DP-002's two naming decisions superseded; prefix and history deliberately unchanged | Owner instruction; [P0-A Completion Gate](../../experiments/integrated-p0/PLATFORM-CORE-GATE-2026-08-17.md) |
