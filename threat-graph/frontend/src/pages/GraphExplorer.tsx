import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { graphApi } from "../api";
import { GraphCanvas } from "../components/GraphCanvas";
import {
  Badge,
  EmptyState,
  ErrorBanner,
  Loading,
  Notice,
  ProvenanceBadge,
  SectionHeader,
  StatCard,
  formatNumber,
} from "../components/UI";
import type { GraphSnapshot, GraphStats, Provenance } from "../types";

export function GraphExplorer() {
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [snapshot, setSnapshot] = useState<GraphSnapshot>({ nodes: [], edges: [] });
  const [sourceSnapshot, setSourceSnapshot] = useState<GraphSnapshot | null>(null);
  const [viewLabel, setViewLabel] = useState("Full graph");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [observed, setObserved] = useState(true);
  const [inferred, setInferred] = useState(true);
  const [nodeKey, setNodeKey] = useState("");
  const [depth, setDepth] = useState(1);
  const [pathSource, setPathSource] = useState("");
  const [pathTarget, setPathTarget] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([graphApi.stats(), graphApi.snapshot(600)])
      .then(([nextStats, nextSnapshot]) => {
        setStats(nextStats);
        setSnapshot(nextSnapshot);
        setSourceSnapshot(nextSnapshot);
        setViewLabel("Full graph");
        setSelectedKey(null);
      })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Unable to load graph"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const visibleProvenance = useMemo<Provenance[]>(() => {
    const values: Provenance[] = [];
    if (observed) values.push("observed");
    if (inferred) values.push("inferred");
    return values;
  }, [observed, inferred]);

  const handleSelect = useCallback((key: string | null) => setSelectedKey(key), []);
  const selectedNode = snapshot.nodes.find((node) => node.key === selectedKey) ?? null;
  const selectedEdges = selectedKey ? snapshot.edges.filter((edge) => edge.source === selectedKey || edge.target === selectedKey) : [];

  async function neighbors(event: FormEvent) {
    event.preventDefault();
    if (!nodeKey.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await graphApi.neighbors(nodeKey.trim(), depth);
      setSourceSnapshot(result);
      setSnapshot(result);
      setViewLabel(`Neighborhood: ${nodeKey.trim()}`);
      setSelectedKey(nodeKey.trim());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Neighbor query failed");
    } finally {
      setBusy(false);
    }
  }

  async function path(event: FormEvent) {
    event.preventDefault();
    if (!pathSource.trim() || !pathTarget.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await graphApi.path(pathSource.trim(), pathTarget.trim());
      setSourceSnapshot(result);
      setSnapshot(result);
      setViewLabel(`Path: ${pathSource.trim()} → ${pathTarget.trim()}`);
      setSelectedKey(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Path query failed");
    } finally {
      setBusy(false);
    }
  }

  function restore() {
    if (sourceSnapshot) {
      setSnapshot(sourceSnapshot);
      setViewLabel("Full graph");
    } else {
      load();
    }
  }

  return (
    <div className="page-stack">
      <ErrorBanner message={error} onClose={() => setError(null)} />
      <Notice>Legend: solid green edges are observed evidence; dashed purple edges are inferred analytical connections.</Notice>
      <SectionHeader
        title="Relationship graph"
        subtitle="Explore attack relationships backed by evidence and analytical inference."
        action={<button type="button" className="button button--ghost" onClick={load}>Reload graph</button>}
      />

      {stats && (
        <div className="stat-grid stat-grid--compact">
          <StatCard label="Nodes" value={formatNumber(stats.node_count)} />
          <StatCard label="Edges" value={formatNumber(stats.edge_count)} />
          <StatCard label="Observed" value={formatNumber(stats.observed_edges)} tone="success" />
          <StatCard label="Inferred" value={formatNumber(stats.inferred_edges)} tone="inferred" />
          <StatCard label="Avg. degree" value={stats.average_degree.toFixed(2)} />
        </div>
      )}

      <div className="graph-layout">
        <section className="card graph-card">
          <div className="graph-toolbar">
            <Badge tone="info">{viewLabel}</Badge>
            <label className="checkbox"><input type="checkbox" checked={observed} onChange={(event) => setObserved(event.target.checked)} /><span>Observed</span></label>
            <label className="checkbox"><input type="checkbox" checked={inferred} onChange={(event) => setInferred(event.target.checked)} /><span>Inferred</span></label>
            <button type="button" className="button button--tiny" onClick={restore}>Restore view</button>
          </div>
          {loading ? (
            <Loading label="Building graph view…" />
          ) : snapshot.nodes.length === 0 ? (
            <EmptyState title="Graph is empty" detail="Ingest sample datasets or import intelligence to create relationships." />
          ) : (
            <GraphCanvas
              snapshot={snapshot}
              visibleProvenance={visibleProvenance}
              selectedKey={selectedKey}
              onSelect={handleSelect}
            />
          )}
          <div className="graph-legend">
            <span><i className="legend-dot legend-dot--indicator" /> Indicator</span>
            <span><i className="legend-dot legend-dot--event" /> Event</span>
            <span><i className="legend-line legend-line--observed" /> Observed</span>
            <span><i className="legend-line legend-line--inferred" /> Inferred</span>
          </div>
        </section>

        <aside className="graph-side">
          <form className="card form-card" onSubmit={neighbors}>
            <h3>Neighbors</h3>
            <label className="field">
              <span className="field__label">Node key</span>
              <input list="graph-node-options" value={nodeKey} onChange={(event) => setNodeKey(event.target.value)} placeholder="indicator:…" />
            </label>
            <label className="field">
              <span className="field__label">Depth</span>
              <select value={depth} onChange={(event) => setDepth(Number(event.target.value))}>
                <option value={1}>1 hop</option>
                <option value={2}>2 hops</option>
                <option value={3}>3 hops</option>
              </select>
            </label>
            <button type="submit" className="button button--secondary" disabled={busy}>Expand neighborhood</button>
          </form>

          <form className="card form-card" onSubmit={path}>
            <h3>Shortest path</h3>
            <label className="field">
              <span className="field__label">Source</span>
              <input list="graph-node-options" value={pathSource} onChange={(event) => setPathSource(event.target.value)} />
            </label>
            <label className="field">
              <span className="field__label">Target</span>
              <input list="graph-node-options" value={pathTarget} onChange={(event) => setPathTarget(event.target.value)} />
            </label>
            <button type="submit" className="button button--secondary" disabled={busy}>Find path</button>
          </form>

          <datalist id="graph-node-options">
            {snapshot.nodes.map((node) => <option key={node.key} value={node.key}>{node.label}</option>)}
          </datalist>

          <section className="card">
            <h3>Selected node</h3>
            {!selectedNode ? (
              <EmptyState title="No node selected" detail="Click a node in the graph to inspect evidence." />
            ) : (
              <div className="detail-stack">
                <strong>{selectedNode.label}</strong>
                <div className="detail-row"><span>Key</span><code>{selectedNode.key}</code></div>
                <div className="detail-row"><span>Type</span><Badge>{selectedNode.type}</Badge></div>
                <div className="detail-row"><span>Degree</span><span>{selectedNode.degree}</span></div>
                <div className="detail-row"><span>Risk</span><span>{selectedNode.risk_score ?? "—"}</span></div>
                <div className="detail-row"><span>Connected edges</span><span>{selectedEdges.length}</span></div>
                {Object.entries(selectedNode.properties).slice(0, 8).map(([key, value]) => (
                  <div className="detail-row" key={key}><span>{key}</span><code>{String(value)}</code></div>
                ))}
              </div>
            )}
          </section>

          {selectedEdges.length > 0 && (
            <section className="card">
              <h3>Connected relationships</h3>
              <div className="list">
                {selectedEdges.slice(0, 12).map((edge) => (
                  <div className="list-row" key={edge.key || `${edge.source}-${edge.target}`}>
                    <div>
                      <strong>{edge.relationship}</strong>
                      <span>{edge.source} → {edge.target}</span>
                    </div>
                    <ProvenanceBadge provenance={edge.provenance} />
                  </div>
                ))}
              </div>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
