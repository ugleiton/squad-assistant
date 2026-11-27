async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  get: <T,>(p: string) => request<T>("GET", p),
  post: <T,>(p: string, b?: unknown) => request<T>("POST", p, b),
  put: <T,>(p: string, b: unknown) => request<T>("PUT", p, b),
  del: (p: string) => request<void>("DELETE", p),
};

export type ChatConnection = { id: number; name: string; provider: "slack" | "mattermost"; base_url?: string; has_token: boolean };
export type GitLabConnection = { id: number; name: string; base_url: string; has_token: boolean };
export type Member = { id: number; name: string; chat_user_id?: string; chat_username?: string; gitlab_username?: string };
export type Squad = { id: number; name: string; member_ids: number[] };
export type ReviewAssistant = {
  id: number; name: string; enabled: boolean; language: string; chat_connection_id: number;
  channel_id: string; gitlab_connection_id: number; gitlab_projects: string[]; squad_ids: number[];
  scan_interval_minutes: number; emojis: Record<string, string>; features: Record<string, boolean>;
  webhook_url: string;
};
export type Schedule = { weekday: number; time: string };
export type DailyAssistant = {
  id: number; name: string; enabled: boolean; language: string; timezone: string;
  delivery: "bot" | "webhook"; chat_connection_id?: number | null; channel_id?: string | null;
  webhook_url?: string; has_webhook_url?: boolean; lead_time_minutes: number;
  rotation_mode: "none" | "daily" | "weekly"; meeting_url?: string | null;
  schedules: Schedule[]; participants: { member_id: number; order: number; active: boolean }[];
  current_facilitator_id?: number | null;
};
export type Meta = { languages: string[]; review_emojis: Record<string, string>; review_features: Record<string, boolean> };
