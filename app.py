import streamlit as st
from dotenv import load_dotenv

from agent_demo import DemoConfigurationError, build_agent_workflow, format_agent_trace
from src.evidence import format_evidence_citation


DEFAULT_PDF = "data/raw/城市轨道交通工程设计标准.pdf"

load_dotenv()
st.set_page_config(page_title="工程规范 Agentic RAG", layout="wide")


@st.cache_resource
def load_agent_workflow(pdf_path: str, index_dir: str):
    return build_agent_workflow(pdf_path=pdf_path, index_dir=index_dir)


if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title("工程规范 Agentic RAG")
st.caption("Hybrid Retrieval + Evidence Sufficiency + bounded retry/refusal")

with st.sidebar:
    st.header("配置")
    pdf_path = st.text_input("PDF 路径", value=DEFAULT_PDF)
    index_dir = st.text_input("索引目录", value=".rag_index")
    if st.button("清空对话"):
        st.session_state.chat_history = []
        st.rerun()

try:
    workflow = load_agent_workflow(pdf_path, index_dir)
except DemoConfigurationError as exc:
    st.error(f"配置错误：{exc}")
    st.stop()
except (FileNotFoundError, ValueError) as exc:
    st.error(f"初始化失败：{exc}")
    st.stop()

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

query = st.chat_input("请输入你的问题，例如：车站发生火灾时消防联动如何执行？")

if query:
    st.session_state.chat_history.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    response = workflow.run(query)
    st.session_state.chat_history.append({"role": "assistant", "content": response.answer})

    with st.chat_message("assistant"):
        st.markdown(response.answer)

        with st.expander("Evidence", expanded=True):
            if response.state.evidences:
                for evidence in response.state.evidences:
                    st.markdown(f"**{format_evidence_citation(evidence)}**")
                    st.caption(
                        f"content_type={evidence.content_type} | "
                        f"rerank_score={evidence.rerank_score or 0:.4f}"
                    )
                    st.write(evidence.text)
                    st.divider()
            else:
                st.write("无")

            validation = response.state.citation_validation
            if validation is not None and not validation.valid:
                st.warning(f"引用校验错误：{validation.errors}")

        with st.expander("Agent Trace", expanded=False):
            for step in format_agent_trace(response):
                st.code(step, language=None)
            st.write(f"retry_count: {response.state.retry_count}")
            st.write(f"final_action: {response.state.final_action}")
            if response.state.missing_requirements:
                st.write("missing_requirements:")
                for requirement in response.state.missing_requirements:
                    st.write(f"- {requirement}")
