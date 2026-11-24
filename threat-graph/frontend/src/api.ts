import type {
  AnalysisResult,
  ApiErrorPayload,
  DashboardSummary,
  FeedConfig,
  FeedConfigCreate,
  FeedConfigUpdate,
  FeedPollResult,
  GraphSnapshot,
  GraphStats,
  Investigation,
  InvestigationCreate,
  InvestigationDetail,
  InvestigationUpdate,
  Indicator,
  IndicatorCreate,
  IndicatorUpdate,
  IngestionJob,
  IngestionResult,
  ModelStatus,
  Note,
  Prediction,
  ReportRequest,
  SeedSamplesResult,
  SystemHealth,
  TimelineEvent,
  Token,
  TrainResult,
  UserOut,
  UserRole,
} from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "http://localhost:8000";
const TOKEN_KEY = "threatgraph_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  let payload: unknown = text;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!response.ok) {
    const body = payload as ApiErrorPayload;
    const message = body?.error?.message ?? (typeof payload === "string" && payload ? payload : `Request failed with status ${response.status}`);
    const error = new Error(message) as Error & { code?: string; details?: unknown };
    error.code = body?.error?.code;
    error.details = body?.error?.details ?? body?.detail;
    throw error;
  }
  return payload as T;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
  headers?: HeadersInit;
  signal?: AbortSignal;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (options.auth !== false && token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  let body: BodyInit | undefined;
  if (options.body instanceof FormData || options.body instanceof URLSearchParams) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body,
    signal: options.signal,
  });
  return parseResponse<T>(response);
}

export async function download(path: string, filename: string, options: RequestOptions = {}): Promise<void> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (options.auth !== false && token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body,
  });
  if (!response.ok) {
    await parseResponse(response);
    return;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export const authApi = {
  login(username: string, password: string): Promise<Token> {
    const form = new URLSearchParams();
    form.set("username", username);
    form.set("password", password);
    return api<Token>("/api/auth/login", {
      method: "POST",
      body: form,
      auth: false,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
  },
  me(): Promise<UserOut> {
    return api<UserOut>("/api/auth/me");
  },
  register(payload: { email: string; username: string; full_name: string; password: string; role?: UserRole }): Promise<UserOut> {
    return api<UserOut>("/api/auth/register", { method: "POST", body: payload });
  },
  users(): Promise<UserOut[]> {
    return api<UserOut[]>("/api/auth/users");
  },
};

export const systemApi = {
  health(): Promise<SystemHealth> {
    return api<SystemHealth>("/api/system/health", { auth: false });
  },
  seedSamples(): Promise<SeedSamplesResult> {
    return api<SeedSamplesResult>("/api/system/seed-samples", { method: "POST" });
  },
};

export const dashboardApi = {
  summary(): Promise<DashboardSummary> {
    return api<DashboardSummary>("/api/dashboard/summary");
  },
};

export const indicatorsApi = {
  list(params: { indicator_type?: string; severity?: string; search?: string; limit?: number; offset?: number } = {}): Promise<Indicator[]> {
    return api<Indicator[]>(`/api/indicators${query(params)}`);
  },
  get(id: string): Promise<Indicator> {
    return api<Indicator>(`/api/indicators/${encodeURIComponent(id)}`);
  },
  create(payload: IndicatorCreate): Promise<Indicator> {
    return api<Indicator>("/api/indicators", { method: "POST", body: payload });
  },
  update(id: string, payload: IndicatorUpdate): Promise<Indicator> {
    return api<Indicator>(`/api/indicators/${encodeURIComponent(id)}`, { method: "PATCH", body: payload });
  },
  remove(id: string): Promise<void> {
    return api<void>(`/api/indicators/${encodeURIComponent(id)}`, { method: "DELETE" });
  },
};

export const ingestionApi = {
  upload(file: File, source = "upload"): Promise<IngestionResult> {
    const form = new FormData();
    form.set("file", file);
    form.set("source", source);
    return api<IngestionResult>("/api/ingestion/upload", { method: "POST", body: form });
  },
  text(payload: { content: string; filename?: string; source?: string; format_hint?: string | null }): Promise<IngestionResult> {
    return api<IngestionResult>("/api/ingestion/text", { method: "POST", body: payload });
  },
  jobs(limit = 100): Promise<IngestionJob[]> {
    return api<IngestionJob[]>(`/api/ingestion/jobs${query({ limit })}`);
  },
};

export const graphApi = {
  stats(): Promise<GraphStats> {
    return api<GraphStats>("/api/graph/stats");
  },
  snapshot(limit = 500): Promise<GraphSnapshot> {
    return api<GraphSnapshot>(`/api/graph/snapshot${query({ limit })}`);
  },
  neighbors(key: string, depth = 1): Promise<GraphSnapshot> {
    return api<GraphSnapshot>(`/api/graph/neighbors${query({ key, depth })}`);
  },
  path(source: string, target: string): Promise<GraphSnapshot> {
    return api<GraphSnapshot>("/api/graph/path", { method: "POST", body: { source, target } });
  },
};

export const analyticsApi = {
  rebuild(): Promise<Record<string, unknown>> {
    return api<Record<string, unknown>>("/api/analytics/graph/rebuild", { method: "POST" });
  },
  analyze(persist = false): Promise<AnalysisResult> {
    return api<AnalysisResult>(`/api/analytics/graph/analyze${query({ persist })}`, { method: "POST" });
  },
  train(): Promise<TrainResult> {
    return api<TrainResult>("/api/analytics/model/train", { method: "POST" });
  },
  model(): Promise<ModelStatus> {
    return api<ModelStatus>("/api/analytics/model");
  },
  predictions(): Promise<Prediction[]> {
    return api<Prediction[]>("/api/analytics/predictions");
  },
};

export const investigationsApi = {
  list(): Promise<Investigation[]> {
    return api<Investigation[]>("/api/investigations");
  },
  get(id: string): Promise<InvestigationDetail> {
    return api<InvestigationDetail>(`/api/investigations/${encodeURIComponent(id)}`);
  },
  create(payload: InvestigationCreate): Promise<InvestigationDetail> {
    return api<InvestigationDetail>("/api/investigations", { method: "POST", body: payload });
  },
  update(id: string, payload: InvestigationUpdate): Promise<Investigation> {
    return api<Investigation>(`/api/investigations/${encodeURIComponent(id)}`, { method: "PATCH", body: payload });
  },
  remove(id: string): Promise<void> {
    return api<void>(`/api/investigations/${encodeURIComponent(id)}`, { method: "DELETE" });
  },
  linkIndicator(caseId: string, indicatorId: string): Promise<InvestigationDetail> {
    return api<InvestigationDetail>(`/api/investigations/${encodeURIComponent(caseId)}/indicators/${encodeURIComponent(indicatorId)}`, { method: "POST" });
  },
  addNote(caseId: string, content: string): Promise<Note> {
    return api<Note>(`/api/investigations/${encodeURIComponent(caseId)}/notes`, { method: "POST", body: { content } });
  },
  timeline(caseId: string): Promise<TimelineEvent[]> {
    return api<TimelineEvent[]>(`/api/investigations/${encodeURIComponent(caseId)}/timeline`);
  },
};

export const feedsApi = {
  list(): Promise<FeedConfig[]> {
    return api<FeedConfig[]>("/api/feeds");
  },
  create(payload: FeedConfigCreate): Promise<FeedConfig> {
    return api<FeedConfig>("/api/feeds", { method: "POST", body: payload });
  },
  update(id: string, payload: FeedConfigUpdate): Promise<FeedConfig> {
    return api<FeedConfig>(`/api/feeds/${encodeURIComponent(id)}`, { method: "PATCH", body: payload });
  },
  remove(id: string): Promise<void> {
    return api<void>(`/api/feeds/${encodeURIComponent(id)}`, { method: "DELETE" });
  },
  poll(id: string): Promise<FeedPollResult> {
    return api<FeedPollResult>(`/api/feeds/${encodeURIComponent(id)}/poll`, { method: "POST" });
  },
  pollEnabled(): Promise<FeedPollResult[]> {
    return api<FeedPollResult[]>("/api/feeds/poll-enabled", { method: "POST" });
  },
};

export const reportsApi = {
  pdf(payload: ReportRequest): Promise<void> {
    return download("/api/reports/pdf", "threatgraph-report.pdf", { method: "POST", body: payload });
  },
  indicatorsCsv(): Promise<void> {
    return download("/api/exports/indicators.csv", "threatgraph-indicators.csv");
  },
  relationshipsCsv(): Promise<void> {
    return download("/api/exports/relationships.csv", "threatgraph-relationships.csv");
  },
  graphJson(): Promise<void> {
    return download("/api/exports/graph.json", "threatgraph-graph.json");
  },
  graphGraphml(): Promise<void> {
    return download("/api/exports/graph.graphml", "threatgraph-graph.graphml");
  },
};
