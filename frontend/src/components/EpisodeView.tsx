"use client";

import { useState } from "react";
import type { EpisodeDetail } from "@/lib/api";
import { Transcript } from "./Transcript";
import { VocabularyList } from "./VocabularyList";
import { RelatedReading } from "./RelatedReading";

const TABS = ["Transcript", "Vocabulary", "Related Reading"] as const;
type Tab = (typeof TABS)[number];

function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-GB", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function EpisodeView({ episode }: { episode: EpisodeDetail }) {
  const [activeTab, setActiveTab] = useState<Tab>("Transcript");

  return (
    <div>
      <h1 className="mb-1 text-xl font-bold">{episode.title}</h1>
      {episode.published_at && (
        <p className="mb-4 text-sm text-[var(--muted)]">
          {formatDate(episode.published_at)}
        </p>
      )}

      {/* Video embed */}
      <div className="relative mb-6 overflow-hidden rounded-lg pb-[56.25%]">
        <iframe
          className="absolute inset-0 h-full w-full"
          src={`https://www.youtube.com/embed/${episode.video_id}`}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
        />
      </div>

      {/* Tab bar */}
      <div className="mb-4 flex gap-1 border-b border-[var(--border)]">
        {TABS.map((tab) => {
          const isActive = activeTab === tab;
          const label =
            tab === "Vocabulary"
              ? `Vocabulary (${episode.vocabulary.length})`
              : tab;
          return (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "border-b-2 border-[var(--accent)] text-[var(--accent)]"
                  : "text-[var(--muted)] hover:text-[var(--foreground)]"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {activeTab === "Transcript" && (
        <Transcript
          segments={episode.segments}
          videoId={episode.video_id}
          vocabulary={episode.vocabulary}
        />
      )}
      {activeTab === "Vocabulary" && (
        <VocabularyList vocabulary={episode.vocabulary} />
      )}
      {activeTab === "Related Reading" && (
        <RelatedReading
          articles={episode.related_articles}
          topics={episode.topics}
        />
      )}
    </div>
  );
}
