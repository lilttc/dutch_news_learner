/**
 * API client for the Dutch News Learner FastAPI backend.
 *
 * Auth (Phase 6F): Bearer token (registered) > X-Session-Token (anonymous).
 * JWT in localStorage (dutch_news_auth), session token (dutch_news_session).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const AUTH_TOKEN_KEY = "dutch_news_auth";
const SESSION_KEY = "dutch_news_session";

let _sessionPromise: Promise<string> | null = null;

/** JWT for registered users. Client only. */
function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

/** Session token for anonymous users. Client only. */
async function getSessionToken(): Promise<string> {
  if (typeof window === "undefined") return "";
  const stored = localStorage.getItem(SESSION_KEY);
  if (stored) return stored;
  if (!_sessionPromise) {
    _sessionPromise = fetch(`${API_BASE}/api/session`)
      .then((r) => r.json())
      .then((d: { token: string }) => {
        localStorage.setItem(SESSION_KEY, d.token);
        return d.token;
      });
  }
  return _sessionPromise;
}

/** Token for API: prefer Bearer (JWT), else X-Session-Token. */
async function getAuthHeaders(): Promise<Record<string, string>> {
  const jwt = getAuthToken();
  if (jwt) return { Authorization: `Bearer ${jwt}` };
  const session = await getSessionToken();
  if (session) return { "X-Session-Token": session };
  return {};
}

async function fetchWithAuth<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const authHeaders = await getAuthHeaders();
  const headers = new Headers(options?.headers);
  Object.entries(authHeaders).forEach(([k, v]) => headers.set(k, v));
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface EpisodeListItem {
  id: number;
  video_id: string;
  title: string;
  published_at: string | null;
  thumbnail_url: string | null;
  topics: string | null;
  vocab_count: number;
}

export interface Segment {
  id: number;
  text: string;
  translation_en: string | null;
  start_time: number;
  duration: number;
}

export interface VocabWord {
  vocabulary_id: number;
  lemma: string;
  pos: string | null;
  occurrence_count: number;
  surface_forms: string | null;
  example_sentence: string | null;
  meaning: string | null;
  meaning_en: string | null;
  status: string;
}

export interface Article {
  topic: string;
  title: string;
  url: string;
  snippet: string;
}

export interface EpisodeDetail {
  id: number;
  video_id: string;
  title: string;
  description: string | null;
  published_at: string | null;
  topics: string | null;
  segments: Segment[];
  vocabulary: VocabWord[];
  related_articles: Article[];
}

export async function getEpisodes(
  limit = 50,
  offset = 0
): Promise<EpisodeListItem[]> {
  return fetchWithAuth(`/api/episodes?limit=${limit}&offset=${offset}`);
}

export async function getEpisode(id: number): Promise<EpisodeDetail> {
  return fetchWithAuth(`/api/episodes/${id}`);
}

export async function updateVocabStatus(
  vocabularyId: number,
  status: string
): Promise<void> {
  const authHeaders = await getAuthHeaders();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders,
  };
  const res = await fetch(
    `${API_BASE}/api/vocabulary/${vocabularyId}/status`,
    {
      method: "PUT",
      headers,
      body: JSON.stringify({ status }),
    }
  );
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}
