import type { components } from "./generated";

export type User = components["schemas"]["UserOut"];
export type Application = components["schemas"]["ApplicationOut"];
export type ApplicationCreate = components["schemas"]["ApplicationCreate"];
export type ApplicationUpdate = components["schemas"]["ApplicationUpdate"];
export type ApplicationList = components["schemas"]["ApplicationList"];
export type StatusHistory = components["schemas"]["StatusHistoryOut"];
export type Reminder = components["schemas"]["ReminderOut"];
export type ReminderList = components["schemas"]["ReminderList"];
export type Resume = components["schemas"]["ResumeOut"];
export type Score = components["schemas"]["ScoreOut"];
export type Stats = components["schemas"]["StatsOut"];
export type ApplicationStatus = Application["status"];

const API_URL = (import.meta.env.VITE_API_URL || "/api").replace(/\/$/, "");
const SCORING_TIMEOUT_MS = 65_000;
const DEFAULT_TIMEOUT_MS = 15_000;
let memoryToken: string | null = sessionStorage.getItem("jobtrack_token");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getToken(): string | null {
  return memoryToken;
}

export function setToken(token: string | null): void {
  memoryToken = token;
  if (token) {
    sessionStorage.setItem("jobtrack_token", token);
  } else {
    sessionStorage.removeItem("jobtrack_token");
  }
}

function clearSessionAndRedirect(): void {
  const hadSession = getToken() !== null;
  setToken(null);
  if (hadSession) window.dispatchEvent(new Event("jobtrack:unauthorized"));
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  const headers = new Headers(options.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !headers.has("Content-Type")) {
    if (options.body instanceof URLSearchParams) {
      headers.set("Content-Type", "application/x-www-form-urlencoded;charset=UTF-8");
    } else if (!(options.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
  }

  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
    if (response.status === 401) clearSessionAndRedirect();
    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try {
        const body = (await response.json()) as { detail?: string };
        if (body.detail) message = body.detail;
      } catch {
        // Keep the status-based message when the server returns no JSON body.
      }
      throw new ApiError(message, response.status);
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("Request timed out. Please try again.", 408);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export const api = {
  signup: (email: string, password: string) =>
    request<User>("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: async (email: string, password: string) => {
    const body = new URLSearchParams({ username: email, password });
    const result = await request<{ access_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      body,
    });
    setToken(result.access_token);
    return result;
  },
  me: () => request<User>("/auth/me"),
  deleteAccount: () => request<void>("/auth/me", { method: "DELETE" }),
  applications: (filters: { status?: string; q?: string } = {}) => {
    const query = new URLSearchParams({ limit: "100" });
    if (filters.status) query.set("status", filters.status);
    if (filters.q) query.set("q", filters.q);
    return request<ApplicationList>(`/applications?${query.toString()}`);
  },
  application: (id: number) => request<Application>(`/applications/${id}`),
  deleteApplication: (id: number) =>
    request<void>(`/applications/${id}`, { method: "DELETE" }),
  createApplication: (data: ApplicationCreate) =>
    request<Application>("/applications", { method: "POST", body: JSON.stringify(data) }),
  updateApplication: (id: number, data: ApplicationUpdate) =>
    request<Application>(`/applications/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  changeStatus: (id: number, nextStatus: ApplicationStatus, note?: string) =>
    request<Application>(`/applications/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: nextStatus, note }),
    }),
  history: (id: number) => request<StatusHistory[]>(`/applications/${id}/history`),
  reminders: (due = false) =>
    request<ReminderList>(`/reminders?due=${String(due)}&limit=100`),
  createReminder: (id: number, dueAt: string, note: string) =>
    request<Reminder>(`/applications/${id}/reminders`, {
      method: "POST",
      body: JSON.stringify({ due_at: dueAt, note }),
    }),
  markReminderDone: (id: number) =>
    request<Reminder>(`/reminders/${id}/done`, { method: "PATCH" }),
  resumes: () => request<Resume[]>("/resumes"),
  uploadResume: (label: string, file: File) => {
    const body = new FormData();
    body.set("label", label);
    body.set("file", file);
    return request<Resume>("/resumes", { method: "POST", body });
  },
  deleteResume: (id: number) => request<void>(`/resumes/${id}`, { method: "DELETE" }),
  score: (applicationId: number, resumeId: number) =>
    request<Score>(
      `/applications/${applicationId}/score`,
      { method: "POST", body: JSON.stringify({ resume_id: resumeId }) },
      SCORING_TIMEOUT_MS,
    ),
  scores: (applicationId: number) =>
    request<Score[]>(`/applications/${applicationId}/scores`),
  stats: () => request<Stats>("/stats"),
};
