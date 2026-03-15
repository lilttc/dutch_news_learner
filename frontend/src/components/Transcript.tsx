"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import type { Segment, VocabWord } from "@/lib/api";

interface Props {
  segments: Segment[];
  videoId: string;
  vocabulary: VocabWord[];
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export function Transcript({ segments, videoId, vocabulary }: Props) {
  const [showTranslation, setShowTranslation] = useState(false);
  const [bubble, setBubble] = useState<{
    word: VocabWord;
    x: number;
    y: number;
  } | null>(null);
  const bubbleRef = useRef<HTMLDivElement>(null);

  // Build word -> VocabWord lookup
  const wordMap = new Map<string, VocabWord>();
  for (const v of vocabulary) {
    wordMap.set(v.lemma.toLowerCase(), v);
    if (v.surface_forms) {
      for (const form of v.surface_forms.split("|")) {
        const f = form.trim().toLowerCase();
        if (f) wordMap.set(f, v);
      }
    }
  }

  const handleWordClick = useCallback(
    (word: string, event: React.MouseEvent) => {
      const vocab = wordMap.get(word.toLowerCase());
      if (!vocab) return;
      const rect = (event.target as HTMLElement).getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      setBubble({
        word: vocab,
        x: Math.min(rect.left, window.innerWidth - 380),
        y: spaceBelow > 300 ? rect.bottom + 8 : rect.top - 300,
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [vocabulary]
  );

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        bubbleRef.current &&
        !bubbleRef.current.contains(e.target as Node)
      ) {
        setBubble(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  function renderText(text: string) {
    return text.split(/(\w+)/g).map((part, i) => {
      const vocab = wordMap.get(part.toLowerCase());
      if (vocab) {
        return (
          <span
            key={i}
            className="cursor-pointer text-[var(--accent)] underline decoration-dotted hover:decoration-solid"
            onClick={(e) => handleWordClick(part, e)}
          >
            {part}
          </span>
        );
      }
      return <span key={i}>{part}</span>;
    });
  }

  return (
    <div>
      <label className="mb-3 flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={showTranslation}
          onChange={(e) => setShowTranslation(e.target.checked)}
          className="rounded"
        />
        Show English translation
      </label>
      <p className="mb-4 text-xs text-[var(--muted)]">
        Click any underlined word to see its definition.
      </p>

      <div className="space-y-3">
        {segments.map((seg) => (
          <div key={seg.id} className="leading-relaxed">
            <a
              href={`https://www.youtube.com/watch?v=${videoId}&t=${Math.floor(seg.start_time)}s`}
              target="_blank"
              rel="noopener noreferrer"
              className="mr-2 text-sm font-bold text-[var(--muted)] hover:text-[var(--foreground)]"
            >
              {formatTime(seg.start_time)}
            </a>
            <span>{renderText(seg.text)}</span>
            {showTranslation && seg.translation_en && (
              <p className="ml-14 text-sm text-[var(--muted)]">
                {seg.translation_en}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Definition bubble */}
      {bubble && (
        <div
          ref={bubbleRef}
          className="fixed z-50 max-h-[60vh] w-80 overflow-y-auto rounded-lg border border-[var(--border)] bg-[var(--background)] p-4 shadow-xl"
          style={{ left: bubble.x, top: bubble.y }}
        >
          <button
            onClick={() => setBubble(null)}
            className="float-right text-lg text-[var(--muted)] hover:text-[var(--foreground)]"
          >
            &times;
          </button>
          <h3 className="mb-2 text-lg font-bold">{bubble.word.lemma}</h3>
          {bubble.word.pos && (
            <p className="text-xs text-[var(--muted)]">({bubble.word.pos})</p>
          )}
          {bubble.word.meaning && (
            <p className="mt-2">
              <strong>Meaning:</strong> {bubble.word.meaning}
            </p>
          )}
          {bubble.word.meaning_en && (
            <p className="mt-1">
              <strong>English:</strong> {bubble.word.meaning_en}
            </p>
          )}
          {bubble.word.example_sentence && (
            <p className="mt-2 text-sm italic text-[var(--muted)]">
              {bubble.word.example_sentence}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
