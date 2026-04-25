"""
# Реализован визуальный интерфейс сервиса
Streamlit-интерфейс для AI Web.

Использует 5+ эндпоинтов API:
  /health, /users, /users/{id}/sessions, /chat, /chat/async,
  /tasks/{id}, /classify, /users/{id}/sessions/{sid}/messages

# UX асинхронности — спиннеры + polling для фоновых задач
# Обработка сбоев — красивые уведомления при 503/connection errors
# Визуальная репрезентация — графики latency и распределения intents
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

from ui.api_client import APIClient

st.set_page_config(page_title="AI Web", page_icon="🤖", layout="wide")

api = APIClient()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def safe_call(fn, *args, spinner_text: str = "Working…", **kwargs):
    """# Обработка сбоев — любой вызов API обёрнут в понятное сообщение."""
    try:
        with st.spinner(spinner_text):
            return fn(*args, **kwargs)
    except httpx.ConnectError:
        st.error("🚫 Cannot reach API. The service may be starting up. Try again shortly.")
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code == 503:
            st.error("⚠️ Сервис временно недоступен (503). Попробуйте через минуту.")
        elif code == 404:
            st.warning(f"Not found: {e.response.text[:200]}")
        elif code == 422:
            st.warning(f"Validation error: {e.response.json().get('error', {}).get('details')}")
        else:
            st.error(f"API error {code}: {e.response.text[:300]}")
    except httpx.TimeoutException:
        st.error("⏱️ Request timed out.")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
    return None


def init_state() -> None:
    st.session_state.setdefault("latency_log", [])  # list of {time, ms, model}
    st.session_state.setdefault("intent_log", [])   # list of {label, confidence}
    st.session_state.setdefault("user_id", None)
    st.session_state.setdefault("session_id", None)


init_state()

# ------------------------------------------------------------------
# Sidebar: health + user / session selection
# ------------------------------------------------------------------
st.sidebar.title("🤖 AI Web")

with st.sidebar.expander("⚙️ Health", expanded=False):
    h = safe_call(api.health, spinner_text="Checking…")
    if h:
        dot = {"ok": "🟢", "degraded": "🟡", "down": "🔴"}.get(h["status"], "⚪")
        st.markdown(f"**Overall:** {dot} `{h['status']}`")
        for name, comp in h["components"].items():
            d = {"ok": "🟢", "degraded": "🟡", "down": "🔴"}[comp["status"]]
            st.markdown(f"- {d} `{name}` {comp.get('detail') or ''}")

st.sidebar.markdown("---")
st.sidebar.subheader("👤 User")

users = safe_call(api.list_users, spinner_text="Loading users…") or []
user_options = {u["name"]: u["id"] for u in users}

col_u1, col_u2 = st.sidebar.columns([3, 1])
with col_u1:
    picked = st.selectbox(
        "Select user",
        options=["(none)"] + list(user_options.keys()),
        label_visibility="collapsed",
    )
with col_u2:
    if st.button("➕", help="Create new user"):
        st.session_state["show_user_modal"] = True

if picked != "(none)":
    st.session_state["user_id"] = user_options[picked]

if st.session_state.get("show_user_modal"):
    with st.sidebar.form("new_user"):
        new_name = st.text_input("Name")
        new_email = st.text_input("Email (optional)")
        if st.form_submit_button("Create"):
            u = safe_call(api.create_user, new_name, new_email or None,
                          spinner_text="Creating user…")
            if u:
                st.success(f"User #{u['id']} created")
                st.session_state["show_user_modal"] = False
                st.rerun()

# Sessions
user_id = st.session_state.get("user_id")
if user_id:
    st.sidebar.markdown("---")
    st.sidebar.subheader("💬 Sessions")
    sessions = safe_call(api.list_sessions, user_id, spinner_text="Loading sessions…") or []
    sess_options = {f"[{s['id']}] {s['title']}": s["id"] for s in sessions}
    pick_s = st.sidebar.selectbox(
        "Select session",
        options=["(none)"] + list(sess_options.keys()),
        label_visibility="collapsed",
    )
    if pick_s != "(none)":
        st.session_state["session_id"] = sess_options[pick_s]

    with st.sidebar.form("new_session"):
        new_title = st.text_input("New session title", "New chat")
        if st.form_submit_button("Create session"):
            s = safe_call(api.create_session, user_id, new_title,
                          spinner_text="Creating session…")
            if s:
                st.session_state["session_id"] = s["id"]
                st.rerun()

# ------------------------------------------------------------------
# Main area: tabs
# ------------------------------------------------------------------
tab_chat, tab_async, tab_classify, tab_analytics = st.tabs(
    ["💬 Chat (sync)", "⏳ Chat (async queue)", "🏷️ Classify intent", "📈 Analytics"]
)

session_id = st.session_state.get("session_id")


# -------- Tab 1: Sync chat --------
with tab_chat:
    st.header("Synchronous chat")
    st.caption("Request goes straight to the model. Good for short prompts.")

    if not session_id:
        st.info("Pick or create a session in the sidebar.")
    else:
        # История сообщений
        msgs = safe_call(api.get_messages, user_id, session_id,
                         spinner_text="Loading history…") or []
        for m in msgs:
            with st.chat_message(m["role"]):
                st.write(m["content"])

        prompt = st.chat_input("Type your message…")
        c1, c2 = st.columns(2)
        creativity = c1.slider("Creativity", 0.0, 1.0, 0.7, 0.05)
        max_tokens = c2.slider("Max new tokens", 16, 1024, 256, 16)

        if prompt:
            with st.chat_message("user"):
                st.write(prompt)
            reply = safe_call(
                api.chat_sync,
                session_id, prompt, creativity, max_tokens,
                spinner_text="🧠 Generating…",
            )
            if reply:
                with st.chat_message("assistant"):
                    st.write(reply["content"])
                    st.caption(
                        f"model: `{reply['model']}` · latency: {reply['duration_ms']:.0f} ms"
                    )
                # Для графиков
                st.session_state["latency_log"].append(
                    {"time": time.time(), "ms": reply["duration_ms"], "model": reply["model"]}
                )


# -------- Tab 2: Async (Celery) --------
with tab_async:
    st.header("Async chat via Celery queue")
    st.caption(
        "Heavy prompts are queued, the API returns 202 + task_id, "
        "UI polls /tasks/{id} until it's done."
    )
    if not session_id:
        st.info("Pick or create a session in the sidebar.")
    else:
        prompt_a = st.text_area("Prompt", "Write a 200-word summary of transformer attention.")
        ca, cb = st.columns(2)
        creativity_a = ca.slider("Creativity", 0.0, 1.0, 0.7, 0.05, key="c_async")
        max_tokens_a = cb.slider("Max new tokens", 16, 1024, 256, 16, key="t_async")

        if st.button("Submit to queue", type="primary"):
            submit = safe_call(
                api.chat_async,
                session_id, prompt_a, creativity_a, max_tokens_a,
                spinner_text="Submitting…",
            )
            if submit:
                task_id = submit["task_id"]
                st.success(f"Queued. task_id = `{task_id}`")

                # Polling с прогрессом
                progress = st.progress(0, text="pending")
                status_box = st.empty()
                result_box = st.empty()

                for i in range(60):  # до 60 * 1s = 60 сек
                    time.sleep(1)
                    try:
                        t = api.get_task(task_id)
                    except Exception as e:
                        status_box.error(f"Cannot fetch task: {e}")
                        break
                    status_box.info(f"Status: `{t['status']}`")
                    progress.progress(min((i + 1) * 2, 95), text=t["status"])
                    if t["status"] == "success":
                        progress.progress(100, text="done")
                        result_box.success(t["result"])
                        break
                    if t["status"] == "failed":
                        result_box.error(f"Task failed: {t.get('error')}")
                        break
                else:
                    status_box.warning("Timed out waiting for task.")


# -------- Tab 3: Classify --------
with tab_classify:
    st.header("Intent classifier (own ONNX model)")
    st.caption("TF-IDF + LogisticRegression, exported to ONNX, served via onnxruntime.")
    text = st.text_input("Text to classify",
                         "I can't log in to my account, please help")
    if st.button("Classify"):
        r = safe_call(api.classify, text, spinner_text="Running ONNX inference…")
        if r:
            st.metric("Predicted label", r["label"], f"{r['confidence']*100:.1f}%")
            # # Визуальная репрезентация — bar-chart вероятностей
            df = pd.DataFrame(
                {"label": list(r["all_scores"].keys()), "score": list(r["all_scores"].values())}
            )
            fig = px.bar(df.sort_values("score"), x="score", y="label",
                         orientation="h", title="Class probabilities")
            st.plotly_chart(fig, use_container_width=True)
            st.session_state["intent_log"].append(
                {"label": r["label"], "confidence": r["confidence"]}
            )


# -------- Tab 4: Analytics --------
with tab_analytics:
    st.header("Analytics (session)")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("LLM latency (this session)")
        lat = st.session_state["latency_log"]
        if lat:
            df = pd.DataFrame(lat)
            df["n"] = range(1, len(df) + 1)
            fig = px.line(df, x="n", y="ms", markers=True,
                          title="ms per request", hover_data=["model"])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No requests yet — run a sync chat first.")

    with col2:
        st.subheader("Intent distribution")
        ints = st.session_state["intent_log"]
        if ints:
            df2 = pd.DataFrame(ints)
            counts = df2["label"].value_counts().reset_index()
            counts.columns = ["label", "count"]
            fig = px.pie(counts, names="label", values="count",
                         title="Predicted intents")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No classifications yet.")
