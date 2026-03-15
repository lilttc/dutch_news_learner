/**
 * API client for the Dutch News Learner FastAPI backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getEpisodes(
  limit = 50,
  offset = 0
): Promise<EpisodeListItem[]> {
  return fetchJSON(`/api/episodes?limit=${limit}&offset=${offset}`);
}

export async function getEpisode(id: number): Promise<EpisodeDetail> {
  return fetchJSON(`/api/episodes/${id}`);
}

export async function updateVocabStatus(
  vocabularyId: number,
  status: string
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/vocabulary/${vocabularyId}/status`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }
  );
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}
