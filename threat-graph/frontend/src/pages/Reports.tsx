import { useEffect, useState, type FormEvent } from "react";
import { indicatorsApi, investigationsApi, reportsApi } from "../api";
import {
  EmptyState,
  ErrorBanner,
  Field,
  Notice,
  SectionHeader,
  formatDate,
} from "../components/UI";
import type { Indicator, Investigation, Severity } from "../types";

const severities: Severity[] = ["low", "medium", "high", "critical"];

export function Reports() {
  const [title, setTitle] = useState("ThreatGraph Intelligence Report");
  const [investigationId, setInvestigationId] = useState("");
  const [minimumSeverity, setMinimumSeverity] = useState<Severity>("low");
  const [includePredictions, setIncludePredictions] = useState(true);
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>([]);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    indicatorsApi.list({ limit: 500 }).then(setIndicators).catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Unable to load indicators"));
    investigationsApi.list().then(setInvestigations).catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Unable to load cases"));
  }, []);

  async function generate(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await reportsApi.pdf({
        title: title.trim(),
        investigation_id: investigationId || null,
        indicator_ids: selectedIndicators,
        include_predictions: includePredictions,
        minimum_severity: minimumSeverity,
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Report generation failed");
    } finally {
      setBusy(false);
    }
  }

  async function exportFile(action: () => Promise<void>, label: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `${label} export failed`);
    } finally {
      setBusy(false);
    }
  }

  function toggleIndicator(id: string) {
    setSelectedIndicators((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  return (
    <div className="page-stack">
      <ErrorBanner message={error} onClose={() => setError(null)} />
      <Notice>Generated reports and exports are downloaded with your authenticated session.</Notice>
      <SectionHeader title="Reports & exports" subtitle="Produce analyst-ready PDF reports and machine-readable datasets." />

      <div className="two-column">
        <form className="card form-card" onSubmit={generate}>
          <h3>PDF intelligence report</h3>
          <p className="muted">Include confirmed evidence and clearly labelled advisory predictions.</p>
          <Field label="Report title">
            <input value={title} onChange={(event) => setTitle(event.target.value)} minLength={3} required />
          </Field>
          <Field label="Investigation">
            <select value={investigationId} onChange={(event) => setInvestigationId(event.target.value)}>
              <option value="">No specific case</option>
              {investigations.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
            </select>
          </Field>
          <div className="field-row">
            <Field label="Minimum severity">
              <select value={minimumSeverity} onChange={(event) => setMinimumSeverity(event.target.value as Severity)}>
                {severities.map((severity) => <option key={severity} value={severity}>{severity}</option>)}
              </select>
            </Field>
            <label className="checkbox checkbox--aligned">
              <input type="checkbox" checked={includePredictions} onChange={(event) => setIncludePredictions(event.target.checked)} />
              <span>Include predictions</span>
            </label>
          </div>
          <Field label="Specific indicators" hint="Optional; leave empty to include all matching indicators">
            <div className="indicator-picker">
              {indicators.length === 0 ? (
                <EmptyState title="No indicators available" />
              ) : (
                indicators.slice(0, 40).map((indicator) => (
                  <label key={indicator.id} className="picker-item">
                    <input type="checkbox" checked={selectedIndicators.includes(indicator.id)} onChange={() => toggleIndicator(indicator.id)} />
                    <span className="mono">{indicator.value}</span>
                  </label>
                ))
              )}
            </div>
          </Field>
          <button type="submit" className="button button--primary" disabled={busy}>{busy ? "Generating…" : "Generate PDF report"}</button>
        </form>

        <section className="card form-card">
          <h3>Dataset exports</h3>
          <p className="muted">Download raw data for offline analysis or pipeline integration.</p>
          <div className="export-grid">
            <button type="button" className="button button--secondary" disabled={busy} onClick={() => exportFile(reportsApi.indicatorsCsv, "Indicators CSV")}>Indicators CSV</button>
            <button type="button" className="button button--secondary" disabled={busy} onClick={() => exportFile(reportsApi.relationshipsCsv, "Relationships CSV")}>Relationships CSV</button>
            <button type="button" className="button button--secondary" disabled={busy} onClick={() => exportFile(reportsApi.graphJson, "Graph JSON")}>Graph JSON</button>
            <button type="button" className="button button--secondary" disabled={busy} onClick={() => exportFile(reportsApi.graphGraphml, "GraphML")}>GraphML</button>
          </div>
          <div className="detail-stack">
            <div className="detail-row"><span>Indicators loaded</span><span>{indicators.length}</span></div>
            <div className="detail-row"><span>Cases loaded</span><span>{investigations.length}</span></div>
            <div className="detail-row"><span>Selected indicators</span><span>{selectedIndicators.length}</span></div>
            {investigations.length > 0 && <div className="detail-row"><span>Latest case</span><span>{formatDate(investigations[0].updated_at)}</span></div>}
          </div>
        </section>
      </div>
    </div>
  );
}
