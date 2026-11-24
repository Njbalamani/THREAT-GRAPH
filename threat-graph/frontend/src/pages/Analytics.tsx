import { useCallback, useEffect, useState } from "react";
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
import { analyticsApi } from "../api";
import { useAuth } from "../auth";
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
import type { AnalysisResult, ModelStatus, Prediction, TrainResult } from "../types";

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend);

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: "70%",
  plugins: { legend: { position: "bottom" as const, labels: { color: "#cbd5e1", boxWidth: 12 } } },
};

export function Analytics() {
  const { canWrite } = useAuth();
  const [model, setModel] = useState<ModelStatus | null>(null);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [training, setTraining] = useState<TrainResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([analyticsApi.model(), analyticsApi.predictions()])
      .then(([nextModel, nextPredictions]) => {
        setModel(nextModel);
        setPredictions(nextPredictions);
      })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Unable to load analytics"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function run(key: "rebuild" | "analyze" | "train", action: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    try {
      const result = await action();
      if (key === "analyze") setAnalysis(result as AnalysisResult);
      if (key === "train") {
        setTraining(result as TrainResult);
        load();
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Analytics operation failed");
    } finally {
      setBusy(null);
    }
  }

  const riskLevels = ["low", "medium", "high", "critical"] as const;
  const riskCounts = riskLevels.map((level) => predictions.filter((item) => item.risk_level === level).length);

  if (loading && !model) return <Loading label="Loading analytics…" />;

  return (
    <div className="page-stack">
      <ErrorBanner message={error} onClose={() => setError(null)} />
      <Notice>Model predictions are advisory, never confirmed attacks. Analysts must validate evidence before escalation.</Notice>
      <SectionHeader
        title="Graph analytics & machine learning"
        subtitle="Detect communities, rank important nodes, flag anomalous links, and score indicator risk."
        action={<button type="button" className="button button--ghost" onClick={load}>Refresh</button>}
      />

      <div className="button-row">
        <button type="button" className="button button--secondary" disabled={busy !== null || !canWrite} onClick={() => run("rebuild", analyticsApi.rebuild)}>
          {busy === "rebuild" ? "Rebuilding…" : "Rebuild relationships"}
        </button>
        <button type="button" className="button button--secondary" disabled={busy !== null} onClick={() => run("analyze", () => analyticsApi.analyze(true))}>
          {busy === "analyze" ? "Analyzing…" : "Analyze graph"}
        </button>
        <button type="button" className="button button--primary" disabled={busy !== null || !canWrite} onClick={() => run("train", analyticsApi.train)}>
          {busy === "train" ? "Training…" : "Train risk model"}
        </button>
      </div>
      {!canWrite && <Notice>Analyst or admin access is required to rebuild relationships or train models.</Notice>}

      <div className="stat-grid stat-grid--compact">
        <StatCard label="Predictions" value={formatNumber(predictions.length)} hint="Advisory only" tone="inferred" />
        <StatCard label="High / critical" value={formatNumber(predictions.filter((item) => item.risk_level === "high" || item.risk_level === "critical").length)} tone="critical" />
        <StatCard label="Model accuracy" value={model?.trained ? formatPercent(model.metrics?.accuracy) : "—"} />
        <StatCard label="Training rows" value={formatNumber(model?.training_samples)} />
        <StatCard label="Model version" value={model?.trained ? model.version ?? "—" : "Not trained"} />
      </div>

      {training && (
        <section className="card">
          <SectionHeader title="Training complete" subtitle={`Version ${training.version}`} />
          <div className="result-grid">
            <div className="result-tile"><strong>{formatNumber(training.training_samples)}</strong><span>samples</span></div>
            <div className="result-tile"><strong>{formatPercent(training.metrics.accuracy)}</strong><span>accuracy</span></div>
            <div className="result-tile"><strong>{training.metrics.evaluation_rows}</strong><span>evaluation rows</span></div>
            <div className="result-tile"><strong>{training.label_source}</strong><span>label source</span></div>
          </div>
          <Notice tone="warning">{training.note}</Notice>
        </section>
      )}

      <div className="two-column">
        <section className="card">
          <h3>Risk level distribution</h3>
          <div className="chart-box chart-box--short">
            <Doughnut
              data={{
                labels: riskLevels.map((level) => level.toUpperCase()),
                datasets: [{ data: riskCounts, backgroundColor: ["#38bdf8", "#facc15", "#fb923c", "#f87171"], borderColor: "#0f172a", borderWidth: 2 }],
              }}
              options={doughnutOptions}
            />
          </div>
        </section>

        <section className="card">
          <h3>Model features</h3>
          {model?.trained && model.features ? (
            <div className="tag-cloud">
              {model.features.map((feature) => <Badge key={feature}>{feature}</Badge>)}
            </div>
          ) : (
            <EmptyState title="No trained model" detail="Train the risk model to unlock predictions." />
          )}
          {model?.trained && model.label_source === "heuristic" && (
            <Notice tone="warning">Labels were derived heuristically. Treat scores as exploratory until analysts confirm indicators.</Notice>
          )}
        </section>
      </div>

      <section className="card">
        <SectionHeader title="Advisory predictions" subtitle="Each score includes an explanation and its originating model version." />
        {predictions.length === 0 ? (
          <EmptyState title="No predictions yet" detail="Train a model after ingesting at least two indicators." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Indicator</th><th>Type</th><th>Probability</th><th>Risk</th><th>Cluster</th><th>Status</th><th>Explanation</th><th>Model</th></tr></thead>
              <tbody>
                {predictions.map((prediction) => (
                  <tr key={`${prediction.indicator_id}-${prediction.model_version}`}>
                    <td className="mono">{prediction.value}</td>
                    <td><Badge>{prediction.type}</Badge></td>
                    <td>{formatPercent(prediction.probability)}</td>
                    <td><SeverityBadge severity={prediction.risk_level} /></td>
                    <td>{prediction.cluster_id ?? "—"}{prediction.cluster_size ? ` (${prediction.cluster_size})` : ""}</td>
                    <td><Badge tone={prediction.confirmed ? "success" : "warning"}>{prediction.confirmed ? "confirmed" : "prediction only"}</Badge></td>
                    <td>
                      <div className="explanation-list">
                        {prediction.explanation.slice(0, 3).map((item) => <span key={item}>{item}</span>)}
                      </div>
                    </td>
                    <td className="mono">{prediction.model_version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {analysis && (
        <>
          <section className="card">
            <SectionHeader title="Graph analysis" subtitle={`${analysis.backend} · generated ${formatDate(analysis.generated_at)}`} />
            <div className="stat-grid stat-grid--compact">
              <StatCard label="Nodes analyzed" value={formatNumber(analysis.node_count)} />
              <StatCard label="Edges analyzed" value={formatNumber(analysis.edge_count)} />
              <StatCard label="Clusters" value={formatNumber(analysis.clusters.length)} />
              <StatCard label="Anomalies" value={formatNumber(analysis.anomalies.length)} tone="critical" />
            </div>
            {analysis.clusters.length > 0 && (
              <div className="chart-box chart-box--short">
                <Bar
                  data={{
                    labels: analysis.clusters.map((cluster) => `Cluster ${cluster.cluster_id}`),
                    datasets: [{ label: "Nodes", data: analysis.clusters.map((cluster) => cluster.size), backgroundColor: "#38bdf8", borderRadius: 6 }],
                  }}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: "#cbd5e1" } } },
                    scales: { x: { ticks: { color: "#94a3b8" } }, y: { ticks: { color: "#94a3b8", precision: 0 } } },
                  }}
                />
              </div>
            )}
          </section>

          <div className="two-column">
            <section className="card">
              <h3>Important nodes</h3>
              {analysis.important_nodes.length === 0 ? (
                <EmptyState title="No important nodes" />
              ) : (
                <div className="list">
                  {analysis.important_nodes.slice(0, 10).map((node) => (
                    <div className="list-row" key={node.key}>
                      <div><strong>{node.label}</strong><span>{node.type} · degree {node.degree}</span></div>
                      <Badge tone="info">{node.score.toFixed(3)}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </section>
            <section className="card">
              <h3>Anomalous relationships</h3>
              {analysis.anomalies.length === 0 ? (
                <EmptyState title="No anomalies detected" />
              ) : (
                <div className="list">
                  {analysis.anomalies.slice(0, 10).map((item) => (
                    <div className="list-row" key={`${item.source}-${item.target}-${item.relationship}`}>
                      <div>
                        <strong>{item.source} → {item.target}</strong>
                        <span>{item.reason}</span>
                      </div>
                      <Badge tone="critical">{item.score.toFixed(3)}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
