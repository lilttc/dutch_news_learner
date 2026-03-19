"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import type { Segment, VocabWord } from "@/lib/api";

interface Props {
  segments: Segment[];
  videoId: string;
  vocabulary: VocabWord[];
  onSeek?: (seconds: number) => void;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

interface MergedSentence {
  start_time: number;
  text: string;
  translation_en: string;
}

function mergeIntoSentences(segs: Segment[]): MergedSentence[] {
  const sorted = [...segs].sort((a, b) => a.start_time - b.start_time);
  const result: MergedSentence[] = [];
  let texts: string[] = [];
  let translations: string[] = [];
  let startTime = 0;

  for (const seg of sorted) {
    const text = seg.text.trim();
    if (!text) continue;
    if (texts.length === 0) startTime = seg.start_time;
    texts.push(text);
    if (seg.translation_en) translations.push(seg.translation_en);

    if (/[.!?]$/.test(text)) {
      result.push({
        start_time: startTime,
        text: texts.join(" "),
        translation_en: translations.join(" "),
      });
      texts = [];
      translations = [];
    }
  }
  if (texts.length > 0) {
    result.push({
      start_time: startTime,
      text: texts.join(" "),
      translation_en: translations.join(" "),
    });
  }
  return result;
}

export function Transcript({ segments, videoId, vocabulary, onSeek }: Props) {
  const [showTranslation, setShowTranslation] = useState(false);
  const [bubble, setBubble] = useState<{
    word: VocabWord;
    clickedForm: string;
    x: number;
    y: number;
  } | null>(null);
  const bubbleRef = useRef<HTMLDivElement>(null);
  const sentences = mergeIntoSentences(segments);

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
        clickedForm: word,
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
        {sentences.map((sent, i) => (
          <div key={i} className="leading-relaxed">
            <button
              type="button"
              onClick={() => onSeek?.(sent.start_time)}
              title={`Jump to ${formatTime(sent.start_time)}`}
              className="mr-2 text-sm font-bold text-[var(--muted)] hover:text-[var(--foreground)] hover:underline"
            >
              {formatTime(sent.start_time)}
            </button>
            <span>{renderText(sent.text)}</span>
            {showTranslation && sent.translation_en && (
              <p className="ml-14 text-sm text-[var(--muted)]">
                {sent.translation_en}
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
          <h3 className="mb-2 text-lg font-bold">{bubble.clickedForm}</h3>
          {bubble.word.pos && (
            <p className="text-xs text-[var(--muted)]">({bubble.word.pos})</p>
          )}
          {bubble.word.lemma.toLowerCase() !== bubble.clickedForm.toLowerCase() && (
            <p className="mt-1 text-sm">
              <strong>{bubble.word.pos === "VERB" ? "Infinitive" : "Base form"}:</strong>{" "}
              {bubble.word.lemma}
            </p>
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
