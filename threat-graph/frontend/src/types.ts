export type UserRole = "admin" | "analyst" | "viewer";
export type IndicatorType = "ip" | "domain" | "hash" | "url" | "email";
export type Severity = "low" | "medium" | "high" | "critical";
export type Priority = "low" | "medium" | "high" | "critical";
export type InvestigationStatus = "open" | "in_progress" | "resolved" | "closed";
export type JobStatus = "running" | "completed" | "failed";
export type FeedType = "stix" | "taxii" | "json" | "csv" | "log";
export type Provenance = "observed" | "inferred";

export interface Token {
  access_token: string;
  token_type: "bearer";
}

export interface UserOut {
  id: string;
  email: string;
  username: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface Indicator {
  type: IndicatorType;
  value: string;
  severity: Severity;
  confidence: number;
  source: string;
  description: string | null;
  tags: string[];
  stix_id: string | null;
  is_confirmed: boolean;
  id: string;
  first_seen: string;
  last_seen: string;
  raw: Record<string, unknown>;
}

export interface IndicatorCreate {
  type: IndicatorType;
  value: string;
  severity?: Severity;
  confidence?: number;
  source?: string;
  description?: string | null;
  tags?: string[];
  stix_id?: string | null;
  is_confirmed?: boolean;
}

export interface IndicatorUpdate {
  severity?: Severity | null;
  confidence?: number | null;
  description?: string | null;
  tags?: string[] | null;
  is_confirmed?: boolean | null;
}

export interface IngestionJob {
  id: string;
  source: string;
  file_name: string | null;
  format: string;
  status: JobStatus;
  total_records: number;
  imported_indicators: number;
  imported_events: number;
  rejected_records: number;
  errors: Array<Record<string, unknown>>;
  created_at: string;
  completed_at: string | null;
}

export interface RelationshipBuildResult {
  events_processed: number;
  nodes_upserted: number;
  edges_upserted: number;
  relationships_created: number;
  observed_edges: number;
  inferred_edges: number;
  backend: string;
}

export interface IngestionResult {
  job_id: string;
  status: string;
  format: string;
  total_records: number;
  imported_indicators: number;
  imported_events: number;
  rejected_records: number;
  errors: Array<Record<string, unknown>>;
  relationships: RelationshipBuildResult;
}

export interface SeedSamplesResult {
  seeded_files: number;
  results: Array<{ file: string } & IngestionResult>;
}

export interface GraphNode {
  key: string;
  id: string;
  type: string;
  label: string;
  properties: Record<string, unknown>;
  degree: number;
  risk_score: number | null;
}

export interface GraphEdge {
  key: string;
  source: string;
  target: string;
  relationship: string;
  provenance: Provenance;
  confidence: number;
  strength: number;
  properties: Record<string, unknown>;
}

export interface GraphSnapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphStats {
  node_count: number;
  edge_count: number;
  observed_edges: number;
  inferred_edges: number;
  node_types: Record<string, number>;
  relationship_types: Record<string, number>;
  average_degree: number;
}

export interface ClusterOut {
  cluster_id: number;
  size: number;
  nodes: string[];
  labels: string[];
  risk_score: number;
}

export interface ImportantNodeOut {
  key: string;
  label: string;
  type: string;
  score: number;
  degree: number;
}

export interface AnomalyOut {
  source: string;
  target: string;
  relationship: string;
  provenance: Provenance;
  score: number;
  reason: string;
}

export interface AnalysisResult {
  backend: string;
  node_count: number;
  edge_count: number;
  clusters: ClusterOut[];
  important_nodes: ImportantNodeOut[];
  anomalies: AnomalyOut[];
  generated_at: string;
}

export interface TrainMetrics {
  accuracy: number;
  evaluation_rows: number;
  training_rows: number;
  roc_auc?: number;
}

export interface TrainResult {
  version: string;
  training_samples: number;
  metrics: TrainMetrics;
  features: string[];
  label_source: "analyst_or_trusted_feed" | "heuristic";
  note: string;
}

export interface Prediction {
  indicator_id: string;
  value: string;
  type: IndicatorType;
  probability: number;
  risk_level: Severity;
  cluster_id: number | null;
  cluster_size: number | null;
  confirmed: boolean;
  prediction_only: boolean;
  explanation: string[];
  model_version: string;
}

export interface ModelStatus {
  trained: boolean;
  version?: string;
  model_type?: string;
  metrics?: TrainMetrics & { cluster_sizes?: Record<string, number> };
  features?: string[];
  training_samples?: number;
  label_source?: "analyst_or_trusted_feed" | "heuristic";
  artifact_path?: string;
  created_at?: string;
}

export interface Investigation {
  id: string;
  title: string;
  description: string | null;
  status: InvestigationStatus;
  priority: Priority;
  created_at: string;
  updated_at: string;
}

export interface Note {
  id: string;
  content: string;
  author_id: string | null;
  created_at: string;
}

export interface TimelineEvent {
  id: string;
  kind: "event" | "note";
  title: string;
  description: string | null;
  timestamp: string;
  severity: Severity | null;
  source: string | null;
}

export interface InvestigationDetail {
  investigation: Investigation;
  indicators: Indicator[];
  notes: Note[];
  timeline: TimelineEvent[];
}

export interface InvestigationCreate {
  title: string;
  description?: string | null;
  priority?: Priority;
}

export interface InvestigationUpdate {
  title?: string | null;
  description?: string | null;
  status?: InvestigationStatus | null;
  priority?: Priority | null;
}

export interface FeedConfig {
  name: string;
  description: string | null;
  feed_type: FeedType;
  url: string;
  collection_id: string | null;
  auth_header_env: string | null;
  enabled: boolean;
  poll_interval_minutes: number;
  id: string;
  last_polled_at: string | null;
  last_status: string | null;
  last_error: string | null;
  created_at: string;
}

export interface FeedConfigCreate {
  name: string;
  description?: string | null;
  feed_type: FeedType;
  url: string;
  collection_id?: string | null;
  auth_header_env?: string | null;
  enabled?: boolean;
  poll_interval_minutes?: number;
}

export interface FeedConfigUpdate {
  description?: string | null;
  url?: string | null;
  collection_id?: string | null;
  auth_header_env?: string | null;
  enabled?: boolean | null;
  poll_interval_minutes?: number | null;
}

export interface FeedPollResult extends IngestionResult {
  feed_id: string;
  feed_name: string;
}

export interface DashboardSummary {
  totals: {
    indicators: number;
    suspicious_ips: number;
    malicious_domains: number;
    relationships: number;
    investigations: number;
    running_ingestion_jobs: number;
  };
  indicator_types: Partial<Record<IndicatorType, number>>;
  severity_distribution: Partial<Record<Severity, number>>;
  relationship_provenance: Partial<Record<Provenance, number>>;
  investigation_status: Partial<Record<InvestigationStatus, number>>;
  graph: GraphStats;
  model: ModelStatus;
  high_risk_indicators: Indicator[];
  recent_investigations: Investigation[];
  recent_ingestion_jobs: IngestionJob[];
  disclaimer: string;
}

export interface SystemHealth {
  status: "ok";
  service: "ThreatGraph";
}

export interface ReportRequest {
  title?: string;
  investigation_id?: string | null;
  indicator_ids?: string[];
  include_predictions?: boolean;
  minimum_severity?: Severity;
}

export interface ApiErrorPayload {
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
  detail?: unknown;
}
