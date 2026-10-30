import streamlit as st
import logging
from uuid import uuid4
from dotenv import load_dotenv

from src.application import build_agent_workflow
from src.config import AppConfig, ConfigurationError
from src.evidence import format_evidence_citation
from src.presentation import format_agent_trace, present_agent_response


logger = logging.getLogger(__name__)


load_dotenv()
st.set_page_config(page_title="工程规范 Agentic RAG", layout="wide")
try:
    environment_config = AppConfig.from_sources()
except ConfigurationError as exc:
    st.error(f"配置错误：{exc}")
    st.stop()


@st.cache_resource
def load_agent_workflow(config: AppConfig):
    return build_agent_workflow(config)


if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title("工程规范 Agentic RAG")
st.caption("Hybrid Retrieval + Evidence Sufficiency + bounded retry/refusal")

with st.sidebar:
    st.header("配置")
    pdf_path = st.text_input("PDF 路径", value=environment_config.pdf_path)
    index_dir = st.text_input("索引目录", value=environment_config.index_dir)
    if st.button("清空对话"):
        st.session_state.chat_history = []
        st.rerun()

try:
    config = AppConfig.from_sources(pdf_path=pdf_path, index_dir=index_dir)
    workflow = load_agent_workflow(config)
except ConfigurationError as exc:
    st.error(f"配置错误：{exc}")
    st.stop()
except Exception:
    request_id = uuid4().hex
    logger.exception("application initialization failed request_id=%s", request_id)
    st.error(f"初始化失败，请检查本地文件和服务配置。请求编号：{request_id}")
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
    public = present_agent_response(response)
    st.session_state.chat_history.append({"role": "assistant", "content": public.message})

    with st.chat_message("assistant"):
        if public.severity == "error":
            st.error(public.message)
        elif public.severity == "info":
            st.info(public.message)
        else:
            st.markdown(public.message)
        for detail in public.details:
            st.caption(detail)

        if public.show_evidence:
            with st.expander("Evidence", expanded=True):
                for evidence in response.state.evidences:
                    st.markdown(f"**{format_evidence_citation(evidence)}**")
                    st.caption(
                        f"content_type={evidence.content_type} | "
                        f"rerank_score={evidence.rerank_score or 0:.4f}"
                    )
                    st.write(evidence.text)
                    st.divider()

        with st.expander("Agent Trace", expanded=False):
            for step in format_agent_trace(response):
                st.code(step, language=None)
            st.write(f"retry_count: {response.state.retry_count}")
            st.write(f"final_action: {response.state.final_action}")
            if response.state.missing_requirements:
                st.write("missing_requirements:")
                for requirement in response.state.missing_requirements:
                    st.write(f"- {requirement}")
