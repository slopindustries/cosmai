-- 0004 — what an importer is allowed to read (DP-024).
--
-- `addon_host.capabilities._UNBOUND_KINDS` refuses every importer with the words
-- "open_input needs a registry of approved local inputs, and no document defines one
-- yet". DP-024 is that document and this column is its grant.
--
-- The shape mirrors `outbound_profile` on purpose. A collector names an endpoint and the
-- operator's profile says which host and path that is; an importer names an input and this
-- says which file. In both cases the add-on holds a name and the operator holds the
-- destination, which is the whole of DP-008 D4.
--
--   {"root": "/home/op/datasets/beauty", "inputs": {"rows": "2026-08/posts.jsonl"}}
--
-- Containment is enforced in `domain.inputs`, not here: it needs the filesystem, and a
-- CHECK that compared strings would be the mistake `ADVERSARIAL-REVIEW-2026-08-19.md` F4
-- already found once in the outbound guard.

alter table source add column input_profile jsonb;

-- The mirror of `source_normalizer_reaches_nothing_outside_its_snapshot`. Each kind has
-- exactly one input surface: a collector fetches, an importer reads a file, a normalizer
-- reads a sealed snapshot and nothing else. A row holding both grants would be a source
-- that could do two of those, and the kind split would stop meaning anything.
alter table source add constraint source_only_an_importer_reads_a_local_input
  check (kind = 'importer' or input_profile is null);

-- An importer receives no network capability, so an outbound grant on one would be a
-- grant nothing can spend. `addon_api.manifest` already refuses an importer that
-- *declares* hosts or endpoints; this refuses one that was *granted* a profile.
--
-- `credential_ref` is deliberately **not** forbidden here. `addon_api.manifest` says so in
-- as many words: the platform may need a credential to open a protected input. A rule
-- forbidding it would contradict the contract rather than enforce it.
alter table source add constraint source_an_importer_is_granted_no_outbound_profile
  check (kind <> 'importer' or outbound_profile is null);
