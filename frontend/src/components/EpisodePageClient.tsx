"use client";

import { useEffect, useState } from "react";
import { getEpisode, type EpisodeDetail } from "@/lib/api";
import { EpisodeView } from "./EpisodeView";

export function EpisodePageClient({ id }: { id: number }) {
  const [episode, setEpisode] = useState<EpisodeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getEpisode(id)
      .then(setEpisode)
      .catch(() =>
        setError("Could not load episode. Make sure the API is running on port 8000.")
      );
  }, [id]);

  if (error) {
    return (
      <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!episode) {
    return (
      <div className="text-center py-8 text-[var(--muted)]">Loading episode…</div>
    );
  }

  return <EpisodeView episode={episode} />;
}
