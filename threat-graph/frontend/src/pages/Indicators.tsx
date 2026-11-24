import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { indicatorsApi } from "../api";
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
  SeverityBadge,
  formatDate,
  formatPercent,
} from "../components/UI";
import type { Indicator, IndicatorCreate, IndicatorType, Severity } from "../types";

const indicatorTypes: IndicatorType[] = ["ip", "domain", "hash", "url", "email"];
const severities: Severity[] = ["low", "medium", "high", "critical"];

export function Indicators() {
  const { canWrite, isAdmin } = useAuth();
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Indicator | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    indicatorsApi
      .list({
        indicator_type: typeFilter || undefined,
        severity: severityFilter || undefined,
        search: search.trim() || undefined,
        limit: 300,
      })
      .then(setIndicators)
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Unable to load indicators"))
      .finally(() => setLoading(false));
  }, [typeFilter, severityFilter, search]);

  useEffect(() => {
    load();
  }, [load]);

  async function remove(indicator: Indicator) {
    if (!window.confirm(`Delete ${indicator.value}?`)) return;
    setBusy(true);
    setError(null);
    try {
      await indicatorsApi.remove(indicator.id);
      load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  const stats = useMemo(() => ({
    confirmed: indicators.filter((item) => item.is_confirmed).length,
    high: indicators.filter((item) => item.severity === "high" || item.severity === "critical").length,
  }), [indicators]);

  return (
    <div className="page-stack">
      <ErrorBanner message={error} onClose={() => setError(null)} />
      <SectionHeader
        title="Indicator registry"
        subtitle="Deduplicated indicators extracted from analyst input, datasets, and intelligence feeds."
        action={
          <button type="button" className="button button--primary" onClick={() => setCreating(true)} disabled={!canWrite}>
            Add indicator
          </button>
        }
      />
      {!canWrite && <Notice>Analyst or admin access is required to modify indicators.</Notice>}

      <div className="filter-bar">
        <label className="field field--inline">
          <span className="field__label">Type</span>
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
            <option value="">All</option>
            {indicatorTypes.map((type) => <option key={type} value={type}>{type}</option>)}
          </select>
        </label>
        <label className="field field--inline">
          <span className="field__label">Severity</span>
          <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
            <option value="">All</option>
            {severities.map((severity) => <option key={severity} value={severity}>{severity}</option>)}
          </select>
        </label>
        <label className="field field--inline field--grow">
          <span className="field__label">Search</span>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="IP, domain, hash, URL…" />
        </label>
        <button type="button" className="button button--secondary" onClick={load}>Apply filters</button>
      </div>

      <div className="inline-stats">
        <Badge tone="info">{indicators.length} loaded</Badge>
        <Badge tone="critical">{stats.high} high / critical</Badge>
        <Badge tone="success">{stats.confirmed} confirmed</Badge>
      </div>

      {loading ? (
        <Loading label="Loading indicators…" />
      ) : indicators.length === 0 ? (
        <EmptyState title="No indicators match" detail="Adjust filters or ingest new intelligence." />
      ) : (
        <section className="card table-card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Value</th><th>Type</th><th>Severity</th><th>Confidence</th><th>Status</th><th>Source</th><th>Tags</th><th>Last seen</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {indicators.map((indicator) => (
                  <tr key={indicator.id}>
                    <td className="mono indicator-value">{indicator.value}</td>
                    <td><Badge>{indicator.type}</Badge></td>
                    <td><SeverityBadge severity={indicator.severity} /></td>
                    <td>{formatPercent(indicator.confidence)}</td>
                    <td><Badge tone={indicator.is_confirmed ? "success" : "warning"}>{indicator.is_confirmed ? "confirmed" : "unconfirmed"}</Badge></td>
                    <td>{indicator.source}</td>
                    <td>{indicator.tags.length ? indicator.tags.map((tag) => <Badge key={tag}>{tag}</Badge>) : "—"}</td>
                    <td>{formatDate(indicator.last_seen)}</td>
                    <td>
                      <div className="row-actions">
                        <button type="button" className="button button--tiny" onClick={() => setEditing(indicator)} disabled={!canWrite}>Edit</button>
                        {isAdmin && <button type="button" className="button button--tiny button--danger" onClick={() => remove(indicator)} disabled={busy}>Delete</button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {creating && <CreateIndicatorModal onClose={() => setCreating(false)} onSaved={() => { setCreating(false); load(); }} />}
      {editing && <EditIndicatorModal indicator={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
}

function CreateIndicatorModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState<IndicatorCreate>({
    type: "ip",
    value: "",
    severity: "medium",
    confidence: 0.7,
    source: "manual",
    description: "",
    tags: [],
  });
  const [tags, setTags] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await indicatorsApi.create({
        ...form,
        value: form.value.trim(),
        tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      });
      onSaved();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Add indicator" onClose={onClose}>
      <form className="form-stack" onSubmit={submit}>
        <ErrorBanner message={error} onClose={() => setError(null)} />
        <div className="field-row">
          <Field label="Type">
            <select value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value as IndicatorType })}>
              {indicatorTypes.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </Field>
          <Field label="Severity">
            <select value={form.severity} onChange={(event) => setForm({ ...form, severity: event.target.value as Severity })}>
              {severities.map((severity) => <option key={severity} value={severity}>{severity}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Value">
          <input value={form.value} onChange={(event) => setForm({ ...form, value: event.target.value })} required />
        </Field>
        <div className="field-row">
          <Field label="Confidence">
            <input type="number" step="0.05" min="0" max="1" value={form.confidence ?? 0.5} onChange={(event) => setForm({ ...form, confidence: Number(event.target.value) })} />
          </Field>
          <Field label="Source">
            <input value={form.source ?? "manual"} onChange={(event) => setForm({ ...form, source: event.target.value })} />
          </Field>
        </div>
        <Field label="Tags" hint="Comma-separated">
          <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="phishing, credential-access" />
        </Field>
        <Field label="Description">
          <textarea rows={3} value={form.description ?? ""} onChange={(event) => setForm({ ...form, description: event.target.value })} />
        </Field>
        <label className="checkbox">
          <input type="checkbox" checked={form.is_confirmed ?? false} onChange={(event) => setForm({ ...form, is_confirmed: event.target.checked })} />
          <span>Verified by an analyst</span>
        </label>
        <div className="modal-actions">
          <button type="button" className="button button--ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="button button--primary" disabled={busy}>{busy ? "Saving…" : "Create indicator"}</button>
        </div>
      </form>
    </Modal>
  );
}

function EditIndicatorModal({ indicator, onClose, onSaved }: { indicator: Indicator; onClose: () => void; onSaved: () => void }) {
  const [severity, setSeverity] = useState<Severity>(indicator.severity);
  const [confidence, setConfidence] = useState(indicator.confidence);
  const [description, setDescription] = useState(indicator.description ?? "");
  const [tags, setTags] = useState(indicator.tags.join(", "));
  const [confirmed, setConfirmed] = useState(indicator.is_confirmed);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await indicatorsApi.update(indicator.id, {
        severity,
        confidence: Number(confidence),
        description,
        tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
        is_confirmed: confirmed,
      });
      onSaved();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`Edit ${indicator.value}`} onClose={onClose}>
      <form className="form-stack" onSubmit={submit}>
        <ErrorBanner message={error} onClose={() => setError(null)} />
        <div className="field-row">
          <Field label="Severity">
            <select value={severity} onChange={(event) => setSeverity(event.target.value as Severity)}>
              {severities.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </Field>
          <Field label="Confidence">
            <input type="number" step="0.05" min="0" max="1" value={confidence} onChange={(event) => setConfidence(Number(event.target.value))} />
          </Field>
        </div>
        <Field label="Tags">
          <input value={tags} onChange={(event) => setTags(event.target.value)} />
        </Field>
        <Field label="Description">
          <textarea rows={4} value={description} onChange={(event) => setDescription(event.target.value)} />
        </Field>
        <label className="checkbox">
          <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
          <span>Verified by an analyst</span>
        </label>
        <div className="modal-actions">
          <button type="button" className="button button--ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="button button--primary" disabled={busy}>{busy ? "Saving…" : "Save changes"}</button>
        </div>
      </form>
    </Modal>
  );
}
