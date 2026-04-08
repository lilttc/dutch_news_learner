import Link from "next/link";
import { getEpisodes, type EpisodeListItem } from "@/lib/api";

function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-GB", {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function TopicBadges({ topics }: { topics: string | null }) {
  if (!topics) return null;
  const list = topics.split("|").filter(Boolean);
  return (
    <div className="mt-1 flex flex-wrap gap-1">
      {list.map((t) => (
        <span
          key={t}
          className="rounded-full bg-[var(--accent-light)] px-2 py-0.5 text-xs text-[var(--accent)]"
        >
          {t.trim()}
        </span>
      ))}
    </div>
  );
}

export default async function HomePage() {
  let episodes: EpisodeListItem[] = [];
  let error = "";

  try {
    episodes = await getEpisodes();
  } catch {
    error =
      "Could not connect to the API. Make sure the FastAPI backend is running on port 8000.";
  }

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Episodes</h1>
      <p className="mb-6 text-sm text-[var(--muted)]">
        NOS Journaal in Makkelijke Taal - click an episode to start learning
      </p>

      {error && (
        <div className="mb-4 rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-3">
        {episodes.map((ep) => (
          <Link
            key={ep.id}
            href={`/episode/${ep.id}`}
            className="group flex items-start gap-4 rounded-lg border border-[var(--border)] p-4 transition-colors hover:bg-[var(--card)]"
          >
            {ep.thumbnail_url && (
              <img
                src={ep.thumbnail_url}
                alt=""
                className="h-20 w-28 flex-shrink-0 rounded object-cover"
              />
            )}
            <div className="min-w-0 flex-1">
              <h2 className="font-medium leading-snug group-hover:text-[var(--accent)]">
                {ep.title}
              </h2>
              <div className="mt-1 flex items-center gap-3 text-xs text-[var(--muted)]">
                {ep.published_at && <span>{formatDate(ep.published_at)}</span>}
                <span>{ep.vocab_count} words</span>
              </div>
              <TopicBadges topics={ep.topics} />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
