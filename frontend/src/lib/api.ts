/**
 * API client for the Dutch News Learner FastAPI backend.
 *
 * Anonymous sessions (Phase 6E): token stored in localStorage, sent via
 * X-Session-Token header. GET /api/session creates/returns session.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SESSION_KEY = "dutch_news_session";

let _tokenPromise: Promise<string> | null = null;

/** Get or create session token. On client: fetches from API if missing. On server: returns "". */
async function getSessionToken(): Promise<string> {
  if (typeof window === "undefined") return "";
  const stored = localStorage.getItem(SESSION_KEY);
  if (stored) return stored;
  if (!_tokenPromise) {
    _tokenPromise = fetch(`${API_BASE}/api/session`)
      .then((r) => r.json())
      .then((d: { token: string }) => {
        localStorage.setItem(SESSION_KEY, d.token);
        return d.token;
      });
  }
  return _tokenPromise;
}

async function fetchWithAuth<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const token = await getSessionToken();
  const headers = new Headers(options?.headers);
  if (token) headers.set("X-Session-Token", token);
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
  const token = await getSessionToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["X-Session-Token"] = token;
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
