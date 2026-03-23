import type { Article } from "@/lib/api";

/** Fix missing spaces in Dutch text from search snippets (e.g. "deverkiezingenheeft" -> "de verkiezingen heeft"). */
function fixConcatenatedSpaces(text: string): string {
  if (!text) return text;
  let t = text;
  t = t.replace(/\bde(?=[a-z]{2,})/gi, "de ");
  t = t.replace(/\bhet(?=[a-z]{2,})/gi, "het ");
  t = t.replace(/\been(?=[a-z]{2,})/gi, "een ");
  for (const word of [
    "heeft", "hebben", "is", "zijn", "van", "op", "te", "dat", "die", "voor", "met", "naar", "uit"
  ]) {
    t = t.replace(new RegExp(`([a-z])(${word})\\b`, "g"), "$1 $2");
  }
  return t;
}

interface Props {
  articles: Article[];
  topics: string | null;
}

export function RelatedReading({ articles, topics }: Props) {
  if (!topics) {
    return (
      <p className="text-sm text-[var(--muted)]">
        No topics extracted for this episode.
      </p>
    );
  }

  const topicList = topics.split("|").filter(Boolean);

  if (articles.length === 0) {
    return (
      <div>
        <p className="mb-3 text-sm text-[var(--muted)]">
          No articles fetched yet. Run{" "}
          <code className="rounded bg-[var(--card)] px-1 py-0.5 text-xs">
            python scripts/fetch_related_articles.py
          </code>{" "}
          to populate.
        </p>
        <div className="space-y-2">
          {topicList.map((t) => (
            <a
              key={t}
              href={`https://www.google.com/search?q=${encodeURIComponent(t + " site:nos.nl")}`}
              target="_blank"
              rel="noopener noreferrer"
              className="block text-[var(--accent)] hover:underline"
            >
              {t.trim()}
            </a>
          ))}
        </div>
      </div>
    );
  }

  // Group by topic
  const byTopic = new Map<string, Article[]>();
  for (const a of articles) {
    const list = byTopic.get(a.topic) || [];
    list.push(a);
    byTopic.set(a.topic, list);
  }

  return (
    <div>
      <p className="mb-4 text-xs text-[var(--muted)]">
        NOS articles related to this episode&apos;s topics
      </p>
      <div className="space-y-5">
        {topicList.map((topic) => {
          const topicArticles = byTopic.get(topic.trim()) || [];
          return (
            <div key={topic}>
              <h3 className="mb-2 font-semibold">{topic.trim()}</h3>
              {topicArticles.length > 0 ? (
                <ul className="space-y-2">
                  {topicArticles.map((a, i) => (
                    <li key={i}>
                      <a
                        href={a.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[var(--accent)] hover:underline"
                      >
                        {fixConcatenatedSpaces(a.title)}
                      </a>
                      {a.snippet && (
                        <p className="mt-0.5 text-xs text-[var(--muted)]">
                          {fixConcatenatedSpaces(a.snippet)}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-[var(--muted)]">
                  No articles found for this topic.
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
