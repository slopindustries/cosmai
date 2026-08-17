# Experimental Contracts

Everything here is unstable and may be replaced without migration during P0.

P0-A may create only source- and normalization-independent platform contracts for handler-neutral jobs, process lifecycle, platform operations, and platform security. It must not create acquisition, Raw, snapshot, normalization, source-policy, or source-credential contracts.

P0-B drafts those domain contracts after bounded source evidence and a provisional decision use exist. Exercise them with domain test doubles and then against the concrete collector, importer, and normalizer. A contract or passing test-double scenario is not evidence that the real integration works.

Experimental contracts must still include:

- an explicit experimental version;
- the Open Question or Decision Packet that motivated them;
- example valid and invalid payloads;
- semantics for missing and unknown values;
- source provenance and version fields where applicable;
- validation and error expectations.

Moving a contract out of this directory requires an accepted Decision Packet.

Use [CONTRACT-TEMPLATE.md](CONTRACT-TEMPLATE.md) and keep examples or machine-readable schema beside the completed contract.
