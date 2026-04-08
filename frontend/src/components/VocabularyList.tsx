"use client";

import { useState } from "react";
import { updateVocabStatus, type VocabWord } from "@/lib/api";

const STATUS_OPTIONS = [
  { value: "new", label: "New" },
  { value: "learning", label: "📖 Learning" },
  { value: "known", label: "✅ Known" },
] as const;

const DEFAULT_LIMIT = 20;

export function VocabularyList({ vocabulary }: { vocabulary: VocabWord[] }) {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"frequency" | "alpha">("frequency");
  const [hideKnown, setHideKnown] = useState(true);
  const [showAll, setShowAll] = useState(false);
  const [statuses, setStatuses] = useState<Record<number, string>>(() => {
    const map: Record<number, string> = {};
    for (const v of vocabulary) map[v.vocabulary_id] = v.status;
    return map;
  });
  const [expanded, setExpanded] = useState<number | null>(null);

  let filtered = vocabulary.filter((v) => {
    if (hideKnown && (statuses[v.vocabulary_id] || v.status) === "known")
      return false;
    if (search) return v.lemma.toLowerCase().includes(search.toLowerCase());
    return true;
  });

  if (sortBy === "alpha") {
    filtered = [...filtered].sort((a, b) =>
      a.lemma.toLowerCase().localeCompare(b.lemma.toLowerCase())
    );
  } else {
    filtered = [...filtered].sort(
      (a, b) => b.occurrence_count - a.occurrence_count
    );
  }

  const isSearching = search.length > 0;
  const display =
    showAll || isSearching ? filtered : filtered.slice(0, DEFAULT_LIMIT);
  const hiddenCount = filtered.length - display.length;

  async function handleStatusChange(vocabId: number, newStatus: string) {
    const prevStatus = statuses[vocabId] ?? "new";
    setStatuses((prev) => ({ ...prev, [vocabId]: newStatus }));
    try {
      await updateVocabStatus(vocabId, newStatus);
    } catch {
      setStatuses((prev) => ({ ...prev, [vocabId]: prevStatus }));
    }
  }

  return (
    <div>
      <p className="mb-2 text-xs text-[var(--muted)]">
        Your progress is saved per session (this browser).
      </p>
      {/* Controls */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Search words..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-sm"
        />
        <select
          value={sortBy}
          onChange={(e) =>
            setSortBy(e.target.value as "frequency" | "alpha")
          }
          className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm"
        >
          <option value="frequency">Most frequent</option>
          <option value="alpha">A-Z</option>
        </select>
        <span className="flex items-center gap-2 text-sm">
          <span className="text-[var(--muted)]">Filter:</span>
          <label className="flex items-center gap-1">
            <input
              type="radio"
              name="knownFilter"
              checked={hideKnown}
              onChange={() => setHideKnown(true)}
              className="rounded-full"
            />
            Hide known
          </label>
          <label className="flex items-center gap-1">
            <input
              type="radio"
              name="knownFilter"
              checked={!hideKnown}
              onChange={() => setHideKnown(false)}
              className="rounded-full"
            />
            Show all
          </label>
        </span>
        <label className="flex items-center gap-1.5 text-sm">
          <input
            type="checkbox"
            checked={showAll}
            onChange={(e) => setShowAll(e.target.checked)}
            className="rounded"
          />
          Show all {filtered.length} words
        </label>
      </div>

      {/* Word list */}
      <div className="space-y-1">
        {display.map((v) => {
          const isOpen = expanded === v.vocabulary_id;
          const currentStatus = statuses[v.vocabulary_id] || "new";
          const statusIcon =
            currentStatus === "known"
              ? "✅ "
              : currentStatus === "learning"
                ? "📖 "
                : "";

          return (
            <div
              key={v.vocabulary_id}
              className="rounded-md border border-[var(--border)]"
            >
              <button
                onClick={() =>
                  setExpanded(isOpen ? null : v.vocabulary_id)
                }
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-[var(--card)]"
              >
                <span>
                  {statusIcon}
                  <strong>{v.lemma}</strong>{" "}
                  <span className="text-[var(--muted)]">
                    ({v.pos}) - {v.occurrence_count}×
                  </span>
                </span>
                <span className="text-[var(--muted)]">{isOpen ? "▲" : "▼"}</span>
              </button>

              {isOpen && (
                <div className="border-t border-[var(--border)] px-3 py-3 text-sm">
                  {v.meaning && (
                    <p>
                      <strong>Meaning:</strong> {v.meaning}
                    </p>
                  )}
                  {v.meaning_en && (
                    <p className="mt-1">
                      <strong>English:</strong> {v.meaning_en}
                    </p>
                  )}
                  {!v.meaning && !v.meaning_en && (
                    <p className="text-[var(--muted)]">
                      No definition available.
                    </p>
                  )}
                  {v.example_sentence && (
                    <p className="mt-2 italic text-[var(--muted)]">
                      {v.example_sentence}
                    </p>
                  )}
                  {v.surface_forms && (
                    <p className="mt-1 text-xs text-[var(--muted)]">
                      Forms: {v.surface_forms.replace(/\|/g, ", ")}
                    </p>
                  )}

                  {/* Status buttons */}
                  <div className="mt-3 flex gap-2">
                    {STATUS_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() =>
                          handleStatusChange(v.vocabulary_id, opt.value)
                        }
                        disabled={currentStatus === opt.value}
                        className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                          currentStatus === opt.value
                            ? "bg-[var(--accent)] text-white"
                            : "border border-[var(--border)] hover:bg-[var(--card)]"
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {hiddenCount > 0 && (
        <p className="mt-3 text-xs text-[var(--muted)]">
          Showing {display.length} of {filtered.length} words.
        </p>
      )}
    </div>
  );
}
