#!/usr/bin/env python3
"""Research Agent -- polished Streamlit GUI with a dynamic knowledge base.

Run:
    streamlit run app.py

Features:
  * Upload your own documents (.txt/.md/.pdf) into the knowledge base.
  * Ask questions and get cited, verified answers (or an honest "not found").
  * Clear the knowledge base to start fresh.
"""
from __future__ import annotations

import glob
import os
import shutil

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # noqa: BLE001
    pass

import streamlit as st

from research_agent.config import TOP_K, has_anthropic_key, has_openai_key
from research_agent.pipeline import ResearchAgent
from research_agent.synthesize import resolve_answer_backend

st.set_page_config(page_title="Research Agent — cited answers", page_icon="📚",
                   layout="wide", initial_sidebar_state="expanded")

KB_DIR = "data/kb"          # runtime knowledge base (uploads land here)
SEED_DIR = "data/sources"   # committed sample docs used to seed KB on first run
ANSWER_BACKENDS = {"OpenAI GPT": "openai", "Claude": "claude"}
EMBED_BACKENDS = {"OpenAI embeddings": "openai"}
ACCENT = "#6C5CE7"


# --------------------------------------------------------------------------- #
# Knowledge-base helpers
# --------------------------------------------------------------------------- #
def ensure_kb() -> None:
    """Create the KB folder, seeding it with the sample docs on first run."""
    if not os.path.isdir(KB_DIR):
        os.makedirs(KB_DIR, exist_ok=True)
        for f in sorted(glob.glob(os.path.join(SEED_DIR, "*"))):
            if os.path.isfile(f):
                shutil.copy(f, os.path.join(KB_DIR, os.path.basename(f)))


def kb_files():
    return sorted(f for f in glob.glob(os.path.join(KB_DIR, "*"))
                  if os.path.isfile(f) and f.lower().endswith((".txt", ".md", ".pdf")))


def kb_signature():
    return tuple((os.path.basename(f), os.path.getsize(f)) for f in kb_files())


def clear_kb() -> None:
    if os.path.isdir(KB_DIR):
        shutil.rmtree(KB_DIR)
    os.makedirs(KB_DIR, exist_ok=True)


ensure_kb()

# --------------------------------------------------------------------------- #
# Styling
# --------------------------------------------------------------------------- #
st.markdown(f"""
<style>
#MainMenu, footer {{visibility: hidden;}}
.block-container {{padding-top: 2rem; max-width: 1150px;}}
.hero {{
  background: linear-gradient(120deg, {ACCENT} 0%, #8E7CF0 55%, #A29BFE 100%);
  padding: 26px 30px; border-radius: 18px; color: #fff; margin-bottom: 8px;
  box-shadow: 0 10px 30px rgba(108,92,231,.25);
}}
.hero h1 {{margin: 0; font-size: 1.9rem; font-weight: 800; letter-spacing:-.5px;}}
.hero p  {{margin: 6px 0 0; opacity: .95; font-size: 1.02rem;}}
.badge {{display:inline-block; padding:4px 12px; border-radius:999px; font-size:.8rem;
         font-weight:700; letter-spacing:.3px;}}
.badge-found    {{background:#e6f7ec; color:#1a7f47; border:1px solid #a6e0bd;}}
.badge-notfound {{background:#fff4e5; color:#9a5b00; border:1px solid #ffd699;}}
.chip {{display:inline-block; background:#efecfd; color:{ACCENT}; border:1px solid #d8d1fa;
        padding:2px 10px; border-radius:999px; font-size:.78rem; font-weight:600; margin:2px 4px 2px 0;}}
.chip-bad {{background:#fdeaea; color:#c0392b; border-color:#f3b7b1;}}
.answer-card {{background:#faf9ff; border:1px solid #e7e3fb; border-left:5px solid {ACCENT};
        border-radius:12px; padding:16px 20px; font-size:1.05rem; line-height:1.6;}}
.src-meta {{font-size:.8rem; color:#6b7280;}}
div.stButton > button {{border-radius:10px; font-weight:600;}}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <h1>📚 Research Agent</h1>
  <p>Ask a question over your documents — get an answer that cites every claim,
     verifies its own citations, and says so when the answer isn't in the sources.</p>
</div>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Sidebar — knowledge base + configuration
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("📁 Knowledge base")
    files = kb_files()
    st.caption(f"{len(files)} document(s) loaded")
    for f in files:
        st.write("📄 " + os.path.basename(f))

    uploads = st.file_uploader("Add documents", type=["txt", "md", "pdf"],
                               accept_multiple_files=True)
    c1, c2 = st.columns(2)
    if c1.button("➕ Add", use_container_width=True, disabled=not uploads):
        for uf in uploads:
            with open(os.path.join(KB_DIR, uf.name), "wb") as out:
                out.write(uf.getbuffer())
        st.session_state.pop("last_result", None)
        st.rerun()
    if c2.button("🗑️ Clear", use_container_width=True):
        clear_kb()
        st.session_state.pop("last_result", None)
        st.rerun()
    if st.button("↩️ Reload sample docs", use_container_width=True):
        clear_kb()
        for f in sorted(glob.glob(os.path.join(SEED_DIR, "*"))):
            if os.path.isfile(f):
                shutil.copy(f, os.path.join(KB_DIR, os.path.basename(f)))
        st.session_state.pop("last_result", None)
        st.rerun()

    st.divider()
    st.header("⚙️ Settings")
    st.write(f"{'✅' if has_openai_key() else '⚪'} OpenAI  ·  "
             f"{'✅' if has_anthropic_key() else '⚪'} Anthropic")
    answer_choice = st.selectbox("Answer model", list(ANSWER_BACKENDS), index=0)
    embed_choice = st.selectbox("Retrieval", list(EMBED_BACKENDS), index=0)


# --------------------------------------------------------------------------- #
# Build (and cache) the agent in session state; rebuild only when needed
# --------------------------------------------------------------------------- #
files = kb_files()
if not files:
    st.info("📭 The knowledge base is empty. Upload documents in the sidebar, or "
            "click **Reload sample docs** to load the built-in example.")
    st.stop()

build_key = (kb_signature(), EMBED_BACKENDS[embed_choice])
if st.session_state.get("build_key") != build_key:
    try:
        with st.spinner("Indexing knowledge base…"):
            st.session_state.agent = ResearchAgent(
                KB_DIR, embed_backend=EMBED_BACKENDS[embed_choice], answer_backend="openai")
        st.session_state.build_key = build_key
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not index the knowledge base: {exc}")
        st.stop()

agent = st.session_state.agent
# Answer backend is cheap to switch (no re-embedding).
try:
    agent.answer_backend = resolve_answer_backend(ANSWER_BACKENDS[answer_choice])
except RuntimeError as exc:
    st.sidebar.warning(str(exc))
    agent.answer_backend = resolve_answer_backend("auto")

st.markdown(f"<span class='src-meta'>🧠 {agent.describe()}</span>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Ask
# --------------------------------------------------------------------------- #
question = st.text_input("Your question",
                         placeholder="Ask something about the documents…")

if st.button("🔍  Ask", type="primary") and question.strip():
    with st.status("Working…", expanded=True) as status:
        st.write("🔎 Retrieving relevant passages…")
        st.write("🧠 Synthesising a cited answer…")
        result = agent.ask(question.strip(), k=TOP_K)
        st.write("✅ Verifying citations…")
        status.update(label="Done", state="complete")
    st.session_state.last_result = result

# --------------------------------------------------------------------------- #
# Render the last answer
# --------------------------------------------------------------------------- #
result = st.session_state.get("last_result")
if result:
    st.markdown("### Answer")
    if result["answer_found"]:
        st.markdown('<span class="badge badge-found">✔ ANSWER FOUND IN SOURCES</span>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge badge-notfound">✖ NOT IN SOURCES — declined to guess</span>',
                    unsafe_allow_html=True)
    st.markdown(f'<div class="answer-card">{result["answer"]}</div>', unsafe_allow_html=True)

    # Citations
    if result["cited_ids"]:
        chips = "".join(f'<span class="chip">S{i}</span>' for i in result["valid_ids"])
        bad = "".join(f'<span class="chip chip-bad">S{i} (unverified)</span>'
                      for i in result["hallucinated_ids"])
        ok = "✅ all citations verified" if result["citations_ok"] else "⚠️ hallucinated citation!"
        st.markdown(f"**Citations** {chips}{bad} &nbsp; {ok}", unsafe_allow_html=True)

    st.markdown("### Retrieved passages")
    for s in result["sources"]:
        used = s["id"] in result["valid_ids"]
        with st.container(border=True):
            tag = "✅ cited" if used else "not cited"
            st.markdown(
                f"<b>[S{s['id']}]</b> &nbsp;<span class='chip'>{s['source']}</span>"
                f"<span class='src-meta'>&nbsp; relevance {s['score']} · {tag}</span>",
                unsafe_allow_html=True)
            st.markdown(f"<span class='src-meta'>{s['snippet']}</span>", unsafe_allow_html=True)
