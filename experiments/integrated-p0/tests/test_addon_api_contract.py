"""The add-on contract's own tests: manifests, version ranges, and configuration.

These exercise ``addon_api`` alone. No host, no database, no add-on — the contract
is the one part of DP-008 that both sides depend on, so it is tested without
either of them present.

The tests that matter most are the refusals. A contract that accepts a malformed
manifest has moved the failure to load time at best and to job time at worst, and
the whole point of D3's version axes is that each mismatch fails in a stated place.
"""

from __future__ import annotations

import pytest
from addon_api import (
    CONTRACT_VERSION,
    AddonManifest,
    ConfigField,
    ConfigValidationError,
    ContractVersion,
    ManifestError,
    VersionRange,
    validate_config,
)

COLLECTOR_TOML = """
[addon]
id = "collector.rest.example"
version = "0.1.0"
kind = "collector"
entry = "handler:run"
requires_contract = ">=1.0,<2.0"

[config]
schema_version = "1"

[[config.field]]
name = "base_path"
type = "string"
required = true
label = "Endpoint path"

[[config.field]]
name = "api_token"
type = "string"
required = true
secret = true
label = "API token"

[[config.field]]
name = "page_size"
type = "integer"
required = false

[declares]
hosts = ["api.example.com"]
endpoints = ["/v1/items"]
streams = ["items"]
needs_credential = true
"""

NORMALIZER_TOML = """
[addon]
id = "normalizer.conformance"
version = "0.1.0"
kind = "normalizer"
entry = "handler:run"
requires_contract = ">=1.0,<2.0"
output_contract_version = "0.1"
"""


def test_a_collector_manifest_parses_into_what_the_host_needs() -> None:
    manifest = AddonManifest.parse(COLLECTOR_TOML)
    assert manifest.addon_id == "collector.rest.example"
    assert manifest.addon_version == "0.1.0"
    assert manifest.kind == "collector"
    assert manifest.entry_module == "handler"
    assert manifest.entry_attribute == "run"
    assert manifest.config_schema_version == "1"
    assert [item.name for item in manifest.config_schema] == [
        "base_path",
        "api_token",
        "page_size",
    ]
    assert manifest.declares.hosts == ("api.example.com",)
    assert manifest.declares.streams == ("items",)
    assert manifest.declares.needs_credential is True
    assert manifest.output_contract_version is None


def test_the_manifest_names_its_secret_fields_so_the_host_can_route_them() -> None:
    """D6's whole mechanism: the host reads this, not a per-add-on special case."""
    manifest = AddonManifest.parse(COLLECTOR_TOML)
    assert [item.name for item in manifest.secret_fields()] == ["api_token"]


def test_a_manifest_declaring_this_contract_version_is_supported() -> None:
    manifest = AddonManifest.parse(COLLECTOR_TOML)
    assert manifest.supports(CONTRACT_VERSION) is True
    assert manifest.supports("2.0") is False
    assert manifest.supports("0.9") is False


class TestVersionRanges:
    def test_a_range_is_a_conjunction_of_comparators(self) -> None:
        span = VersionRange.parse(">=1.0,<2.0")
        assert span.matches(ContractVersion(1, 0)) is True
        assert span.matches(ContractVersion(1, 7)) is True
        assert span.matches(ContractVersion(2, 0)) is False
        assert span.matches(ContractVersion(0, 9)) is False

    def test_minor_versions_order_numerically_not_lexically(self) -> None:
        """``1.10`` is above ``1.9``; string comparison would say otherwise."""
        span = VersionRange.parse(">=1.9")
        assert span.matches(ContractVersion(1, 10)) is True

    def test_an_exact_pin_is_available(self) -> None:
        span = VersionRange.parse("==1.0")
        assert span.matches(ContractVersion(1, 0)) is True
        assert span.matches(ContractVersion(1, 1)) is False

    @pytest.mark.parametrize("text", ["", "1.0", "~=1.0", ">=1", ">=1.0.0", ">= x.y", ",,"])
    def test_a_range_the_parser_does_not_understand_is_refused(self, text: str) -> None:
        with pytest.raises(ManifestError):
            VersionRange.parse(text)

    @pytest.mark.parametrize("text", [">=1.0,", " >=1.0 , <2.0 ", ">=1.0,,<2.0"])
    def test_empty_clauses_and_surrounding_space_are_tolerated(self, text: str) -> None:
        """A trailing comma is unambiguous, so refusing it would buy nothing.

        This started as a refusal in the test and a tolerance in the parser. The
        parser was right: ``">=1.0,"`` has exactly one reading, TOML and Python
        both accept a trailing comma in a list, and rejecting it would cost an
        add-on author a load-time failure in exchange for no safety. Recorded as
        an evaluation failure rather than an implementation one — the code was
        never wrong, the expectation was.

        ``",,"`` stays refused because it states no constraint at all, which a
        manifest asking for one should never do silently.
        """
        assert VersionRange.parse(text).matches(ContractVersion(1, 0)) is True

    def test_a_contract_version_must_be_major_dot_minor(self) -> None:
        assert ContractVersion.parse("1.0") == ContractVersion(1, 0)
        with pytest.raises(ManifestError):
            ContractVersion.parse("1")
        with pytest.raises(ManifestError):
            ContractVersion.parse("1.0.0")


class TestManifestRefusals:
    def test_a_missing_addon_table_is_named(self) -> None:
        with pytest.raises(ManifestError, match=r"\[addon\] table"):
            AddonManifest.parse("[config]\nschema_version = '1'\n")

    def test_an_unknown_kind_lists_the_known_ones(self) -> None:
        toml = COLLECTOR_TOML.replace('kind = "collector"', 'kind = "scraper"')
        with pytest.raises(ManifestError, match="collector, importer, normalizer"):
            AddonManifest.parse(toml)

    def test_an_entry_that_is_not_module_colon_callable_is_refused(self) -> None:
        toml = COLLECTOR_TOML.replace('entry = "handler:run"', 'entry = "handler.run"')
        with pytest.raises(ManifestError, match="module:callable"):
            AddonManifest.parse(toml)

    def test_an_addon_id_that_is_not_a_safe_directory_name_is_refused(self) -> None:
        toml = COLLECTOR_TOML.replace(
            'id = "collector.rest.example"', 'id = "../escape"'
        )
        with pytest.raises(ManifestError, match=r"\[addon\].id"):
            AddonManifest.parse(toml)

    def test_duplicate_config_field_names_are_refused(self) -> None:
        toml = COLLECTOR_TOML.replace('name = "page_size"', 'name = "base_path"')
        with pytest.raises(ManifestError, match="duplicate config field"):
            AddonManifest.parse(toml)

    def test_a_non_string_secret_field_is_refused(self) -> None:
        toml = COLLECTOR_TOML.replace(
            'name = "api_token"\ntype = "string"', 'name = "api_token"\ntype = "integer"'
        )
        with pytest.raises(ManifestError, match="secret field"):
            AddonManifest.parse(toml)

    def test_invalid_toml_says_so_rather_than_raising_something_else(self) -> None:
        with pytest.raises(ManifestError, match="not valid TOML"):
            AddonManifest.parse("[addon\nid =")


class TestKindConsistency:
    """A kind's declarations must match the capabilities that kind is granted.

    Catching this at load time is the point. The alternative is an add-on
    reaching for a ``fetch`` its context does not carry, which surfaces as an
    ``AttributeError`` in the middle of a job.
    """

    def test_a_normalizer_parses_when_it_declares_nothing_it_cannot_have(self) -> None:
        manifest = AddonManifest.parse(NORMALIZER_TOML)
        assert manifest.kind == "normalizer"
        assert manifest.output_contract_version == "0.1"
        assert manifest.declares.hosts == ()

    def test_a_normalizer_asking_for_a_host_is_refused(self) -> None:
        toml = NORMALIZER_TOML + '\n[declares]\nhosts = ["api.example.com"]\n'
        with pytest.raises(ManifestError, match="no network capability"):
            AddonManifest.parse(toml)

    def test_a_normalizer_asking_for_a_credential_is_refused(self) -> None:
        toml = NORMALIZER_TOML + "\n[declares]\nneeds_credential = true\n"
        with pytest.raises(ManifestError, match="no credential"):
            AddonManifest.parse(toml)

    def test_a_normalizer_asking_for_a_cursor_stream_is_refused(self) -> None:
        toml = NORMALIZER_TOML + '\n[declares]\nstreams = ["items"]\n'
        with pytest.raises(ManifestError, match="holds no cursor"):
            AddonManifest.parse(toml)

    def test_a_normalizer_without_an_output_contract_version_is_refused(self) -> None:
        toml = NORMALIZER_TOML.replace('output_contract_version = "0.1"\n', "")
        with pytest.raises(ManifestError, match="output_contract_version"):
            AddonManifest.parse(toml)

    def test_a_collector_declaring_an_output_contract_version_is_refused(self) -> None:
        toml = COLLECTOR_TOML.replace(
            'requires_contract = ">=1.0,<2.0"',
            'requires_contract = ">=1.0,<2.0"\noutput_contract_version = "0.1"',
        )
        with pytest.raises(ManifestError, match="only a normalizer"):
            AddonManifest.parse(toml)

    def test_an_importer_asking_for_a_host_is_refused(self) -> None:
        toml = COLLECTOR_TOML.replace('kind = "collector"', 'kind = "importer"')
        with pytest.raises(ManifestError, match="no network capability"):
            AddonManifest.parse(toml)


class TestConfigValidation:
    schema = (
        ConfigField(name="base_path", type="string", required=True),
        ConfigField(name="api_token", type="string", required=True, secret=True),
        ConfigField(name="page_size", type="integer", required=False),
        ConfigField(name="verify", type="boolean", required=False),
    )

    def test_valid_configuration_comes_back_without_the_secret_field(self) -> None:
        result = validate_config(
            self.schema, {"base_path": "/v1/items", "page_size": 50, "verify": True}
        )
        assert result == {"base_path": "/v1/items", "page_size": 50, "verify": True}
        assert "api_token" not in result

    def test_a_secret_field_offered_as_stored_configuration_is_refused(self) -> None:
        """The rule that keeps a token out of the source row.

        A caller reaching here with a token has already made the mistake. Refusing
        means it is not also persisted, which is what ``p0-security.md`` forbids.
        """
        with pytest.raises(ConfigValidationError) as caught:
            validate_config(self.schema, {"base_path": "/v1", "api_token": "s3cret"})
        assert caught.value.fields == ("api_token",)
        assert "must not be stored as configuration" in caught.value.summary
        # The refusal must not repeat the value it refused.
        assert "s3cret" not in caught.value.summary

    def test_a_missing_required_field_is_named(self) -> None:
        with pytest.raises(ConfigValidationError) as caught:
            validate_config(self.schema, {})
        assert caught.value.fields == ("base_path",)

    def test_an_undeclared_field_is_named(self) -> None:
        with pytest.raises(ConfigValidationError) as caught:
            validate_config(self.schema, {"base_path": "/v1", "surprise": 1})
        assert caught.value.fields == ("surprise",)

    def test_a_value_of_the_wrong_type_is_named(self) -> None:
        with pytest.raises(ConfigValidationError) as caught:
            validate_config(self.schema, {"base_path": "/v1", "page_size": "fifty"})
        assert caught.value.fields == ("page_size",)

    def test_a_boolean_is_not_accepted_where_an_integer_is_declared(self) -> None:
        """``True`` is an ``int`` in Python; a page size of ``True`` is a defect."""
        with pytest.raises(ConfigValidationError) as caught:
            validate_config(self.schema, {"base_path": "/v1", "page_size": True})
        assert caught.value.fields == ("page_size",)

    def test_every_problem_is_reported_at_once_rather_than_one_per_attempt(self) -> None:
        """An operator filling a form should see every bad field, not the first."""
        with pytest.raises(ConfigValidationError) as caught:
            validate_config(self.schema, {"page_size": "fifty", "surprise": 1})
        assert caught.value.fields == ("base_path", "page_size", "surprise")
