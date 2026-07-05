# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Streamlit UI for the Tenant Communication Platform.

Run with:  streamlit run app.py

Document handling is in-memory only: an uploaded lease is extracted from a BytesIO buffer
and kept in st.session_state. Nothing is written to disk. See the README privacy note.

Note: `streamlit run app.py` executes this file by path, so the sibling `app/` package
(imported below as `from app.workflow import ...`) is resolved normally.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Local dev: load credentials (GEMINI_API_KEY / Vertex config) from .env.
load_dotenv(Path(__file__).resolve().parent / ".env")

# Streamlit Community Cloud: there is no .env on the server. The key is provided via
# st.secrets, but google-genai reads GEMINI_API_KEY from the environment, so bridge it.
if not os.getenv("GEMINI_API_KEY"):
    try:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    except Exception:  # noqa: BLE001 - no secrets file locally; .env already handled it
        pass

from app import config  # noqa: E402
from app.documents import SUPPORTED_EXTENSIONS, UnsupportedDocumentError, extract_text  # noqa: E402
from app.schemas import AnalysisResult  # noqa: E402
from app.workflow import run_workflow  # noqa: E402

st.set_page_config(page_title="Tenant Communication Platform", page_icon="🏠", layout="wide")


def _render_result(result: AnalysisResult) -> None:
    """Render the seven output sections."""
    st.subheader("1. Lease Findings")
    st.markdown(result.lease_findings)
    if result.lease_citations:
        with st.expander("Cited lease passages"):
            for hit in result.lease_citations:
                st.markdown(f"**{hit.citation}** — {hit.text}")

    st.subheader("2. Florida Law Considerations")
    st.markdown(result.law_considerations)

    st.subheader("3. Risk Analysis")
    st.markdown(result.risk_analysis)

    st.subheader("4. Timeline / Deadlines")
    st.markdown(result.timeline)

    st.subheader("5. Recommended Next Steps")
    if result.recommended_next_steps:
        for step in result.recommended_next_steps:
            st.markdown(f"- {step}")
    else:
        st.markdown("_None provided._")

    st.subheader("6. Draft Tenant Message")
    if result.draft_message_subject:
        st.markdown(f"**Subject:** {result.draft_message_subject}")
    st.text_area(
        "Message (copy/edit before sending)",
        value=result.draft_message_body,
        height=220,
        key="draft_output",
    )

    st.subheader("7. Disclaimer")
    st.warning(result.disclaimer)


def main() -> None:
    st.title("🏠 Tenant Communication Platform")
    st.caption(
        "Upload a lease, describe a tenant situation, and get lease findings, Florida law "
        "considerations, risk analysis, deadlines, next steps, and a draft message."
    )
    st.info(config.DISCLAIMER, icon="⚠️")

    # --- Lease upload (in-memory only) ---
    st.markdown("### 1. Upload lease or addendum")
    uploaded = st.file_uploader(
        "PDF, DOCX, or TXT (kept in memory only — never written to disk)",
        type=[ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS],
    )
    if uploaded is not None:
        try:
            lease_text = extract_text(uploaded.name, uploaded.getvalue())
            st.session_state["lease_text"] = lease_text
            st.session_state["lease_name"] = uploaded.name
            if lease_text.strip():
                st.success(f"Extracted {len(lease_text):,} characters from {uploaded.name}.")
            else:
                st.warning(
                    f"No extractable text found in {uploaded.name} (a scanned image PDF?). "
                    "You can still ask a question; findings will rely on Florida law only."
                )
        except UnsupportedDocumentError as exc:
            st.error(str(exc))

    lease_text = st.session_state.get("lease_text", "")
    if lease_text:
        with st.expander(f"Lease loaded: {st.session_state.get('lease_name', 'document')}"):
            st.text(lease_text[:4000] + ("..." if len(lease_text) > 4000 else ""))

    # --- Scenario + tone ---
    st.markdown("### 2. Describe the tenant situation")
    question = st.text_area(
        "Tenant situation or legal question",
        placeholder="e.g., Tenant moved out without notice and still owes utilities. What should I do?",
        height=120,
    )
    tone = st.selectbox("Message tone", config.TONES, index=config.TONES.index(config.DEFAULT_TONE))

    # --- Analyze ---
    if st.button("Analyze", type="primary"):
        if not question.strip():
            st.error("Please describe the tenant situation or question first.")
        else:
            with st.spinner("Analyzing lease, Florida law, risk, and deadlines..."):
                try:
                    result = run_workflow(lease_text, question.strip(), tone)
                except Exception as exc:  # noqa: BLE001 - surface any runtime error to the user
                    st.error(f"Something went wrong running the workflow: {exc}")
                    st.stop()
            st.divider()
            _render_result(result)


if __name__ == "__main__":
    main()
