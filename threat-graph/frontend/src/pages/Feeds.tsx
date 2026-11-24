import { useCallback, useEffect, useState, type FormEvent } from "react";
import { feedsApi } from "../api";
import { useAuth } from "../auth";
import {
  Badge,
  EmptyState,
  ErrorBanner,
  Field,
  Loading,
  Modal,
  Notice,
  SectionHeader,
  formatDate,
  formatNumber,
} from "../components/UI";
import type { FeedConfig, FeedConfigCreate, FeedConfigUpdate, FeedPollResult, FeedType } from "../types";

const feedTypes: FeedType[] = ["stix", "taxii", "json", "csv", "log"];

export function Feeds() {
  const { canWrite, isAdmin } = useAuth();
  const [feeds, setFeeds] = useState<FeedConfig[]>([]);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<FeedConfig | null>(null);
  const [lastPoll, setLastPoll] = useState<FeedPollResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    feedsApi
      .list()
      .then(setFeeds)
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Unable to load feeds"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function toggle(feed: FeedConfig) {
    setBusy(true);
    setError(null);
    try {
      await feedsApi.update(feed.id, { enabled: !feed.enabled });
      load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  async function poll(feed: FeedConfig) {
    setBusy(true);
    setError(null);
    try {
      setLastPoll(await feedsApi.poll(feed.id));
      load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Feed poll failed");
    } finally {
      setBusy(false);
    }
  }

  async function pollAll() {
    setBusy(true);
    setError(null);
    try {
      const results = await feedsApi.pollEnabled();
      setLastPoll(results[0] ?? null);
      load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Feed poll failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(feed: FeedConfig) {
    if (!window.confirm(`Delete feed "${feed.name}"?`)) return;
    setBusy(true);
    setError(null);
    try {
      await feedsApi.remove(feed.id);
      load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-stack">
      <ErrorBanner message={error} onClose={() => setError(null)} />
      <SectionHeader
        title="Threat intelligence feeds"
        subtitle="Configure STIX, TAXII, JSON, CSV, or log feeds. Polled data flows through the same ingestion and graph pipeline."
        action={
          <div className="button-row">
            <button type="button" className="button button--secondary" onClick={pollAll} disabled={busy || !canWrite}>Poll enabled</button>
            <button type="button" className="button button--primary" onClick={() => setCreating(true)} disabled={!isAdmin}>Add feed</button>
          </div>
        }
      />
      {!isAdmin && <Notice>Feed configuration requires admin access. Analysts can poll configured feeds.</Notice>}

      {loading ? (
        <Loading label="Loading feeds…" />
      ) : feeds.length === 0 ? (
        <EmptyState title="No feeds configured" detail="Add a feed to pull external intelligence into ThreatGraph." />
      ) : (
        <section className="card table-card">
          <div className="table-wrap">
            <table>
              <thead><tr><th>Name</th><th>Type</th><th>URL</th><th>Enabled</th><th>Interval</th><th>Last polled</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>
                {feeds.map((feed) => (
                  <tr key={feed.id}>
                    <td><strong>{feed.name}</strong><span className="cell-sub">{feed.description ?? ""}</span></td>
                    <td><Badge>{feed.feed_type}</Badge></td>
                    <td className="mono truncate">{feed.url}</td>
                    <td><Badge tone={feed.enabled ? "success" : "neutral"}>{feed.enabled ? "enabled" : "disabled"}</Badge></td>
                    <td>{feed.poll_interval_minutes}m</td>
                    <td>{formatDate(feed.last_polled_at)}</td>
                    <td>
                      <Badge tone={feed.last_status === "completed" ? "success" : feed.last_status ? "error" : "neutral"}>
                        {feed.last_status ?? "never"}
                      </Badge>
                      {feed.last_error && <span className="cell-sub cell-sub--error">{feed.last_error}</span>}
                    </td>
                    <td>
                      <div className="row-actions">
                        <button type="button" className="button button--tiny" onClick={() => toggle(feed)} disabled={busy || !isAdmin}>{feed.enabled ? "Disable" : "Enable"}</button>
                        <button type="button" className="button button--tiny" onClick={() => poll(feed)} disabled={busy || !canWrite}>Poll</button>
                        <button type="button" className="button button--tiny" onClick={() => setEditing(feed)} disabled={!isAdmin}>Edit</button>
                        {isAdmin && <button type="button" className="button button--tiny button--danger" onClick={() => remove(feed)} disabled={busy}>Delete</button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {lastPoll && (
        <section className="card">
          <SectionHeader title="Last feed poll" subtitle={`${lastPoll.feed_name} · job ${lastPoll.job_id}`} />
          <div className="result-grid">
            <div className="result-tile"><strong>{formatNumber(lastPoll.total_records)}</strong><span>records</span></div>
            <div className="result-tile"><strong>{formatNumber(lastPoll.imported_indicators)}</strong><span>indicators</span></div>
            <div className="result-tile"><strong>{formatNumber(lastPoll.imported_events)}</strong><span>events</span></div>
            <div className="result-tile"><strong>{formatNumber(lastPoll.rejected_records)}</strong><span>rejected</span></div>
            <div className="result-tile"><strong>{lastPoll.relationships.observed_edges}</strong><span>observed edges</span></div>
            <div className="result-tile"><strong>{lastPoll.relationships.inferred_edges}</strong><span>inferred edges</span></div>
          </div>
        </section>
      )}

      {creating && <FeedModal title="Add feed" onClose={() => setCreating(false)} onSaved={() => { setCreating(false); load(); }} />}
      {editing && (
        <FeedModal
          title={`Edit ${editing.name}`}
          feed={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load(); }}
        />
      )}
    </div>
  );
}

function FeedModal({ title, feed, onClose, onSaved }: { title: string; feed?: FeedConfig; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState<FeedConfigCreate>({
    name: feed?.name ?? "",
    description: feed?.description ?? "",
    feed_type: feed?.feed_type ?? "stix",
    url: feed?.url ?? "",
    collection_id: feed?.collection_id ?? "",
    auth_header_env: feed?.auth_header_env ?? "",
    enabled: feed?.enabled ?? false,
    poll_interval_minutes: feed?.poll_interval_minutes ?? 60,
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const payload: FeedConfigUpdate = {
      description: form.description,
      url: form.url,
      collection_id: form.collection_id,
      auth_header_env: form.auth_header_env,
      enabled: form.enabled,
      poll_interval_minutes: form.poll_interval_minutes,
    };
    try {
      if (feed) {
        await feedsApi.update(feed.id, payload);
      } else {
        await feedsApi.create(form);
      }
      onSaved();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <form className="form-stack" onSubmit={submit}>
        <ErrorBanner message={error} onClose={() => setError(null)} />
        <div className="field-row">
          <Field label="Name">
            <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} minLength={2} required disabled={Boolean(feed)} />
          </Field>
          <Field label="Feed type">
            <select value={form.feed_type} onChange={(event) => setForm({ ...form, feed_type: event.target.value as FeedType })} disabled={Boolean(feed)}>
              {feedTypes.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </Field>
        </div>
        <Field label="URL">
          <input value={form.url} onChange={(event) => setForm({ ...form, url: event.target.value })} minLength={8} required />
        </Field>
        <Field label="Description">
          <textarea rows={2} value={form.description ?? ""} onChange={(event) => setForm({ ...form, description: event.target.value })} />
        </Field>
        <div className="field-row">
          <Field label="TAXII collection" hint="Optional">
            <input value={form.collection_id ?? ""} onChange={(event) => setForm({ ...form, collection_id: event.target.value })} />
          </Field>
          <Field label="Auth header env" hint="Environment variable name, not the secret">
            <input value={form.auth_header_env ?? ""} onChange={(event) => setForm({ ...form, auth_header_env: event.target.value })} />
          </Field>
        </div>
        <div className="field-row">
          <Field label="Poll interval (minutes)">
            <input type="number" min={5} max={10080} value={form.poll_interval_minutes ?? 60} onChange={(event) => setForm({ ...form, poll_interval_minutes: Number(event.target.value) })} />
          </Field>
          <label className="checkbox checkbox--aligned">
            <input type="checkbox" checked={form.enabled ?? false} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} />
            <span>Enabled</span>
          </label>
        </div>
        <div className="modal-actions">
          <button type="button" className="button button--ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="button button--primary" disabled={busy}>{busy ? "Saving…" : "Save feed"}</button>
        </div>
      </form>
    </Modal>
  );
}
