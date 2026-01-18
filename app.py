import streamlit as st
from google import genai
from tavily import TavilyClient
import PyPDF2
import json
import os
from datetime import datetime

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Fact Checker", page_icon="🔍", layout="wide")

MODEL_NAME = "models/gemini-2.5-flash"

# ---------------- INIT CLIENTS ----------------
@st.cache_resource
def init_clients():
    gemini_key = os.getenv("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY", "")
    tavily_key = os.getenv("TAVILY_API_KEY") or st.secrets.get("TAVILY_API_KEY", "")

    if not gemini_key or not tavily_key:
        st.error("⚠️ API keys not found. Please set GOOGLE_API_KEY and TAVILY_API_KEY.")
        st.stop()

    client = genai.Client(api_key=gemini_key)
    return client, TavilyClient(api_key=tavily_key)

genai_client, tavily_client = init_clients()

# ---------------- HELPERS ----------------
def extract_text_from_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def clean_json_response(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text

# ---------------- CLAIM EXTRACTION ----------------
def extract_claims(text):
    prompt = f"""
Extract ALL verifiable factual claims from this document.

Return ONLY a JSON array:
[
  {{
    "claim": "exact claim text",
    "category": "financial/statistic/date/technical/economic",
    "search_query": "optimized search query"
  }}
]

Document:
{text[:10000]}
"""

    try:
        response = genai_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        result = clean_json_response(response.text)
        parsed = json.loads(result)
        return parsed if isinstance(parsed, list) else []
    except Exception as e:
        st.error(f"Claim extraction failed: {e}")
        return []

# ---------------- CLAIM VERIFICATION ----------------
def verify_claim(claim_obj):
    try:
        search_results = tavily_client.search(
            query=claim_obj["search_query"],
            max_results=5,
            search_depth="advanced",
            include_answer=True
        )

        prompt = f"""
Fact-check the following claim using the web data.

CLAIM: "{claim_obj['claim']}"

WEB DATA:
{json.dumps(search_results)[:6000]}

Return ONLY JSON:
{{
  "status": "VERIFIED/INACCURATE/FALSE",
  "correct_info": "correct information",
  "sources": ["url1", "url2"],
  "explanation": "brief explanation"
}}
"""

        response = genai_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        result = clean_json_response(response.text)
        return json.loads(result)
    except Exception as e:
        return {"status": "ERROR", "explanation": str(e)}

# ---------------- UI ----------------
st.title("🔍 Fact-Checking Web App")
st.markdown("**Upload a PDF to verify claims against live web data.**")

with st.sidebar:
    st.header("ℹ️ How It Works")
    st.markdown("""
    1. Upload PDF  
    2. Extract factual claims  
    3. Verify using live web search  
    4. Review results  
    """)
    st.divider()
    st.caption(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

uploaded_file = st.file_uploader("📄 Upload PDF", type=["pdf"])

if uploaded_file:
    st.success(f"Uploaded: {uploaded_file.name}")

    if st.button("🚀 Start Fact-Checking", use_container_width=True):
        with st.spinner("Reading PDF..."):
            text = extract_text_from_pdf(uploaded_file)
            st.info(f"Extracted {len(text)} characters")

        with st.spinner("Extracting claims..."):
            claims = extract_claims(text)
            if not claims:
                st.error("No claims extracted.")
                st.stop()

        st.success(f"Found {len(claims)} claims")
        st.subheader("🔎 Verification Results")

        verified = inaccurate = false = errors = 0
        progress = st.progress(0)

        for i, claim in enumerate(claims):
            result = verify_claim(claim)
            status = result.get("status", "ERROR")

            if status == "VERIFIED":
                verified += 1
            elif status == "INACCURATE":
                inaccurate += 1
            elif status == "FALSE":
                false += 1
            else:
                errors += 1

            with st.expander(claim["claim"]):
                st.write(result)

            progress.progress((i + 1) / len(claims))

        st.divider()
        st.subheader("📊 Summary")
        st.metric("Verified", verified)
        st.metric("Inaccurate", inaccurate)
        st.metric("False", false)
        st.metric("Errors", errors)

else:
    st.info("👆 Upload a PDF to begin")
