"""Renders a new add-on skeleton from `addon_kit/template/`, and refuses to overwrite one.

DP-008 D4 is one package format with three capability sets: packaging, manifest
shape, discovery, versioning, and config schema are shared, and only the granted
capabilities and the `[declares]` fields a kind may state differ. This module
writes that asymmetry down as data — three small dictionaries keyed by `Kind` —
rather than as three separate template directories, because the packaging really
is one thing and only the body of `run` is three things.

**Token convention.** Every file under `template/` is plain text with placeholder
tokens: an ALL-CAPS name wrapped in double underscores, each occupying its own
source line (e.g. `__ADDON_ID__`, `__BODY__`). Substitution is a literal string
replace — no templating engine, no control flow, nothing this project does not
already control end to end, for the same reason `addon_api.manifest`'s
version-range parser stops short of PEP 440. A token replaced with an empty
string leaves a blank line, which TOML, Markdown, and Python all tolerate; a
token replaced with a multi-line block must carry its own indentation, because
the template only supplies the indentation of the token's own line, not of
whatever replaces it.

Because the tokens are placeholders rather than valid Python or TOML, the raw
files under `template/` do not parse or type-check on their own — only a
*generated* add-on does, which is what `test_addon_kit.py` checks. `_render`'s
leftover-token check exists so that adding a token to a template file without
adding it to the substitution map fails here, at generation time, rather than
producing a skeleton with a literal `__SOMETHING__` sitting in it.
"""

from __future__ import annotations

import re
from pathlib import Path

from addon_api import AddonManifest, Kind

#: One directory below `addon_kit/`, sitting beside `platform_core` and
#: `addon_api` — the location fixed by the task, not derived from `addon_host`
#: (which this package must not import; see DP-008 D1).
TEMPLATE_DIR = Path(__file__).resolve().parent / "template"

#: `apps/addons`. Mirrors `addon_host.settings.DEFAULT_ADDON_DIR` by construction
#: rather than by import: that module lives in a package this one may not depend
#: on, and the path is two lines of `pathlib`, not a shared secret. Copy-adapted
#: from P0's `experiments/integrated-p0/addons` (M3 batch 3a) — one directory
#: below `addon_kit/`, the same relative shape, at this tree's own root.
DEFAULT_ADDONS_ROOT = Path(__file__).resolve().parents[1] / "addons"

ADDON_VERSION = "0.1.0"

_TOKEN = re.compile(r"__[A-Z][A-Z_]*__")


class AddonKitError(Exception):
    """A refusal `addon_kit` makes on its own account.

    A malformed `addon_id` — or any other manifest-level problem — surfaces as
    `addon_api.ManifestError` instead: `new_addon` renders a manifest and parses
    it back through `AddonManifest.parse` rather than checking the id itself, so
    the id rule has exactly one definition in the whole project.
    """


def _read(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def _render(text: str, tokens: dict[str, str]) -> str:
    for token, value in tokens.items():
        text = text.replace(token, value)
    leftover = sorted(set(_TOKEN.findall(text)))
    if leftover:
        raise AddonKitError(
            f"template left {leftover} unsubstituted; this is a bug in addon_kit, "
            "not in the add-on being generated"
        )
    return text


# --------------------------------------------------------------------------- #
# What differs by kind. Everything else is the template files themselves.
# --------------------------------------------------------------------------- #

_OUTPUT_CONTRACT_LINE: dict[Kind, str] = {
    "collector": "",
    "importer": "",
    "normalizer": 'output_contract_version = "0.1"',
}

_CONFIG_FIELDS: dict[Kind, str] = {
    "collector": (
        '[[config.field]]\n'
        'name = "base_path"\n'
        'type = "string"\n'
        "required = true\n"
        'label = "Endpoint path"\n'
        'help = "Path appended to the source\'s base URL, e.g. /v1/items"\n'
        "\n"
        "[[config.field]]\n"
        'name = "api_token"\n'
        'type = "string"\n'
        "required = true\n"
        "secret = true\n"
        'label = "API token"\n'
        'help = "Routed to the secret store; this add-on never receives the value (DP-008 D6)"\n'
        "\n"
        "[[config.field]]\n"
        'name = "page_size"\n'
        'type = "integer"\n'
        "required = false\n"
        'label = "Page size"\n'
        'help = "Records requested per page; omit to use the source\'s own default"'
    ),
    "importer": (
        '[[config.field]]\n'
        'name = "input_ref"\n'
        'type = "string"\n'
        "required = true\n"
        'label = "Registered input"\n'
        'help = "Identifies which registered file open_input should read"\n'
        "\n"
        "[[config.field]]\n"
        'name = "input_encoding"\n'
        'type = "string"\n'
        "required = false\n"
        'label = "Input encoding"\n'
        'help = "Text encoding of the registered input file, e.g. utf-8"'
    ),
    "normalizer": (
        '[[config.field]]\n'
        'name = "strict"\n'
        'type = "boolean"\n'
        "required = false\n"
        'label = "Strict parsing"\n'
        'help = "Raise instead of skipping a snapshot item this add-on cannot parse"'
    ),
}

_DECLARES: dict[Kind, str] = {
    "collector": (
        "[declares]\n"
        'hosts = ["api.example.com"]\n'
        'endpoints = ["/v1/items"]\n'
        'streams = ["items"]\n'
        "needs_credential = true"
    ),
    "importer": ('[declares]\nstreams = ["items"]'),
    # A normalizer must declare none of hosts, endpoints, streams, or
    # needs_credential (DP-008 D4), so the section is simply absent; an empty
    # [declares] table would parse to the same Declarations but say less.
    "normalizer": "",
}

_CONTEXT_TYPE: dict[Kind, str] = {
    "collector": "CollectContext",
    "importer": "ImportContext",
    "normalizer": "NormalizeContext",
}

_OUTCOME_TYPE: dict[Kind, str] = {
    "collector": "CollectOutcome",
    "importer": "CollectOutcome",
    "normalizer": "NormalizeOutcome",
}

_IMPORTS: dict[Kind, str] = {
    "collector": (
        "from addon_api.context import CollectContext\n"
        "from addon_api.errors import AddonConfigInvalid, AddonPermanent, AddonTransient\n"
        "from addon_api.results import CollectOutcome, RawItem"
    ),
    "importer": (
        "from addon_api.context import ImportContext\n"
        "from addon_api.errors import AddonConfigInvalid, AddonPermanent\n"
        "from addon_api.results import CollectOutcome, RawItem"
    ),
    "normalizer": (
        "import json\n"
        "from typing import Any\n"
        "\n"
        "from addon_api.context import NormalizeContext\n"
        "from addon_api.errors import AddonPermanent\n"
        "from addon_api.results import NormalizedResult, NormalizeOutcome"
    ),
}

_BODY: dict[Kind, str] = {
    "collector": (
        '    base_path = context.config_field("base_path")\n'
        "    if not isinstance(base_path, str) or not base_path:\n"
        "        raise AddonConfigInvalid(\n"
        '            "base_path is not configured", {"source_id": context.source_id}\n'
        "        )\n"
        "\n"
        "    response = context.fetch(\n"
        '        base_path, {"page_size": str(context.config_field("page_size", 50))}\n'
        "    )\n"
        "    if response.status >= 500:\n"
        "        raise AddonTransient(\n"
        '            f"{base_path} returned {response.status}", {"status": response.status}\n'
        "        )\n"
        "    if response.status in (401, 403):\n"
        "        raise AddonConfigInvalid(\n"
        '            f"{base_path} rejected the configured credential",\n'
        '            {"status": response.status},\n'
        "        )\n"
        "    if response.status >= 400:\n"
        "        raise AddonPermanent(\n"
        '            f"{base_path} returned {response.status}", {"status": response.status}\n'
        "        )\n"
        "\n"
        "    item = RawItem(\n"
        '        item_key="page-1",\n'
        "        payload=response.body,\n"
        '        content_type=response.headers.get("content-type", "application/octet-stream"),\n'
        "        envelope_ref=response.envelope_ref,\n"
        "    )\n"
        "    context.emit_raw([item])\n"
        '    context.advance_cursor("items", {"retrieved_at": response.retrieved_at})\n'
        '    context.log("collect.page_fetched", {"status": response.status, "items": 1})\n'
        "    return CollectOutcome(items_emitted=1, more_available=False)"
    ),
    "importer": (
        '    input_ref = context.config_field("input_ref")\n'
        "    if not isinstance(input_ref, str) or not input_ref:\n"
        "        raise AddonConfigInvalid(\n"
        '            "input_ref is not configured", {"source_id": context.source_id}\n'
        "        )\n"
        "\n"
        "    try:\n"
        '        payload = b"".join(context.open_input(input_ref))\n'
        "    except OSError as error:\n"
        '        raise AddonPermanent(f"{input_ref} could not be read: {error}") from error\n'
        "\n"
        "    item = RawItem(\n"
        '        item_key=input_ref, payload=payload, content_type="application/octet-stream"\n'
        "    )\n"
        "    context.emit_raw([item])\n"
        '    context.advance_cursor("items", {"input_ref": input_ref})\n'
        '    context.log("import.file_read", {"input_ref": input_ref, "bytes": len(payload)})\n'
        "    return CollectOutcome(items_emitted=1, more_available=False)"
    ),
    "normalizer": (
        '    strict = bool(context.config_field("strict", False))\n'
        "    results: list[NormalizedResult] = []\n"
        "    skipped = 0\n"
        "    for item in context.read_snapshot():\n"
        "        try:\n"
        '            text = item.payload.decode("utf-8")\n'
        "        except UnicodeDecodeError as error:\n"
        "            raise AddonPermanent(\n"
        '                f"{item.item_key} is not valid utf-8", {"item_key": item.item_key}\n'
        "            ) from error\n"
        "        try:\n"
        "            record = json.loads(text)\n"
        "        except json.JSONDecodeError as error:\n"
        "            if strict:\n"
        "                raise AddonPermanent(\n"
        '                    f"{item.item_key} is not valid JSON", {"item_key": item.item_key}\n'
        "                ) from error\n"
        "            skipped += 1\n"
        "            continue\n"
        "        if not isinstance(record, dict):\n"
        "            skipped += 1\n"
        "            continue\n"
        "        body: dict[str, Any] = {str(key): value for key, value in record.items()}\n"
        "        results.append(NormalizedResult(source_item_key=item.item_key, body=body))\n"
        "\n"
        "    context.emit_result(results)\n"
        "    context.log(\n"
        '        "normalize.snapshot_read", {"emitted": len(results), "skipped": skipped}\n'
        "    )\n"
        "    return NormalizeOutcome(results_emitted=len(results), skipped=skipped)"
    ),
}

_CAPABILITIES: dict[Kind, str] = {
    "collector": (
        "- `context.fetch(endpoint_ref, params)` — one request through the platform's\n"
        "  outbound guard; returns a `FetchResponse` whose bytes are already recorded as\n"
        "  a Raw envelope, whether or not this add-on emits anything from it.\n"
        "- `context.emit_raw(items)` — hand off carved `RawItem`s for durable, lossless\n"
        "  storage.\n"
        "- `context.advance_cursor(stream, cursor)` — record where this stream stopped.\n"
        "- `context.log(event, fields)`, `context.config_field(name, fallback)`.\n"
        "\n"
        "No `open_input` and no `read_snapshot` — those belong to the other two kinds."
    ),
    "importer": (
        "- `context.open_input(input_ref)` — a registered local input, streamed in\n"
        "  chunks.\n"
        "- `context.emit_raw(items)` — hand off carved `RawItem`s for durable, lossless\n"
        "  storage.\n"
        "- `context.advance_cursor(stream, cursor)` — record where this input stopped.\n"
        "- `context.log(event, fields)`, `context.config_field(name, fallback)`.\n"
        "\n"
        "No `fetch` — an importer that wants the network is a collector that has not\n"
        "admitted it (DP-008 D4), and its manifest cannot declare `[declares].hosts`."
    ),
    "normalizer": (
        "- `context.read_snapshot()` — the sealed, hash-verified snapshot, as\n"
        "  `SnapshotItem`s.\n"
        "- `context.emit_result(results)` — hand off `NormalizedResult`s, each tied back\n"
        "  to the Raw item it came from by `source_item_key`.\n"
        "- `context.log(event, fields)`, `context.config_field(name, fallback)`.\n"
        "\n"
        "No `fetch`, no `open_input`, no credential, and no cursor — the input is fixed\n"
        "before the run starts, and the output must be deterministic byte-for-byte from\n"
        "it (OQ-003). This add-on's manifest must declare\n"
        "`[addon].output_contract_version` and must not declare `[declares].hosts`,\n"
        "`.endpoints`, `.streams`, or `needs_credential`."
    ),
}


def render_manifest(addon_id: str, kind: Kind) -> str:
    """`addon.toml` text for `kind`. Not yet validated — `new_addon` parses it back."""
    return _render(
        _read("addon.toml.tmpl"),
        {
            "__ADDON_ID__": addon_id,
            "__ADDON_VERSION__": ADDON_VERSION,
            "__KIND__": kind,
            "__OUTPUT_CONTRACT_LINE__": _OUTPUT_CONTRACT_LINE[kind],
            "__CONFIG_FIELDS__": _CONFIG_FIELDS[kind],
            "__DECLARES__": _DECLARES[kind],
        },
    )


def render_handler(addon_id: str, kind: Kind) -> str:
    """`handler.py` text for `kind`, matching the entry `render_manifest` declares."""
    return _render(
        _read("handler.py.tmpl"),
        {
            "__ADDON_ID__": addon_id,
            "__KIND__": kind,
            "__IMPORTS__": _IMPORTS[kind],
            "__CONTEXT_TYPE__": _CONTEXT_TYPE[kind],
            "__OUTCOME_TYPE__": _OUTCOME_TYPE[kind],
            "__BODY__": _BODY[kind],
        },
    )


def render_readme(addon_id: str, kind: Kind) -> str:
    """`README.md` text for `kind`."""
    return _render(
        _read("README.md.tmpl"),
        {
            "__ADDON_ID__": addon_id,
            "__KIND__": kind,
            "__CAPABILITIES__": _CAPABILITIES[kind],
        },
    )


def new_addon(addon_id: str, kind: Kind, into: Path) -> Path:
    """Write a skeleton add-on for `kind` into `into`, and return `into`.

    Refuses outright if `into` already exists — DP-008 D8 makes the add-on
    directory the installed set, so silently overwriting one is silently
    replacing what is installed. `addon_id` is validated by rendering a manifest
    and parsing it back through `AddonManifest.parse`: a bad id surfaces as
    `ManifestError`, the contract's own refusal, rather than a second regex this
    package would have to keep in step with `addon_api`'s.

    Nothing is written until the manifest has parsed, so a rejected id or kind
    leaves no partial directory behind.
    """
    if into.exists():
        raise AddonKitError(f"{into} already exists; addon_kit refuses to overwrite it")

    manifest_text = render_manifest(addon_id, kind)
    AddonManifest.parse(manifest_text, where=f"<addon_kit new {addon_id!r} --kind {kind}>")
    handler_text = render_handler(addon_id, kind)
    readme_text = render_readme(addon_id, kind)

    into.mkdir(parents=True)
    (into / "addon.toml").write_text(manifest_text, encoding="utf-8")
    (into / "handler.py").write_text(handler_text, encoding="utf-8")
    (into / "README.md").write_text(readme_text, encoding="utf-8")
    return into
