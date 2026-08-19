// The domain screens, as pure functions of API data.
//
// Same rule as `view.tsx` and for the same reason: nothing here fetches, holds state,
// or reads a clock, so `src/domain-text.tsx` can render these from a frozen set of
// API responses and hand the visible text to a pytest assertion. A screen reachable
// only by driving a browser can only be checked by a human with a screenshot.
//
// **Field names are copied from the API, never coined.** `source_view`,
// `snapshot_view`, and `result_view` in `addon_host/api.py` are where every name
// below comes from.
//
// **What these screens are for.** The P0-B operator's loop is four acts, and each has
// exactly one control: collect from a registered source, seal what was collected,
// normalize a sealed snapshot, read the results. `project-state.md` §4 and DP-019 D6
// require the second and third to be *separate* deliberate acts — collection never
// starts normalization — and two buttons is how that reads on a screen. One button
// that did both would be the rule quietly broken.

import type { JSX } from "react";
import type {
  CredentialPart,
  NormalizedResult,
  OutboundProfile,
  RawSummary,
  Snapshot,
  Source,
} from "./api";
import { shortId, shown } from "./view";

/** How a value that is null, absent, or empty reads on screen. Matches `view.tsx`. */
const ABSENT = "—";

export function SourceTable({
  sources,
  raw,
  selectedId,
  onSelect,
  onCollect,
  onSeal,
}: {
  sources: Source[];
  raw: Record<string, RawSummary>;
  selectedId: string | null;
  onSelect: (sourceId: string) => void;
  onCollect: (sourceId: string) => void;
  onSeal: (sourceId: string) => void;
}): JSX.Element {
  if (sources.length === 0) {
    return (
      <p className="empty">
        No source is registered. Nothing can be collected until one is: the platform
        takes a registered source_id and never a URL.
      </p>
    );
  }
  return (
    <table className="table">
      <thead>
        <tr>
          <th scope="col">source_id</th>
          <th scope="col">kind</th>
          <th scope="col">addon_id</th>
          <th scope="col">enabled</th>
          <th scope="col">data_class</th>
          <th scope="col">envelopes</th>
          <th scope="col">items</th>
          <th scope="col">actions</th>
        </tr>
      </thead>
      <tbody>
        {sources.map((source) => {
          const collected = raw[source.source_id];
          const isCollector = source.kind === "collector";
          return (
            <tr
              key={source.source_id}
              className={source.source_id === selectedId ? "row selected" : "row"}
            >
              <td>
                <button type="button" className="link" onClick={() => onSelect(source.source_id)}>
                  {source.source_id}
                </button>
              </td>
              <td>{source.kind}</td>
              <td>{source.addon_id}</td>
              <td>{source.enabled ? "yes" : "no"}</td>
              <td>{source.data_class}</td>
              <td>{collected === undefined ? ABSENT : collected.envelope_count}</td>
              <td>{collected === undefined ? ABSENT : collected.item_count}</td>
              <td>
                {isCollector ? (
                  <>
                    <button
                      type="button"
                      disabled={!source.enabled}
                      onClick={() => onCollect(source.source_id)}
                    >
                      collect
                    </button>{" "}
                    <button
                      type="button"
                      disabled={!source.enabled}
                      onClick={() => onSeal(source.source_id)}
                    >
                      seal snapshot
                    </button>
                  </>
                ) : (
                  <span className="note">runs on a snapshot</span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/**
 * One source in full, including the outbound grant.
 *
 * The credential rows show a header and a **key name**. That is the whole of what
 * `secret-setup.md` permits on a screen and the whole of what an operator needs: it
 * says which key to put in the store. No value is fetched, so none can be shown.
 */
export function SourceDetail({ source }: { source: Source }): JSX.Element {
  return (
    <div className="detail">
      <dl className="fields">
        <Field label="source_id" value={source.source_id} />
        <Field label="addon" value={`${source.addon_id}@${source.addon_version}`} />
        <Field label="kind" value={source.kind} />
        <Field label="data_class" value={source.data_class} />
        <Field label="enabled" value={source.enabled ? "yes" : "no"} />
        <Field label="config" value={JSON.stringify(source.config)} />
        <Field label="credential_ref" value={shown(source.credential_ref)} />
      </dl>
      {source.outbound_profile === null ? (
        <p className="note">
          This source has no outbound profile, so it opens no connection. A normalizer
          is required to have none.
        </p>
      ) : (
        <ProfileDetail profile={source.outbound_profile} />
      )}
    </div>
  );
}

function ProfileDetail({ profile }: { profile: OutboundProfile }): JSX.Element {
  const endpoints = Object.entries(profile.endpoints);
  return (
    <div className="profile">
      <h4>approved outbound grant</h4>
      <dl className="fields">
        <Field label="hosts" value={profile.hosts.join(", ") || ABSENT} />
        <Field label="port" value={String(profile.port)} />
        <Field label="allow_loopback" value={profile.allow_loopback ? "yes" : "no"} />
      </dl>
      <table className="table">
        <thead>
          <tr>
            <th scope="col">endpoint</th>
            <th scope="col">method</th>
            <th scope="col">path</th>
          </tr>
        </thead>
        <tbody>
          {endpoints.map(([name, endpoint]) => (
            <tr key={name} className="row">
              <td>{name}</td>
              <td>{endpoint.method}</td>
              <td>{endpoint.path}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <CredentialTable parts={profile.credentials} />
      <dl className="fields">
        {Object.entries(profile.limits).map(([name, value]) => (
          <Field key={name} label={name} value={String(value)} />
        ))}
      </dl>
    </div>
  );
}

function CredentialTable({ parts }: { parts: CredentialPart[] }): JSX.Element {
  if (parts.length === 0) {
    return <p className="note">This source sends no credential.</p>;
  }
  return (
    <table className="table">
      <thead>
        <tr>
          <th scope="col">header</th>
          <th scope="col">secret store key</th>
        </tr>
      </thead>
      <tbody>
        {parts.map((part) => (
          <tr key={part.header} className="row">
            <td>{part.header}</td>
            <td>{part.ref}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * Sealed snapshots, with whether each still matches what was sealed.
 *
 * `verifies` is shown as its own column rather than folded into a status word. A
 * screen that said only "sealed" would make a tampered input look ready to run, and
 * `problems` is printed in full because "the manifest digest differs" and "member 3
 * was edited" need different operator actions.
 */
export function SnapshotTable({
  snapshots,
  normalizers,
  selectedId,
  onSelect,
  onNormalize,
}: {
  snapshots: Snapshot[];
  normalizers: Source[];
  selectedId: string | null;
  onSelect: (snapshotId: string) => void;
  onNormalize: (snapshotId: string, normalizerSourceId: string) => void;
}): JSX.Element {
  if (snapshots.length === 0) {
    return (
      <p className="empty">
        No snapshot is sealed. A normalizer consumes a sealed snapshot and nothing
        else, so sealing is the step between collecting and normalizing.
      </p>
    );
  }
  return (
    <table className="table">
      <thead>
        <tr>
          <th scope="col">snapshot_id</th>
          <th scope="col">source_id</th>
          <th scope="col">items</th>
          <th scope="col">verifies</th>
          <th scope="col">sealed_at</th>
          <th scope="col">normalize with</th>
        </tr>
      </thead>
      <tbody>
        {snapshots.map((snapshot) => (
          <tr
            key={snapshot.snapshot_id}
            className={snapshot.snapshot_id === selectedId ? "row selected" : "row"}
          >
            <td>
              <button
                type="button"
                className="link"
                onClick={() => onSelect(snapshot.snapshot_id)}
              >
                {shortId(snapshot.snapshot_id)}
              </button>
            </td>
            <td>{snapshot.source_id}</td>
            <td>{snapshot.item_count}</td>
            <td>
              {snapshot.verifies ? "yes" : `no — ${snapshot.problems.join("; ")}`}
            </td>
            <td>{shown(snapshot.sealed_at)}</td>
            <td>
              {normalizers.length === 0 ? (
                <span className="note">no normalizer is registered</span>
              ) : (
                normalizers.map((normalizer) => (
                  <button
                    key={normalizer.source_id}
                    type="button"
                    disabled={!snapshot.verifies || !normalizer.enabled}
                    onClick={() => onNormalize(snapshot.snapshot_id, normalizer.source_id)}
                  >
                    {normalizer.source_id}
                  </button>
                ))
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * The normalized records of one snapshot.
 *
 * Both version axes are columns, because DP-019 D3 makes results coexist rather than
 * replace: two normalizer versions over one snapshot are two sets of rows, and a
 * reader comparing them needs to see which is which. `source_item_key` is a column
 * for the same reason it is a `not null` column in the table — it is the link back to
 * the sealed bytes, and a result that cannot be traced is an interpretation nobody
 * can check.
 */
export function ResultTable({ results }: { results: NormalizedResult[] }): JSX.Element {
  if (results.length === 0) {
    return (
      <p className="empty">
        This snapshot has no normalized result yet. Normalization is started
        explicitly; collecting does not begin it.
      </p>
    );
  }
  return (
    <table className="table">
      <thead>
        <tr>
          <th scope="col">source_item_key</th>
          <th scope="col">title</th>
          <th scope="col">published_at</th>
          <th scope="col">author</th>
          <th scope="col">schema</th>
          <th scope="col">normalizer</th>
        </tr>
      </thead>
      <tbody>
        {results.map((result) => (
          <tr key={result.id} className="row">
            <td className="key">{result.source_item_key}</td>
            <td>{field(result, "title")}</td>
            <td>{field(result, "published_at")}</td>
            <td>{field(result, "author")}</td>
            <td>{field(result, "schema_version")}</td>
            <td>
              {result.addon_id}@{result.addon_version} · out{" "}
              {result.output_contract_version}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * One field of a normalized body, as text.
 *
 * `body` is `Record<string, unknown>` because Schema 0.x is expected to move
 * (OQ-003), so a screen that destructured it into named properties would need a
 * change every time the schema did. Reading by name and rendering whatever is there
 * means a new field appears as soon as the normalizer emits it and a removed one
 * reads as absent rather than as a crash.
 */
function field(result: NormalizedResult, name: string): string {
  const value = result.body[name];
  if (value === null || value === undefined || value === "") {
    return ABSENT;
  }
  return typeof value === "string" ? value : JSON.stringify(value);
}

function Field({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="field">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
