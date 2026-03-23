"""
Dutch News Learner — Streamlit learning interface.

Episode viewer with embedded video, subtitle transcript, and vocabulary list.
Click words in the transcript to jump to their definition.
Run with: streamlit run app/main.py
"""

import json
import re
import sys
import uuid
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote_plus

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import streamlit as st
from sqlalchemy.orm import joinedload

from src.api.session import get_or_create_session
from src.dictionary import get_lookup
from src.models import (
    Episode,
    EpisodeVocabulary,
    SubtitleSegment,
    UserVocabulary,
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

# Lemmas to exclude from vocabulary (show names, etc.)
EXCLUDE_LEMMAS = {"journaal"}


def fix_concatenated_spaces(text: str) -> str:
    """
    Fix missing spaces in Dutch text from search snippets (e.g. "deverkiezingenheeft" -> "de verkiezingen heeft").
    DuckDuckGo and similar sources sometimes return concatenated words.
    """
    if not text or not isinstance(text, str):
        return text
    # Insert space after short Dutch articles when followed by a word (2+ letters)
    text = re.sub(r"\bde(?=[a-z]{2,})", r"de ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bhet(?=[a-z]{2,})", r"het ", text, flags=re.IGNORECASE)
    text = re.sub(r"\been(?=[a-z]{2,})", r"een ", text, flags=re.IGNORECASE)
    # Insert space before common Dutch function words when concatenated (lowercase letter before)
    for word in ("heeft", "hebben", "is", "zijn", "van", "op", "te", "dat", "die", "voor", "met", "naar", "uit"):
        text = re.sub(rf"([a-z])({word})\b", rf"\1 \2", text)
    return text


@st.cache_resource(ttl=3600)
def get_db_engine():
    """Create database engine. Cached for 1 hour. Use get_db_session() for a per-request session."""
    from src.models import _migrate_schema

    engine = get_engine()
    _migrate_schema(engine)
    return engine


def get_db_session():
    """Create a fresh session for this request. Close it when done to return connections to the pool."""
    return get_session(get_db_engine())


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


def load_user_vocab_statuses(session, user_id=1):
    """Load all vocabulary statuses for a user as {vocabulary_id: status}."""
    rows = session.query(UserVocabulary).filter_by(user_id=user_id).all()
    return {row.vocabulary_id: row.status for row in rows}


def set_vocab_status(session, vocabulary_id, status, user_id=1):
    """Set a word's status (known/learning/new) for a user."""
    row = (
        session.query(UserVocabulary)
        .filter_by(user_id=user_id, vocabulary_id=vocabulary_id)
        .first()
    )
    if row:
        row.status = status
    else:
        row = UserVocabulary(
            user_id=user_id, vocabulary_id=vocabulary_id, status=status
        )
        session.add(row)
    session.commit()


def format_timestamp(seconds):
    """Convert seconds to MM:SS."""
    if seconds is None:
        return ""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


_SENTENCE_ENDERS = re.compile(r'[.!?]$')


def merge_segments_into_sentences(segments):
    """
    Merge consecutive subtitle segments into sentence-level groups.

    Groups segments until one ends with sentence-ending punctuation (. ! ?).
    Returns list of dicts: {start_time, text, translation_en, end_time}.
    """
    sorted_segs = sorted(segments, key=lambda s: s.start_time)
    if not sorted_segs:
        return []

    merged = []
    buf_texts = []
    buf_translations = []
    buf_start = None

    for seg in sorted_segs:
        text = seg.text.strip()
        if not text:
            continue
        if buf_start is None:
            buf_start = seg.start_time
        buf_texts.append(text)
        tr = getattr(seg, "translation_en", None) or ""
        if tr:
            buf_translations.append(tr)

        if _SENTENCE_ENDERS.search(text):
            merged.append({
                "start_time": buf_start,
                "text": " ".join(buf_texts),
                "translation_en": " ".join(buf_translations),
            })
            buf_texts = []
            buf_translations = []
            buf_start = None

    # Flush remaining buffer (subtitle didn't end with punctuation)
    if buf_texts:
        merged.append({
            "start_time": buf_start,
            "text": " ".join(buf_texts),
            "translation_en": " ".join(buf_translations),
        })

    return merged


def render_video(video_id):
    """Embed YouTube video with JS API enabled for in-page seeking."""
    st.markdown(
        f'<iframe id="yt-player" width="100%" height="400" '
        f'src="https://www.youtube.com/embed/{video_id}?enablejsapi=1" '
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
        gloss_nl = v.translation or (dict_entry.get("gloss") if dict_entry else None)
        gloss_en = dict_entry.get("gloss_en") if dict_entry else None
        dict_example = dict_entry.get("example") if dict_entry else None
        example = dict_example or ev.example_sentence
        meaning = gloss_nl or gloss_en or "(no definition)"
        forms = []
        if ev.surface_forms:
            forms = [f.strip() for f in ev.surface_forms.split("|") if f.strip()]
        links = lookup.get_links(v.lemma)
        entry = {
            "pos": v.pos or "",
            "lemma": v.lemma,
            "meaning": meaning,
            "meaning_en": gloss_en or "",
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
    merged = merge_segments_into_sentences(segments)
    lines = []
    for sent in merged:
        ts = format_timestamp(sent["start_time"])
        yt_url = f"https://www.youtube.com/watch?v={video_id}&t={int(sent['start_time'])}s"
        text = sent["text"]
        if word_to_lemma:
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
            "start_time": sent["start_time"],
            "text": text,
            "translation_en": sent["translation_en"] if show_translation else "",
        })

    vocab_json = json.dumps(vocab_data).replace("</", "\\u003c/")  # Avoid breaking script tag
    lines_json = json.dumps(lines).replace("</", "\\u003c/")

    return f"""
<style>
.vocab-word {{ color:#1f77b4; text-decoration:underline; cursor:pointer; }}
.vocab-word:hover {{ color:#1565c0; }}
.bubble {{ display:none; position:fixed; z-index:9999; background:#fff; border:1px solid #ccc;
  border-radius:8px; box-shadow:0 4px 12px rgba(0,0,0,0.15); padding:12px 16px; max-width:min(360px, 90vw);
  max-height:60vh; overflow-y:auto;
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
.transcript-ts a {{ color:inherit; cursor:pointer; }}
.transcript-ts a:hover {{ text-decoration:underline; }}
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
      if (e.lemma && e.lemma.toLowerCase() !== displayLemma.toLowerCase()) {{
        html += '<div class="bubble-section"><strong>' + (e.pos === 'VERB' ? 'Infinitive' : 'Base form') + ':</strong> ' + e.lemma + '</div>';
      }}
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
    bubble.classList.add('show');

    var rect = ev.target.getBoundingClientRect();
    var bh = bubble.offsetHeight;
    var spaceBelow = window.innerHeight - rect.bottom - 16;
    var spaceAbove = rect.top - 16;

    // Place below the word if there's room, otherwise flip above
    if (spaceBelow >= bh || spaceBelow >= spaceAbove) {{
      bubble.style.top = (rect.bottom + 8) + 'px';
    }} else {{
      bubble.style.top = Math.max(8, rect.top - bh - 8) + 'px';
    }}
    bubble.style.left = Math.max(8, Math.min(rect.left, window.innerWidth - Math.min(360, window.innerWidth * 0.9) - 16)) + 'px';
    overlay.style.display = 'block';
  }}

  function hideBubble() {{
    bubble.classList.remove('show');
    overlay.style.display = 'none';
  }}

  document.getElementById('bubble-close').onclick = hideBubble;
  overlay.onclick = hideBubble;

  // Seek the YouTube player embedded in the parent Streamlit page.
  // st.components.v1.html() iframes have allow-same-origin, so we can
  // access window.parent.document to find the YouTube iframe by ID,
  // then use YouTube's postMessage protocol to seek + play.
  function seekVideo(seconds) {{
    try {{
      var ytFrame = window.parent.document.getElementById('yt-player');
      if (ytFrame && ytFrame.contentWindow) {{
        ytFrame.contentWindow.postMessage(JSON.stringify({{
          event: 'command', func: 'seekTo', args: [seconds, true]
        }}), '*');
        ytFrame.contentWindow.postMessage(JSON.stringify({{
          event: 'command', func: 'playVideo', args: []
        }}), '*');
        return true;
      }}
    }} catch(e) {{}}
    return false;
  }}

  root.addEventListener('click', function(ev) {{
    // Handle timestamp clicks — seek embedded video
    var tsLink = ev.target.closest('.ts-link');
    if (tsLink) {{
      ev.preventDefault();
      var time = parseFloat(tsLink.getAttribute('data-time'));
      if (!seekVideo(time)) {{
        window.open(tsLink.getAttribute('data-url'), '_blank');
      }}
      return;
    }}
    // Handle vocab word clicks — show definition bubble
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
    var html = '<span class="transcript-ts"><a href="#" class="ts-link" data-time="' + line.start_time + '" data-url="' + line.yt_url + '">' + line.ts + '</a></span> ' + line.text;
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
        merged = merge_segments_into_sentences(segments)
        for sent in merged:
            ts = format_timestamp(sent["start_time"])
            yt_url = f"https://www.youtube.com/watch?v={video_id}&t={int(sent['start_time'])}s"
            st.markdown(f"**[{ts}]({yt_url})** {sent['text']}")
            if show_translation and sent["translation_en"]:
                st.caption(sent["translation_en"])
            st.markdown("")
        return
    html = _transcript_bubble_html(segments, video_id, word_to_lemma, vocab_data, show_translation=show_translation)
    merged_count = len(merge_segments_into_sentences(segments))
    estimated_height = 150 + merged_count * 40
    st.components.v1.html(html, height=min(800, estimated_height), scrolling=True)


DEFAULT_VOCAB_LIMIT = 20


STATUS_LABELS = {"new": "New", "learning": "Learning", "known": "Known"}


@st.cache_data(ttl=3600)
def _cached_dict_lookup(lemma: str, pos: str | None):
    """Cache dictionary lookups to avoid repeated SQLite queries on fragment rerun."""
    return get_lookup().lookup_with_example(lemma, pos)


@st.cache_data(ttl=3600)
def _get_episode_vocab_data(episode_id: int):
    """
    Load episode vocabulary as serializable dicts. Cached so status changes
    skip the heavy Postgres episode load — we only reload statuses.
    """
    session = get_db_session()
    try:
        episode = load_episode_with_data(session, episode_id)
        if not episode:
            return []
        vocab_list = _filter_vocab(episode.episode_vocabulary or [])
        return [
            {
                "vocabulary_id": ev.vocabulary_item.id,
                "lemma": ev.vocabulary_item.lemma,
                "pos": ev.vocabulary_item.pos,
                "occurrence_count": ev.occurrence_count or 0,
                "example_sentence": ev.example_sentence,
                "surface_forms": ev.surface_forms,
                "example_timestamp": ev.example_timestamp,
                "translation": ev.vocabulary_item.translation,
            }
            for ev in vocab_list
        ]
    finally:
        session.close()


@st.fragment
def _render_vocabulary_fragment(episode_id):
    """
    Fragment: vocabulary list with status buttons. Reruns only this block when
    a status button is clicked, avoiding full-app freeze.
    """
    if not episode_id:
        return
    with st.spinner("Updating…"):
        vocab_data = _get_episode_vocab_data(episode_id)
        if not vocab_data:
            return

        session = get_db_session()
        try:
            user_id = st.session_state.get("user_id", 1)
            statuses = load_user_vocab_statuses(session, user_id)
            search_query = st.session_state.get("vocab_search", "").strip()
            sort_by = st.session_state.get("vocab_sort", "frequency")
            known_filter = st.session_state.get("vocab_known_filter", "hide")
            hide_known = known_filter == "hide"
            show_all = st.session_state.get("vocab_show_all", False)

            if hide_known:
                vocab_data = [
                    v for v in vocab_data
                    if statuses.get(v["vocabulary_id"], "new") != "known"
                ]
            if search_query:
                q = search_query.lower()
                vocab_data = [v for v in vocab_data if q in v["lemma"].lower()]
            if sort_by == "alpha":
                vocab_data = sorted(vocab_data, key=lambda v: v["lemma"].lower())
            else:
                vocab_data = sorted(
                    vocab_data,
                    key=lambda v: v["occurrence_count"],
                    reverse=True,
                )

            total = len(vocab_data)
            is_searching = bool(search_query)
            display_vocab = vocab_data if (show_all or is_searching) else vocab_data[:DEFAULT_VOCAB_LIMIT]

            lookup = get_lookup()
            for v in display_vocab:
                vid = v["vocabulary_id"]
                count = v["occurrence_count"]
                current_status = statuses.get(vid, "new")
                status_icon = STATUS_ICONS.get(current_status, "")
                label = f"{status_icon} **{v['lemma']}** ({v['pos']}) — {count}×" if status_icon else f"**{v['lemma']}** ({v['pos']}) — {count}×"

                with st.expander(label):
                    dict_entry = _cached_dict_lookup(v["lemma"], v["pos"])
                    gloss_nl = v["translation"] or (dict_entry.get("gloss") if dict_entry else None)
                    gloss_en = dict_entry.get("gloss_en") if dict_entry else None
                    dict_example = dict_entry.get("example") if dict_entry else None

                    if gloss_nl:
                        st.markdown(f"**Meaning:** {gloss_nl}")
                    if gloss_en:
                        st.markdown(f"**English:** {gloss_en}")
                    if not gloss_nl and not gloss_en:
                        st.caption("No definition available.")
                    links = lookup.get_links(v["lemma"])
                    link_str = " · ".join(f"[{k}]({url})" for k, url in links.items())
                    st.caption(f"**Look up:** {link_str}")

                    example_to_show = dict_example or v.get("example_sentence")
                    if example_to_show:
                        st.markdown(f"**Example:** *{example_to_show}*")

                    if v.get("surface_forms"):
                        forms = [f.strip() for f in v["surface_forms"].split("|") if f.strip()]
                        if len(forms) > 1:
                            st.markdown(f"**Forms in episode:** {', '.join(forms)}")
                        elif forms and forms[0].lower() != v["lemma"].lower():
                            st.markdown(f"**Form in episode:** {forms[0]}")

                    if v.get("example_timestamp") is not None:
                        st.caption(f"Timestamp: {format_timestamp(v['example_timestamp'])}")

                    btn_cols = st.columns(3)
                    for i, (status_val, status_label) in enumerate(STATUS_LABELS.items()):
                        with btn_cols[i]:
                            disabled = current_status == status_val
                            if st.button(
                                f"{'● ' if disabled else ''}{status_label}",
                                key=f"status_{vid}_{status_val}",
                                disabled=disabled,
                                use_container_width=True,
                            ):
                                set_vocab_status(session, vid, status_val, user_id)
                                # Fragment auto-reruns; no st.rerun() needed

            if total - len(display_vocab) > 0:
                st.caption(f"Showing {len(display_vocab)} of {total} words.")
        finally:
            session.close()


STATUS_ICONS = {"new": "", "learning": "📖", "known": "✅"}


def render_vocabulary(episode_vocab_list, session=None, statuses=None,
                      search_query="", sort_by="frequency",
                      show_all=False, hide_known=True):
    """
    Render vocabulary list with search, sort, status buttons, and known-word filtering.

    Args:
        episode_vocab_list: List of EpisodeVocabulary objects.
        session: DB session for persisting status changes.
        statuses: Dict of {vocabulary_id: status} for the current user.
        search_query: Filter by lemma (case-insensitive substring).
        sort_by: "frequency" (most common first) or "alpha" (A-Z).
        show_all: If True, display all words instead of the default limit.
        hide_known: If True, filter out words marked as "known".
    """
    lookup = get_lookup()
    statuses = statuses or {}

    if hide_known:
        episode_vocab_list = [
            ev for ev in episode_vocab_list
            if statuses.get(ev.vocabulary_item.id, "new") != "known"
        ]

    if search_query:
        q = search_query.lower().strip()
        episode_vocab_list = [
            ev for ev in episode_vocab_list
            if q in ev.vocabulary_item.lemma.lower()
        ]

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

    total = len(sorted_vocab)
    is_searching = bool(search_query)
    display_vocab = sorted_vocab if (show_all or is_searching) else sorted_vocab[:DEFAULT_VOCAB_LIMIT]

    for ev in display_vocab:
        v = ev.vocabulary_item
        count = ev.occurrence_count if ev.occurrence_count is not None else 0
        current_status = statuses.get(v.id, "new")
        status_icon = STATUS_ICONS.get(current_status, "")
        label = f"{status_icon} **{v.lemma}** ({v.pos}) — {count}×" if status_icon else f"**{v.lemma}** ({v.pos}) — {count}×"

        with st.expander(label):
            dict_entry = lookup.lookup_with_example(v.lemma, v.pos)
            gloss_nl = v.translation or (dict_entry.get("gloss") if dict_entry else None)
            gloss_en = dict_entry.get("gloss_en") if dict_entry else None
            dict_example = dict_entry.get("example") if dict_entry else None

            if gloss_nl:
                st.markdown(f"**Meaning:** {gloss_nl}")
            if gloss_en:
                st.markdown(f"**English:** {gloss_en}")
            if not gloss_nl and not gloss_en:
                st.caption("No definition available.")
            links = lookup.get_links(v.lemma)
            link_str = " · ".join(f"[{k}]({url})" for k, url in links.items())
            st.caption(f"**Look up:** {link_str}")

            example_to_show = dict_example or ev.example_sentence
            if example_to_show:
                st.markdown(f"**Example:** *{example_to_show}*")

            if ev.surface_forms:
                forms = [f.strip() for f in ev.surface_forms.split("|") if f.strip()]
                if len(forms) > 1:
                    st.markdown(f"**Forms in episode:** {', '.join(forms)}")
                elif forms and forms[0].lower() != v.lemma.lower():
                    st.markdown(f"**Form in episode:** {forms[0]}")

            if ev.example_timestamp is not None:
                st.caption(f"Timestamp: {format_timestamp(ev.example_timestamp)}")

            # Status buttons
            if session:
                btn_cols = st.columns(3)
                for i, (status_val, status_label) in enumerate(STATUS_LABELS.items()):
                    with btn_cols[i]:
                        disabled = current_status == status_val
                        if st.button(
                            f"{'● ' if disabled else ''}{status_label}",
                            key=f"status_{v.id}_{status_val}",
                            disabled=disabled,
                            use_container_width=True,
                        ):
                            set_vocab_status(session, v.id, status_val)
                            st.rerun()

    hidden_count = total - len(display_vocab)
    if hidden_count > 0:
        st.caption(f"Showing {len(display_vocab)} of {total} words.")


def _render_tab_transcript(episode, vocab_list):
    """Render the Transcript tab: translation toggle + clickable transcript."""
    show_translation = st.checkbox(
        "Show English translation",
        value=False,
        key="show_translation",
    )
    st.caption("Click any underlined word to see its definition.")
    if episode.subtitle_segments:
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


def _render_tab_vocabulary(vocab_list, session, episode_id=None):
    """Render the Vocabulary tab: search, sort, known-words filter, status buttons."""
    if not vocab_list:
        st.info("No vocabulary extracted. Run `python scripts/extract_vocabulary.py`.")
        return

    st.caption(
        "💡 Your progress is saved per session (URL). Bookmark your link to keep the same vocabulary status."
    )

    col_search, col_sort = st.columns([2, 1])
    with col_search:
        st.text_input(
            "Search word",
            placeholder="Type to filter (e.g. politie, kind)...",
            key="vocab_search",
            label_visibility="collapsed",
        )
    with col_sort:
        st.radio(
            "Sort",
            options=["frequency", "alpha"],
            format_func=lambda x: "Most frequent" if x == "frequency" else "A-Z",
            horizontal=True,
            key="vocab_sort",
            label_visibility="collapsed",
        )

    col_filter, col_show = st.columns([1, 1])
    with col_filter:
        st.radio(
            "Filter",
            options=["hide", "show"],
            format_func=lambda x: "Hide known" if x == "hide" else "Show all",
            horizontal=True,
            key="vocab_known_filter",
        )
    with col_show:
        st.checkbox(
            f"Show all {len(vocab_list)} words",
            value=False,
            key="vocab_show_all",
        )

    _render_vocabulary_fragment(episode_id or 0)


def _render_tab_related_reading(episode):
    """Render the Related Reading tab: NOS articles grouped by topic."""
    topics = getattr(episode, "topics", None)
    if not topics or not topics.strip():
        st.info(
            "No topics extracted for this episode. "
            "Run `python scripts/extract_topics.py` to generate them."
        )
        return

    # Try to load pre-fetched articles
    articles_json = getattr(episode, "related_articles", None)
    articles = []
    if articles_json:
        try:
            articles = json.loads(articles_json)
        except (json.JSONDecodeError, TypeError):
            pass

    topic_list = [t.strip() for t in topics.split("|") if t.strip()]

    if articles:
        st.caption(
            "NOS articles related to this episode's topics"
            + (" — from ±7 days around episode date" if episode.published_at else "")
        )
        # Group articles by topic
        by_topic: dict[str, list] = {}
        for a in articles:
            t = a.get("topic", "")
            by_topic.setdefault(t, []).append(a)

        for topic in topic_list:
            st.markdown(f"**{topic}**")
            topic_articles = by_topic.get(topic, [])
            if topic_articles:
                for a in topic_articles:
                    title = fix_concatenated_spaces(a.get("title", topic))
                    url = a.get("url", "")
                    snippet = fix_concatenated_spaces(a.get("snippet", "") or "")
                    st.markdown(f"- [{title}]({url})")
                    if snippet:
                        st.caption(snippet)
            else:
                st.caption("No articles found for this topic.")
            st.markdown("")
    else:
        # Fallback: Google search links (when articles haven't been fetched yet)
        st.caption(
            "Read more about these topics on NOS (Dutch news)"
            + (" — filtered to ±2 days around episode date" if episode.published_at else "")
        )
        date_range_params = ""
        pub = episode.published_at
        if pub:
            dt = pub.date() if hasattr(pub, "date") else pub
            start = dt - timedelta(days=2)
            end = dt + timedelta(days=2)
            date_range_params = (
                f"&tbs=cdr:1,cd_min:{start.month:02d}/{start.day:02d}/{start.year}"
                f",cd_max:{end.month:02d}/{end.day:02d}/{end.year}"
            )

        for topic in topic_list:
            query = f"{topic} site:nos.nl"
            url = f"https://www.google.com/search?q={quote_plus(query)}{date_range_params}"
            st.markdown(f"- [{topic}]({url})")

        st.caption(
            "Run `python scripts/fetch_related_articles.py` to show actual article titles."
        )


def main():
    session = get_db_session()
    try:
        # Ensure session token in URL (Phase 6E anonymous sessions)
        token = st.query_params.get("u", "").strip()
        if not token or len(token) != 36 or token.count("-") != 4:
            new_token = str(uuid.uuid4())
            params = dict(st.query_params)
            params["u"] = new_token
            st.query_params.update(params)
            st.rerun()

        user_id = get_or_create_session(session, token)
        st.session_state["user_id"] = user_id

        episodes = load_episodes(session)

        if not episodes:
            st.error("No episodes found. Run `python scripts/ingest_playlist.py` first.")
            st.stop()

        # Sync episode selection with query params (for shareable links)
        query_episode = st.query_params.get("episode")

        episode_options = {
            f"{ep.published_at.strftime('%Y-%m-%d') if ep.published_at else '?'} — {ep.title[:45]}": ep.id
            for ep in episodes
        }
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

        # --- Sidebar ---
        st.sidebar.title("🇳🇱 Dutch News Learner")
        st.sidebar.markdown("---")
        selected_label = st.sidebar.selectbox(
            "Choose episode",
            options=list(episode_options.keys()),
            index=default_index,
            key="episode_select",
        )
        selected_id = episode_options[selected_label]
        st.sidebar.markdown("---")
        st.sidebar.caption("Drie onderwerpen in makkelijke taal")
        st.sidebar.markdown("[☕ Buy me a coffee](https://buymeacoffee.com/lilttc)")

        # --- Load episode data ---
        episode = load_episode_with_data(session, selected_id)
        if not episode:
            st.error("Episode not found.")
            st.stop()

        vocab_list = _filter_vocab(episode.episode_vocabulary or [])

        # --- Header: title + date ---
        st.title(episode.title)
        if episode.published_at:
            st.caption(episode.published_at.strftime("%A, %B %d, %Y"))

        # --- Video (always visible) ---
        render_video(episode.video_id)

        # --- Tabbed content below the video ---
        tab_transcript, tab_vocabulary, tab_reading = st.tabs([
            "📝 Transcript",
            f"📚 Vocabulary ({len(vocab_list)})",
            "📰 Related Reading",
        ])

        with tab_transcript:
            _render_tab_transcript(episode, vocab_list)

        with tab_vocabulary:
            _render_tab_vocabulary(vocab_list, session, episode_id=selected_id)

        with tab_reading:
            _render_tab_related_reading(episode)
    finally:
        session.close()


if __name__ == "__main__":
    main()
