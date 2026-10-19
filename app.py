from __future__ import annotations

import json
import os

import streamlit as st

st.set_page_config(
    page_title="CampusPulse AI",
    page_icon="🎓",
    layout="wide",
)


@st.cache_resource
def get_backend():
    resource = os.getenv("AGENT_ENGINE_RESOURCE")
    if resource:
        import vertexai
        from vertexai import agent_engines

        vertexai.init(
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )
        return agent_engines.get(resource)

    from campuspulse.agent import CampusPulseAgent

    return CampusPulseAgent()


backend = get_backend()

if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("CampusPulse AI")
st.caption(
    "Агент по дедлайнам, событиям и местам кампуса. "
    "Демо-данные, источники видны в трейсе."
)

with st.sidebar:
    st.subheader("Попробуй")
    examples = [
        "Что у меня горит на этой неделе?",
        "Нужно тихое место с розеткой и кофе до вечера.",
        "Куда сходить по AI на этой неделе?",
        "Успею ли подготовить Raft и CNN? Составь план.",
    ]
    for example in examples:
        st.code(example, language=None)

    st.divider()
    mode = "Agent Engine" if os.getenv("AGENT_ENGINE_RESOURCE") else "локальный агент"
    st.caption("Режим: " + mode)
    if not (
        os.getenv("AGENT_ENGINE_RESOURCE")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GEMINI_API_KEY")
    ):
        st.warning("Задай GOOGLE_CLOUD_PROJECT или GEMINI_API_KEY.")
    if st.button("Очистить чат"):
        st.session_state.messages = []
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input(
    "Спроси про дедлайны, события или место для учёбы"
):
    history = [
        {"role": message["role"], "text": message["content"]}
        for message in st.session_state.messages
    ]
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Собираю данные кампуса..."):
            try:
                result = backend.query(message=prompt, history=history)
            except Exception as exc:
                result = {
                    "answer": f"Ошибка конфигурации: {type(exc).__name__}: {exc}",
                    "trace": [],
                    "sources": [],
                }

        st.markdown(result.get("answer", ""))

        if result.get("sources"):
            st.caption("Источники: " + ", ".join(result["sources"]))

        with st.expander("Reasoning loop"):
            for step in result.get("trace", []):
                if step.get("step") == "tool":
                    st.markdown(
                        f"**Tool:** {step.get('tool')} · args: "
                        f"{json.dumps(step.get('args', {}), ensure_ascii=False)}"
                    )
                    st.json(step.get("result"))
                else:
                    st.caption(step.get("text", ""))

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result.get("answer", ""),
        }
    )
