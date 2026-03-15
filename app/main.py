"""
Dutch News Learner — Streamlit learning interface.

Episode viewer with embedded video, subtitle transcript, and vocabulary list.
Click words in the transcript to jump to their definition.
Run with: streamlit run app/main.py
"""

import json
import re
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote_plus

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from sqlalchemy.orm import joinedload

from src.dictionary import get_lookup
from src.models import (
    Episode,
    EpisodeVocabulary,
    SubtitleSegment,
    VocabularyItem,
    get_engine,
    get_session,
)

# Page config
st.set_page_config(
    page_title="Dutch News Learner",
    page_icon="🇳🇱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Database
DB_PATH = "sqlite:///data/dutch_news.db"

# Lemmas to exclude from vocabulary (show names, etc.)
EXCLUDE_LEMMAS = {"journaal"}


@st.cache_resource
def get_db_session():
    """Create database session (cached)."""
    from src.models import _migrate_schema

    engine = get_engine(DB_PATH)
    _migrate_schema(engine)
    return get_session(engine)


def load_episodes(session):
    """Load all episodes ordered by date (newest first)."""
    return (
        session.query(Episode)
        .filter(Episode.transcript_fetched == True)
        .order_by(Episode.published_at.desc())
        .all()
    )


def load_episode_with_data(session, episode_id):
    """Load one episode with subtitles and vocabulary."""
    return (
        session.query(Episode)
        .options(
            joinedload(Episode.subtitle_segments),
            joinedload(Episode.episode_vocabulary).joinedload(EpisodeVocabulary.vocabulary_item),
        )
        .filter(Episode.id == episode_id)
        .first()
    )


def format_timestamp(seconds):
    """Convert seconds to MM:SS."""
    if seconds is None:
        return ""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


def render_video(video_id):
    """Embed YouTube video."""
    st.markdown(
        f'<iframe width="100%" height="400" '
        f'src="https://www.youtube.com/embed/{video_id}" '
        f'frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" '
        f'allowfullscreen></iframe>',
        unsafe_allow_html=True,
    )


def _filter_vocab(episode_vocab_list):
    """Exclude program-name lemmas (e.g. Journaal) from vocabulary."""
    return [ev for ev in episode_vocab_list if ev.vocabulary_item.lemma.lower() not in EXCLUDE_LEMMAS]


def build_word_to_lemma_map(episode_vocab_list):
    """
    Build mapping from surface forms (and lemma) to lemma for this episode.
    Used to make transcript words clickable.
    """
    word_to_lemma = {}
    for ev in episode_vocab_list:
        lemma = ev.vocabulary_item.lemma.lower()
        if lemma in EXCLUDE_LEMMAS:
            continue
        word_to_lemma[lemma] = lemma
        if ev.surface_forms:
            for form in ev.surface_forms.split("|"):
                f = form.strip().lower()
                if f:
                    word_to_lemma[f] = lemma
    return word_to_lemma


def build_vocab_bubble_data(episode_vocab_list):
    """
    Build vocabulary data for the click-to-show bubble: lemma -> list of {pos, meaning, forms, example, links}.
    """
    lookup = get_lookup()
    by_lemma = {}
    for ev in episode_vocab_list:
        v = ev.vocabulary_item
        lemma = v.lemma.lower()
        if lemma in EXCLUDE_LEMMAS:
            continue
        dict_entry = lookup.lookup_with_example(v.lemma, v.pos)
        meaning = v.translation or (dict_entry.get("gloss") if dict_entry else None)
        meaning_en = dict_entry.get("gloss_en") if dict_entry else None
        dict_example = dict_entry.get("example") if dict_entry else None
        example = dict_example or ev.example_sentence
        forms = []
        if ev.surface_forms:
            forms = [f.strip() for f in ev.surface_forms.split("|") if f.strip()]
        links = lookup.get_links(v.lemma)
        entry = {
            "pos": v.pos or "",
            "meaning": meaning or "(no definition)",
            "meaning_en": meaning_en or "",
            "forms": forms,
            "example": example,
            "links": links,
        }
        by_lemma.setdefault(lemma, []).append(entry)

    # Add entries for comparative forms (e.g. goedkoper -> cheaper when goedkoop -> cheap)
    def _derive_comparative(adj: str) -> str:
        if not adj:
            return ""
        if adj.endswith("y"):
            return adj[:-1] + "ier"
        if adj.endswith("e"):
            return adj + "r"
        return adj + "er"

    for lemma, entries in list(by_lemma.items()):
        for e in entries:
            if e.get("pos") == "ADJ" and e.get("meaning_en") and e.get("forms"):
                for form in e["forms"]:
                    f = form.strip().lower()
                    if f and f != lemma and f.endswith("er"):
                        comp_en = _derive_comparative(e["meaning_en"])
                        if comp_en:
                            comp_entry = {**e, "meaning_en": comp_en}
                            by_lemma.setdefault(f, []).insert(0, comp_entry)
    return by_lemma


def _transcript_bubble_html(segments, video_id, word_to_lemma, vocab_data, show_translation=True):
    """Generate HTML for transcript with click-to-show definition bubbles (no page reload)."""
    sorted_segments = sorted(segments, key=lambda s: s.start_time)
    lines = []
    for seg in sorted_segments:
        ts = format_timestamp(seg.start_time)
        yt_url = f"https://www.youtube.com/watch?v={video_id}&t={int(seg.start_time)}s"
        text = seg.text
        if word_to_lemma:
            # Replace vocab words with clickable spans
            def replace_word(match):
                before, core, after = match.group(1), match.group(2), match.group(3)
                core_lower = core.lower()
                if core_lower in word_to_lemma:
                    lemma = word_to_lemma[core_lower]
                    lemma_attr = lemma.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
                    word_attr = core_lower.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
                    return f'{before}<span class="vocab-word" data-lemma="{lemma_attr}" data-word="{word_attr}">{core}</span>{after}'
                return match.group(0)

            text = re.sub(r"(\W*)(\w+)(\W*)", replace_word, text)
        lines.append({
            "ts": ts,
            "yt_url": yt_url,
            "text": text,
            "translation_en": (getattr(seg, "translation_en", None) or "") if show_translation else "",
        })

    vocab_json = json.dumps(vocab_data).replace("</", "\\u003c/")  # Avoid breaking script tag
    lines_json = json.dumps(lines).replace("</", "\\u003c/")

    return f"""
<style>
.vocab-word {{ color:#1f77b4; text-decoration:underline; cursor:pointer; }}
.vocab-word:hover {{ color:#1565c0; }}
.bubble {{ display:none; position:fixed; z-index:9999; background:#fff; border:1px solid #ccc;
  border-radius:8px; box-shadow:0 4px 12px rgba(0,0,0,0.15); padding:12px 16px; max-width:360px;
  font-family:system-ui,sans-serif; font-size:14px; line-height:1.5; }}
.bubble.show {{ display:block; }}
.bubble-close {{ float:right; cursor:pointer; font-size:18px; color:#666; }}
.bubble-close:hover {{ color:#000; }}
.bubble-title {{ font-weight:bold; margin-bottom:8px; font-size:16px; }}
.bubble-section {{ margin:6px 0; }}
.bubble-links {{ margin-top:10px; font-size:12px; }}
.bubble-links a {{ color:#1f77b4; margin-right:8px; }}
.transcript-line {{ margin-bottom:14px; }}
.transcript-ts {{ font-weight:bold; }}
.transcript-ts a {{ color:inherit; }}
.transcript-en {{ color:#555; font-size:0.9em; margin-top:2px; margin-left:0; }}
.bubble-overlay {{ position:fixed; inset:0; z-index:9998; }}
</style>
<div id="transcript-root"></div>
<div id="bubble-overlay" class="bubble-overlay" style="display:none;"></div>
<div id="vocab-bubble" class="bubble">
  <span id="bubble-close" class="bubble-close">&times;</span>
  <div id="bubble-content"></div>
</div>
<script>
(function() {{
  var vocabData = {vocab_json};
  var lines = {lines_json};
  var root = document.getElementById('transcript-root');
  var bubble = document.getElementById('vocab-bubble');
  var bubbleContent = document.getElementById('bubble-content');
  var overlay = document.getElementById('bubble-overlay');

  function renderBubble(lemma, clickedWord) {{
    var lookupKey = (clickedWord && (vocabData[clickedWord] || vocabData[clickedWord.toLowerCase()])) ? clickedWord : lemma;
    var entries = vocabData[lookupKey] || vocabData[lookupKey.toLowerCase()] || vocabData[lemma] || vocabData[lemma.toLowerCase()];
    if (!entries || entries.length === 0) return;
    var displayLemma = clickedWord || lemma;
    var html = '<div class="bubble-title">' + displayLemma + '</div>';
    entries.forEach(function(e, i) {{
      if (e.pos) html += '<div class="bubble-section"><strong>(' + e.pos + ')</strong></div>';
      html += '<div class="bubble-section"><strong>Meaning:</strong> ' + (e.meaning || '') + '</div>';
      if (e.meaning_en) html += '<div class="bubble-section"><strong>English:</strong> ' + e.meaning_en + '</div>';
      if (e.forms && e.forms.length > 1) {{
        html += '<div class="bubble-section"><strong>Forms:</strong> ' + e.forms.join(', ') + '</div>';
      }}
      if (e.example) {{
        html += '<div class="bubble-section"><strong>Example:</strong> <em>' + e.example + '</em></div>';
      }}
      if (e.links && Object.keys(e.links).length) {{
        var links = [];
        for (var k in e.links) links.push('<a href="' + e.links[k] + '" target="_blank" rel="noopener">' + k + '</a>');
        html += '<div class="bubble-section bubble-links"><strong>Look up:</strong> ' + links.join(' · ') + '</div>';
      }}
    }});
    bubbleContent.innerHTML = html;
  }}

  function showBubble(lemma, clickedWord, ev) {{
    renderBubble(lemma, clickedWord);
    var rect = ev.target.getBoundingClientRect();
    bubble.style.left = Math.min(rect.left, window.innerWidth - 380) + 'px';
    bubble.style.top = (rect.bottom + 8) + 'px';
    bubble.classList.add('show');
    overlay.style.display = 'block';
  }}

  function hideBubble() {{
    bubble.classList.remove('show');
    overlay.style.display = 'none';
  }}

  document.getElementById('bubble-close').onclick = hideBubble;
  overlay.onclick = hideBubble;

  root.addEventListener('click', function(ev) {{
    var w = ev.target.closest('.vocab-word');
    if (w) {{
      ev.preventDefault();
      ev.stopPropagation();
      var lemma = w.getAttribute('data-lemma');
      var clickedWord = w.getAttribute('data-word') || lemma;
      showBubble(lemma, clickedWord, ev);
    }}
  }});

  lines.forEach(function(line) {{
    var div = document.createElement('div');
    div.className = 'transcript-line';
    var html = '<span class="transcript-ts"><a href="' + line.yt_url + '" target="_blank" rel="noopener">' + line.ts + '</a></span> ' + line.text;
    if (line.translation_en) {{
      html += '<div class="transcript-en">' + line.translation_en + '</div>';
    }}
    div.innerHTML = html;
    root.appendChild(div);
  }});
}})();
</script>
"""


def render_transcript_with_bubbles(segments, video_id, word_to_lemma=None, vocab_data=None, show_translation=True):
    """
    Render transcript with clickable words. Click shows a bubble with definition, forms, example.
    No page reload — all client-side.
    """
    if not word_to_lemma or not vocab_data:
        # Fallback: plain transcript without bubbles
        sorted_segments = sorted(segments, key=lambda s: s.start_time)
        for seg in sorted_segments:
            ts = format_timestamp(seg.start_time)
            yt_url = f"https://www.youtube.com/watch?v={video_id}&t={int(seg.start_time)}s"
            st.markdown(f"**[{ts}]({yt_url})** {seg.text}")
            if show_translation and getattr(seg, "translation_en", None):
                st.caption(seg.translation_en)
            st.markdown("")
        return
    html = _transcript_bubble_html(segments, video_id, word_to_lemma, vocab_data, show_translation=show_translation)
    st.components.v1.html(html, height=min(600, 150 + len(segments) * 28), scrolling=True)


def render_vocabulary(episode_vocab_list, search_query="", sort_by="frequency"):
    """
    Render vocabulary list with search, sort, and expandable details.

    Args:
        episode_vocab_list: List of EpisodeVocabulary objects.
        search_query: Filter by lemma (case-insensitive substring).
        sort_by: "frequency" (most common first) or "alpha" (A-Z).
    """
    lookup = get_lookup()

    # Filter by search
    if search_query:
        q = search_query.lower().strip()
        episode_vocab_list = [
            ev for ev in episode_vocab_list
            if q in ev.vocabulary_item.lemma.lower()
        ]

    # Sort
    if sort_by == "alpha":
        sorted_vocab = sorted(
            episode_vocab_list,
            key=lambda ev: ev.vocabulary_item.lemma.lower(),
        )
    else:
        sorted_vocab = sorted(
            episode_vocab_list,
            key=lambda ev: ev.occurrence_count or 0,
            reverse=True,
        )

    for ev in sorted_vocab:
        v = ev.vocabulary_item
        count = ev.occurrence_count if ev.occurrence_count is not None else 0
        with st.expander(f"**{v.lemma}** ({v.pos}) — {count}×"):
            # Meaning — from DB, then dictionary (POS-aware for correct definition)
            dict_entry = lookup.lookup_with_example(v.lemma, v.pos)
            meaning = v.translation or (dict_entry.get("gloss") if dict_entry else None)
            meaning_en = dict_entry.get("gloss_en") if dict_entry else None
            dict_example = dict_entry.get("example") if dict_entry else None

            if meaning:
                st.markdown(f"**Meaning:** {meaning}")
            if meaning_en:
                st.markdown(f"**English:** {meaning_en}")
            # Authoritative dictionary links (Van Dale, Woorden.org, Wiktionary)
            links = lookup.get_links(v.lemma)
            link_str = " · ".join(f"[{k}]({url})" for k, url in links.items())
            st.caption(f"**Look up:** {link_str}")

            # Example — prefer dictionary example (from Wiktionary) when available
            example_to_show = dict_example or ev.example_sentence
            if example_to_show:
                st.markdown(f"**Example:** *{example_to_show}*")

            # Different forms seen in this episode
            if ev.surface_forms:
                forms = [f.strip() for f in ev.surface_forms.split("|") if f.strip()]
                if len(forms) > 1:
                    st.markdown(f"**Forms in episode:** {', '.join(forms)}")
                elif forms and forms[0].lower() != v.lemma.lower():
                    st.markdown(f"**Form in episode:** {forms[0]}")

            if ev.example_timestamp is not None:
                st.caption(f"Timestamp: {format_timestamp(ev.example_timestamp)}")


def main():
    session = get_db_session()
    episodes = load_episodes(session)

    if not episodes:
        st.error("No episodes found. Run `python scripts/ingest_playlist.py` first.")
        st.stop()

    # Sync episode selection with query params (for shareable links)
    query_episode = st.query_params.get("episode")

    episode_options = {
        f"{ep.id} | {ep.published_at.strftime('%Y-%m-%d') if ep.published_at else '?'} — {ep.title[:45]}": ep.id
        for ep in episodes
    }
    # Default to episode from URL if valid
    default_index = 0
    if query_episode:
        try:
            qe = int(query_episode)
            for i, (_, eid) in enumerate(episode_options.items()):
                if eid == qe:
                    default_index = i
                    break
        except ValueError:
            pass

    st.sidebar.title("🇳🇱 Dutch News Learner")
    st.sidebar.markdown("---")

    selected_label = st.sidebar.selectbox(
        "Choose episode",
        options=list(episode_options.keys()),
        index=default_index,
        key="episode_select",
    )
    selected_id = episode_options[selected_label]

    # Load episode with data
    episode = load_episode_with_data(session, selected_id)
    if not episode:
        st.error("Episode not found.")
        st.stop()

    # Main content
    st.title(episode.title)
    pub = episode.published_at.strftime("%A, %B %d, %Y") if episode.published_at else ""
    st.caption(pub)
    st.markdown("---")

    # Video
    st.subheader("📺 Watch")
    render_video(episode.video_id)
    st.markdown("---")

    # Two columns: subtitles | vocabulary
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📝 Transcript")
        show_translation = st.checkbox(
            "Show English translation",
            value=False,
            key="show_translation",
        )
        st.caption("Click any vocabulary word to see its definition →")
        if episode.subtitle_segments:
            vocab_list = _filter_vocab(episode.episode_vocabulary or [])
            word_to_lemma = build_word_to_lemma_map(vocab_list) if vocab_list else None
            vocab_data = build_vocab_bubble_data(vocab_list) if vocab_list else None
            render_transcript_with_bubbles(
                episode.subtitle_segments,
                episode.video_id,
                word_to_lemma=word_to_lemma,
                vocab_data=vocab_data,
                show_translation=show_translation,
            )
        else:
            st.info("No subtitles for this episode.")

    with col2:
        st.subheader("📚 Vocabulary")
        vocab_list = _filter_vocab(episode.episode_vocabulary or [])
        if vocab_list:
            # Search and sort controls
            vocab_search = st.text_input(
                "Search word",
                placeholder="Type to filter (e.g. politie, kind)...",
                key="vocab_search",
            )
            sort_option = st.radio(
                "Sort by",
                options=["frequency", "alpha"],
                format_func=lambda x: "Most frequent first" if x == "frequency" else "A–Z",
                horizontal=True,
                key="vocab_sort",
            )
            st.markdown("")  # spacing
            render_vocabulary(
                vocab_list,
                search_query=vocab_search,
                sort_by=sort_option,
            )
        else:
            st.info("No vocabulary extracted. Run `python scripts/extract_vocabulary.py`.")

    # Related reading
    topics = getattr(episode, "topics", None)
    if topics and topics.strip():
        st.markdown("---")
        st.subheader("📰 Related reading")
        st.caption(
            "Read more about these topics on NOS (Dutch news)"
            + (" — filtered to ±2 days around episode date" if episode.published_at else "")
        )
        topic_list = [t.strip() for t in topics.split("|") if t.strip()]

        # Build date range for search (episode date ± 2 days)
        date_range_params = ""
        pub = episode.published_at
        if pub:
            dt = pub.date() if hasattr(pub, "date") else pub
            start = dt - timedelta(days=2)
            end = dt + timedelta(days=2)
            # Google tbs format: cdr:1,cd_min:MM/DD/YYYY,cd_max:MM/DD/YYYY
            date_range_params = f"&tbs=cdr:1,cd_min:{start.month:02d}/{start.day:02d}/{start.year},cd_max:{end.month:02d}/{end.day:02d}/{end.year}"

        for topic in topic_list:
            # Use Google search with site:nos.nl for date-filtered NOS results
            query = f"{topic} site:nos.nl"
            url = f"https://www.google.com/search?q={quote_plus(query)}{date_range_params}"
            st.markdown(f"- [{topic}]({url})")

    st.sidebar.markdown("---")
    st.sidebar.caption("Drie onderwerpen in makkelijke taal")


if __name__ == "__main__":
    main()
