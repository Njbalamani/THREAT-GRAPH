import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
} from "chart.js";
import { Bar, Doughnut } from "react-chartjs-2";
import { dashboardApi } from "../api";
import {
  Badge,
  EmptyState,
  ErrorBanner,
  Loading,
  Notice,
  SectionHeader,
  SeverityBadge,
  StatCard,
  formatDate,
  formatNumber,
  formatPercent,
} from "../components/UI";
import type { DashboardSummary } from "../types";

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend);

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { labels: { color: "#cbd5e1", boxWidth: 12 } } },
  scales: {
    x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148,163,184,0.12)" } },
    y: { ticks: { color: "#94a3b8", precision: 0 }, grid: { color: "rgba(148,163,184,0.12)" } },
  },
};

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: "70%",
  plugins: { legend: { position: "bottom" as const, labels: { color: "#cbd5e1", boxWidth: 12 } } },
};

export function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);

  const load = useCallback(() => {
    setBusy(true);
    setError(null);
    dashboardApi
      .summary()
      .then(setSummary)
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Unable to load dashboard"))
      .finally(() => setBusy(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (busy && !summary) return <Loading label="Loading intelligence overview…" />;

  if (!summary) {
    return (
      <>
        <ErrorBanner message={error} onClose={() => setError(null)} />
        <EmptyState title="Dashboard unavailable" detail="Retry the request or verify the API connection." />
        <button type="button" className="button button--primary" onClick={load}>Retry</button>
      </>
    );
  }

  const severityLabels = ["low", "medium", "high", "critical"] as const;
  const severityValues = severityLabels.map((key) => summary.severity_distribution[key] ?? 0);
  const typeEntries = Object.entries(summary.indicator_types);
  const provenanceEntries = Object.entries(summary.relationship_provenance);

  return (
    <div className="page-stack">
      <ErrorBanner message={error} onClose={() => setError(null)} />
      <Notice>{summary.disclaimer}</Notice>

      <SectionHeader
        title="Intelligence overview"
        subtitle="Live counts from PostgreSQL, the relationship graph, and the ML model registry."
        action={
          <button type="button" className="button button--ghost" onClick={load}>
            Refresh
          </button>
        }
      />

      <div className="stat-grid">
        <StatCard label="Indicators" value={formatNumber(summary.totals.indicators)} hint="Deduplicated across imports" tone="info" />
        <StatCard label="Relationships" value={formatNumber(summary.totals.relationships)} hint={`${summary.graph.observed_edges} observed / ${summary.graph.inferred_edges} inferred`} tone="high" />
        <StatCard label="Investigations" value={formatNumber(summary.totals.investigations)} hint={`${summary.totals.running_ingestion_jobs} ingestion jobs running`} />
        <StatCard label="Graph nodes" value={formatNumber(summary.graph.node_count)} hint={`Average degree ${summary.graph.average_degree.toFixed(2)}`} />
      </div>

      <div className="chart-grid">
        <section className="card">
          <h3>Severity distribution</h3>
          <div className="chart-box">
            <Doughnut
              data={{
                labels: severityLabels.map((label) => label.toUpperCase()),
                datasets: [
                  {
                    data: severityValues,
                    backgroundColor: ["#38bdf8", "#facc15", "#fb923c", "#f87171"],
                    borderColor: "#0f172a",
                    borderWidth: 2,
                  },
                ],
              }}
              options={doughnutOptions}
            />
          </div>
        </section>
        <section className="card">
          <h3>Indicator types</h3>
          <div className="chart-box">
            <Bar
              data={{
                labels: typeEntries.length ? typeEntries.map(([key]) => key.toUpperCase()) : ["No data"],
                datasets: [
                  {
                    label: "Indicators",
                    data: typeEntries.length ? typeEntries.map(([, value]) => value) : [0],
                    backgroundColor: "#38bdf8",
                    borderRadius: 6,
                  },
                ],
              }}
              options={chartOptions}
            />
          </div>
        </section>
        <section className="card">
          <h3>Relationship provenance</h3>
          <div className="chart-box">
            <Doughnut
              data={{
                labels: provenanceEntries.length ? provenanceEntries.map(([key]) => key) : ["No data"],
                datasets: [
                  {
                    data: provenanceEntries.length ? provenanceEntries.map(([, value]) => value) : [1],
                    backgroundColor: ["#22c55e", "#a855f7"],
                    borderColor: "#0f172a",
                    borderWidth: 2,
                  },
                ],
              }}
              options={doughnutOptions}
            />
          </div>
          <p className="muted">Observed links come from evidence. Inferred links are analytical candidates.</p>
        </section>
      </div>

      <div className="two-column">
        <section className="card">
          <SectionHeader title="High-risk indicators" action={<Link className="text-link" to="/indicators">View all</Link>} />
          {summary.high_risk_indicators.length === 0 ? (
            <EmptyState title="No high-risk indicators yet" detail="Ingest data or create indicators to populate this view." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Value</th><th>Type</th><th>Severity</th><th>Confidence</th></tr></thead>
                <tbody>
                  {summary.high_risk_indicators.map((indicator) => (
                    <tr key={indicator.id}>
                      <td className="mono">{indicator.value}</td>
                      <td><Badge>{indicator.type}</Badge></td>
                      <td><SeverityBadge severity={indicator.severity} /></td>
                      <td>{formatPercent(indicator.confidence)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="card">
          <SectionHeader title="Recent investigations" action={<Link className="text-link" to="/investigations">Open workspace</Link>} />
          {summary.recent_investigations.length === 0 ? (
            <EmptyState title="No cases yet" detail="Create an investigation to track related indicators." />
          ) : (
            <div className="list">
              {summary.recent_investigations.map((item) => (
                <div className="list-row" key={item.id}>
                  <div>
                    <strong>{item.title}</strong>
                    <span>{formatDate(item.updated_at)}</span>
                  </div>
                  <Badge tone={item.status}>{item.status.replace("_", " ")}</Badge>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <div className="two-column">
        <section className="card">
          <SectionHeader title="Recent ingestion" action={<Link className="text-link" to="/ingestion">Ingest data</Link>} />
          {summary.recent_ingestion_jobs.length === 0 ? (
            <EmptyState title="No ingestion jobs yet" />
          ) : (
            <div className="list">
              {summary.recent_ingestion_jobs.map((job) => (
                <div className="list-row" key={job.id}>
                  <div>
                    <strong>{job.file_name ?? job.source}</strong>
                    <span>{job.format} · {job.imported_indicators} indicators · {formatDate(job.created_at)}</span>
                  </div>
                  <Badge tone={job.status}>{job.status}</Badge>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="card">
          <SectionHeader title="Model status" action={<Link className="text-link" to="/analytics">Open analytics</Link>} />
          {summary.model.trained ? (
            <div className="model-status">
              <Badge tone="success">trained</Badge>
              <strong>{summary.model.version}</strong>
              <span>{summary.model.training_samples} training samples</span>
              <span>Accuracy {formatPercent(summary.model.metrics?.accuracy)}</span>
              {summary.model.metrics?.roc_auc !== undefined && <span>ROC AUC {formatPercent(summary.model.metrics.roc_auc)}</span>}
              <p className="muted">Label source: {summary.model.label_source}</p>
            </div>
          ) : (
            <EmptyState title="No trained model" detail="Train a risk model from the Analytics workspace." />
          )}
        </section>
      </div>
    </div>
  );
}
