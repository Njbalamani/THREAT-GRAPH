import { useCallback, useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { ingestionApi, systemApi } from "../api";
import { useAuth } from "../auth";
import { Badge, EmptyState, ErrorBanner, Loading, Notice, SectionHeader, formatDate, formatNumber } from "../components/UI";
import type { IngestionJob, IngestionResult, SeedSamplesResult } from "../types";

export function Ingestion() {
  const { canWrite } = useAuth();
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [result, setResult] = useState<IngestionResult | SeedSamplesResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [uploadSource, setUploadSource] = useState("upload");
  const [text, setText] = useState("192.0.2.41\nlogin-portal.example\n9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08");
  const [textFilename, setTextFilename] = useState("analyst-notes.txt");
  const [textSource, setTextSource] = useState("analyst");

  const loadJobs = useCallback(() => {
    setLoading(true);
    setError(null);
    ingestionApi
      .jobs()
      .then(setJobs)
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Unable to load ingestion jobs"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
  }

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a file first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await ingestionApi.upload(file, uploadSource.trim() || "upload");
      setResult(response);
      loadJobs();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function ingestText(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const response = await ingestionApi.text({
        content: text,
        filename: textFilename,
        source: textSource,
      });
      setResult(response);
      loadJobs();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Text ingestion failed");
    } finally {
      setBusy(false);
    }
  }

  async function seedSamples() {
    setBusy(true);
    setError(null);
    try {
      const response = await systemApi.seedSamples();
      setResult(response);
      loadJobs();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sample seeding failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-stack">
      <ErrorBanner message={error} onClose={() => setError(null)} />
      <SectionHeader
        title="Ingestion pipeline"
        subtitle="Import JSON, CSV, raw logs, or STIX bundles. Every job is validated, deduplicated, and linked into the graph."
      />

      {!canWrite && <Notice>Your role is read-only. Analyst or admin access is required to import data.</Notice>}

      <div className="two-column">
        <form className="card form-card" onSubmit={upload}>
          <h3>Upload dataset</h3>
          <p className="muted">Maximum configured upload size is enforced by the API.</p>
          <label className="field">
            <span className="field__label">Dataset file</span>
            <input type="file" onChange={handleFile} accept=".json,.csv,.txt,.log,.stix,.jsonl" />
          </label>
          <label className="field">
            <span className="field__label">Source label</span>
            <input value={uploadSource} onChange={(event) => setUploadSource(event.target.value)} placeholder="upload" />
          </label>
          <button type="submit" className="button button--primary" disabled={busy || !canWrite || !file}>
            {busy ? "Processing…" : "Upload and analyze"}
          </button>
        </form>

        <form className="card form-card" onSubmit={ingestText}>
          <h3>Paste intelligence</h3>
          <p className="muted">Extract IPs, domains, hashes, URLs, and emails from raw text.</p>
          <label className="field">
            <span className="field__label">Content</span>
            <textarea rows={5} value={text} onChange={(event) => setText(event.target.value)} />
          </label>
          <div className="field-row">
            <label className="field">
              <span className="field__label">Filename</span>
              <input value={textFilename} onChange={(event) => setTextFilename(event.target.value)} />
            </label>
            <label className="field">
              <span className="field__label">Source</span>
              <input value={textSource} onChange={(event) => setTextSource(event.target.value)} />
            </label>
          </div>
          <button type="submit" className="button button--primary" disabled={busy || !canWrite || text.trim().length < 2}>
            {busy ? "Processing…" : "Ingest text"}
          </button>
        </form>
      </div>

      <section className="card">
        <SectionHeader
          title="Sample datasets"
          subtitle="Load bundled event, log, CSV, and STIX examples to explore the platform."
          action={
            <button type="button" className="button button--secondary" onClick={seedSamples} disabled={busy || !canWrite}>
              Seed samples
            </button>
          }
        />
      </section>

      {result && <ResultPanel result={result} />}

      <section className="card">
        <SectionHeader
          title="Ingestion jobs"
          subtitle="Audit trail for every import, including rejected records and relationship build results."
          action={<button type="button" className="button button--ghost" onClick={loadJobs}>Refresh</button>}
        />
        {loading ? (
          <Loading label="Loading jobs…" />
        ) : jobs.length === 0 ? (
          <EmptyState title="No jobs yet" detail="Upload a dataset or seed the sample feeds to begin." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Source</th><th>File</th><th>Format</th><th>Status</th><th>Records</th><th>Indicators</th><th>Events</th><th>Rejected</th><th>Created</th></tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td>{job.source}</td>
                    <td className="mono">{job.file_name ?? "—"}</td>
                    <td>{job.format}</td>
                    <td><Badge tone={job.status}>{job.status}</Badge></td>
                    <td>{formatNumber(job.total_records)}</td>
                    <td>{formatNumber(job.imported_indicators)}</td>
                    <td>{formatNumber(job.imported_events)}</td>
                    <td>{formatNumber(job.rejected_records)}</td>
                    <td>{formatDate(job.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function ResultPanel({ result }: { result: IngestionResult | SeedSamplesResult }) {
  if ("seeded_files" in result) {
    return (
      <section className="card">
        <SectionHeader title="Sample import complete" subtitle={`${result.seeded_files} datasets processed.`} />
        <div className="result-grid">
          {result.results.map((item) => (
            <div className="result-tile" key={item.job_id}>
              <strong>{item.file}</strong>
              <span>{item.format}</span>
              <Badge tone={item.status}>{item.status}</Badge>
              <span>{formatNumber(item.imported_indicators)} indicators · {formatNumber(item.imported_events)} events</span>
              <span>{item.relationships.observed_edges} observed · {item.relationships.inferred_edges} inferred</span>
            </div>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="card">
      <SectionHeader title="Ingestion result" subtitle={`Job ${result.job_id}`} />
      <div className="result-grid">
        <div className="result-tile"><strong>{formatNumber(result.total_records)}</strong><span>records</span></div>
        <div className="result-tile"><strong>{formatNumber(result.imported_indicators)}</strong><span>indicators</span></div>
        <div className="result-tile"><strong>{formatNumber(result.imported_events)}</strong><span>events</span></div>
        <div className="result-tile"><strong>{formatNumber(result.rejected_records)}</strong><span>rejected</span></div>
        <div className="result-tile"><strong>{result.relationships.observed_edges}</strong><span>observed edges</span></div>
        <div className="result-tile"><strong>{result.relationships.inferred_edges}</strong><span>inferred edges</span></div>
      </div>
      {result.errors.length > 0 && (
        <div className="error-list">
          {result.errors.slice(0, 10).map((item, index) => <div key={`${index}-${String(item.message ?? item)}`}>{String(item.message ?? item.reason ?? JSON.stringify(item))}</div>)}
        </div>
      )}
    </section>
  );
}
