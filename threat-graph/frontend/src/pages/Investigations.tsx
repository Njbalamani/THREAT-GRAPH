import { useCallback, useEffect, useState, type FormEvent } from "react";
import { indicatorsApi, investigationsApi } from "../api";
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
} from "../components/UI";
import type {
  Indicator,
  Investigation,
  InvestigationCreate,
  InvestigationDetail,
  InvestigationStatus,
  Priority,
} from "../types";

const statuses: InvestigationStatus[] = ["open", "in_progress", "resolved", "closed"];
const priorities: Priority[] = ["low", "medium", "high", "critical"];

export function Investigations() {
  const { canWrite } = useAuth();
  const [cases, setCases] = useState<Investigation[]>([]);
  const [detail, setDetail] = useState<InvestigationDetail | null>(null);
  const [creating, setCreating] = useState(false);
  const [linking, setLinking] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    investigationsApi
      .list()
      .then((items) => {
        setCases(items);
        setDetail((current) => (current && items.some((item) => item.id === current.investigation.id) ? current : null));
      })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Unable to load investigations"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openCase = useCallback((id: string) => {
    setBusy(true);
    setError(null);
    investigationsApi
      .get(id)
      .then(setDetail)
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Unable to open case"))
      .finally(() => setBusy(false));
  }, []);

  useEffect(() => {
    if (cases.length > 0 && !detail) {
      openCase(cases[0].id);
    }
  }, [cases, detail, openCase]);

  async function updateField(field: "status" | "priority", value: string) {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await investigationsApi.update(detail.investigation.id, { [field]: value });
      setDetail({ ...detail, investigation: updated });
      setCases((items) => items.map((item) => (item.id === updated.id ? updated : item)));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  async function addNote(event: FormEvent) {
    event.preventDefault();
    if (!detail || note.trim().length === 0) return;
    setBusy(true);
    setError(null);
    try {
      await investigationsApi.addNote(detail.investigation.id, note.trim());
      setNote("");
      setDetail(await investigationsApi.get(detail.investigation.id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to add note");
    } finally {
      setBusy(false);
    }
  }

  async function removeCase(target: Investigation) {
    if (!window.confirm(`Delete case "${target.title}"?`)) return;
    setBusy(true);
    setError(null);
    try {
      await investigationsApi.remove(target.id);
      setDetail(null);
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
        title="Investigation workspace"
        subtitle="Track cases, link confirmed evidence, and preserve an analyst timeline."
        action={<button type="button" className="button button--primary" onClick={() => setCreating(true)} disabled={!canWrite}>New case</button>}
      />
      {!canWrite && <Notice>Analyst or admin access is required to change investigation cases.</Notice>}

      <div className="investigation-layout">
        <section className="card case-list">
          <h3>Cases</h3>
          {loading ? (
            <Loading label="Loading cases…" />
          ) : cases.length === 0 ? (
            <EmptyState title="No cases yet" detail="Create a case to begin an investigation." />
          ) : (
            <div className="list">
              {cases.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  className={`case-item ${detail?.investigation.id === item.id ? "case-item--active" : ""}`}
                  onClick={() => openCase(item.id)}
                >
                  <strong>{item.title}</strong>
                  <span>{formatDate(item.updated_at)}</span>
                  <div className="case-item__badges">
                    <Badge tone={item.status}>{item.status.replace("_", " ")}</Badge>
                    <Badge tone={item.priority}>{item.priority}</Badge>
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="card case-detail">
          {busy && !detail ? (
            <Loading label="Opening case…" />
          ) : !detail ? (
            <EmptyState title="Select or create a case" detail="Case details, linked indicators, notes, and timeline appear here." />
          ) : (
            <div className="case-body">
              <div className="case-header">
                <div>
                  <h3>{detail.investigation.title}</h3>
                  <p>{detail.investigation.description ?? "No description provided."}</p>
                  <span>Created {formatDate(detail.investigation.created_at)}</span>
                </div>
                {canWrite && <button type="button" className="button button--tiny button--danger" onClick={() => removeCase(detail.investigation)}>Delete</button>}
              </div>

              <div className="field-row">
                <Field label="Status">
                  <select value={detail.investigation.status} onChange={(event) => updateField("status", event.target.value)} disabled={!canWrite || busy}>
                    {statuses.map((status) => <option key={status} value={status}>{status.replace("_", " ")}</option>)}
                  </select>
                </Field>
                <Field label="Priority">
                  <select value={detail.investigation.priority} onChange={(event) => updateField("priority", event.target.value)} disabled={!canWrite || busy}>
                    {priorities.map((priority) => <option key={priority} value={priority}>{priority}</option>)}
                  </select>
                </Field>
              </div>

              <div className="case-section-head">
                <h4>Linked indicators</h4>
                <button type="button" className="button button--tiny" onClick={() => setLinking(true)} disabled={!canWrite}>Link indicator</button>
              </div>
              {detail.indicators.length === 0 ? (
                <EmptyState title="No linked indicators" detail="Attach indicators to build the case evidence set." />
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Value</th><th>Type</th><th>Severity</th><th>Status</th><th>Source</th></tr></thead>
                    <tbody>
                      {detail.indicators.map((indicator) => (
                        <tr key={indicator.id}>
                          <td className="mono">{indicator.value}</td>
                          <td><Badge>{indicator.type}</Badge></td>
                          <td><SeverityBadge severity={indicator.severity} /></td>
                          <td><Badge tone={indicator.is_confirmed ? "success" : "warning"}>{indicator.is_confirmed ? "confirmed" : "unconfirmed"}</Badge></td>
                          <td>{indicator.source}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="case-notes">
                <div className="case-section-head"><h4>Analyst notes</h4></div>
                <form className="note-form" onSubmit={addNote}>
                  <textarea rows={3} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Record observations, evidence, and next steps…" disabled={!canWrite} />
                  <button type="submit" className="button button--secondary" disabled={!canWrite || busy || note.trim().length === 0}>Add note</button>
                </form>
                <div className="list">
                  {detail.notes.length === 0 ? (
                    <EmptyState title="No notes yet" />
                  ) : (
                    detail.notes.map((item) => (
                      <div className="list-row" key={item.id}>
                        <div><strong>{item.content}</strong><span>{formatDate(item.created_at)}</span></div>
                        <Badge>{item.author_id ? "signed" : "system"}</Badge>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="case-section-head"><h4>Timeline</h4></div>
              {detail.timeline.length === 0 ? (
                <EmptyState title="No timeline events" />
              ) : (
                <div className="timeline">
                  {detail.timeline.map((event) => (
                    <div className="timeline__item" key={event.id}>
                      <span className="timeline__dot" />
                      <div>
                        <strong>{event.title}</strong>
                        <p>{event.description ?? ""}</p>
                        <span>{formatDate(event.timestamp)} · {event.source ?? event.kind}</span>
                      </div>
                      {event.severity && <SeverityBadge severity={event.severity} />}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      {creating && (
        <CreateCaseModal
          onClose={() => setCreating(false)}
          onSaved={(created) => {
            setCreating(false);
            setDetail(created);
            load();
          }}
        />
      )}
      {linking && detail && <LinkIndicatorModal caseId={detail.investigation.id} onClose={() => setLinking(false)} onSaved={(next) => { setDetail(next); setLinking(false); }} />}
    </div>
  );
}

function CreateCaseModal({ onClose, onSaved }: { onClose: () => void; onSaved: (detail: InvestigationDetail) => void }) {
  const [form, setForm] = useState<InvestigationCreate>({ title: "", description: "", priority: "medium" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSaved(await investigationsApi.create({ ...form, title: form.title.trim() }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="New investigation" onClose={onClose}>
      <form className="form-stack" onSubmit={submit}>
        <ErrorBanner message={error} onClose={() => setError(null)} />
        <Field label="Title">
          <input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} minLength={3} required />
        </Field>
        <Field label="Priority">
          <select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value as Priority })}>
            {priorities.map((priority) => <option key={priority} value={priority}>{priority}</option>)}
          </select>
        </Field>
        <Field label="Description">
          <textarea rows={4} value={form.description ?? ""} onChange={(event) => setForm({ ...form, description: event.target.value })} />
        </Field>
        <div className="modal-actions">
          <button type="button" className="button button--ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="button button--primary" disabled={busy}>{busy ? "Creating…" : "Create case"}</button>
        </div>
      </form>
    </Modal>
  );
}

function LinkIndicatorModal({ caseId, onClose, onSaved }: { caseId: string; onClose: () => void; onSaved: (detail: InvestigationDetail) => void }) {
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    indicatorsApi.list({ limit: 500 }).then(setIndicators).catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Unable to load indicators"));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      onSaved(await investigationsApi.linkIndicator(caseId, selected));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to link indicator");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Link indicator" onClose={onClose}>
      <form className="form-stack" onSubmit={submit}>
        <ErrorBanner message={error} onClose={() => setError(null)} />
        <Field label="Indicator">
          <select value={selected} onChange={(event) => setSelected(event.target.value)} required>
            <option value="">Choose an indicator…</option>
            {indicators.map((indicator) => <option key={indicator.id} value={indicator.id}>{indicator.type} · {indicator.value}</option>)}
          </select>
        </Field>
        <div className="modal-actions">
          <button type="button" className="button button--ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="button button--primary" disabled={busy || !selected}>{busy ? "Linking…" : "Link indicator"}</button>
        </div>
      </form>
    </Modal>
  );
}
