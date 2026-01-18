import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import PyPDF2
import json
import os
from datetime import datetime

st.set_page_config(page_title="Fact Checker", page_icon="🔍", layout="wide")

@st.cache_resource
def init_clients():
    openai_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")
    tavily_key = os.getenv("TAVILY_API_KEY") or st.secrets.get("TAVILY_API_KEY", "")
    
    if not openai_key or not tavily_key:
        st.error("⚠️ API keys not found. Configure in Streamlit secrets.")
        st.stop()
    
    return OpenAI(api_key=openai_key), TavilyClient(api_key=tavily_key)

openai_client, tavily_client = init_clients()

def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def extract_claims(text):
    prompt = f"""Extract ALL verifiable factual claims from this document. Focus on:
- Statistics and percentages
- Dates and specific timeframes
- Financial figures (prices, revenue, market cap)
- Technical specifications
- Numerical data
- Company/organization activities
- Economic indicators

For each claim, provide:
1. The exact claim text
2. Category (financial/statistic/date/technical/economic)
3. Key search terms to verify it

Return ONLY a JSON array with this structure:
[
  {{
    "claim": "exact claim text",
    "category": "category type",
    "search_query": "optimized search query"
  }}
]

Document text:
{text[:8000]}

Return ONLY valid JSON, no markdown, no explanation."""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"}
    )
    
    result = response.choices[0].message.content.strip()
    parsed = json.loads(result)
    
    # Handle if wrapped in object
    if isinstance(parsed, dict) and 'claims' in parsed:
        return parsed['claims']
    return parsed if isinstance(parsed, list) else []

def verify_claim(claim_obj):
    try:
        search_results = tavily_client.search(
            query=claim_obj["search_query"],
            max_results=5,
            search_depth="advanced",
            include_answer=True
        )
        
        analysis_prompt = f"""You are a fact-checker. Analyze if this claim is accurate.

CLAIM: {claim_obj['claim']}

SEARCH RESULTS:
{json.dumps(search_results.get('results', [])[:3], indent=2)}

TAVILY ANSWER: {search_results.get('answer', 'No answer')}

Determine:
1. Status: "VERIFIED", "INACCURATE", or "FALSE"
2. Correct information
3. Sources URLs
4. Brief explanation

Return ONLY JSON:
{{
  "status": "VERIFIED|INACCURATE|FALSE",
  "correct_info": "actual truth",
  "sources": ["url1", "url2"],
  "explanation": "brief reasoning"
}}"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content.strip())
        
    except Exception as e:
        return {
            "status": "ERROR",
            "correct_info": "Could not verify",
            "sources": [],
            "explanation": f"Error: {str(e)}"
        }

# UI
st.title("🔍 Fact-Checking Web App")
st.markdown("**Upload a PDF to verify claims against live web data.**")

with st.sidebar:
    st.header("ℹ️ How It Works")
    st.markdown("""
    1. Upload PDF
    2. Extract claims (AI)
    3. Verify with web search
    4. Review results
    """)
    st.divider()
    st.caption(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

uploaded_file = st.file_uploader("📄 Upload PDF", type=['pdf'])

if uploaded_file:
    st.success(f"✅ Uploaded: {uploaded_file.name}")
    
    if st.button("🚀 Start Fact-Checking", type="primary", use_container_width=True):
        with st.spinner("📖 Reading PDF..."):
            text = extract_text_from_pdf(uploaded_file)
            st.info(f"Extracted {len(text)} characters")
        
        with st.spinner("🤖 Extracting claims..."):
            claims = extract_claims(text)
            st.info(f"Found {len(claims)} claims")
        
        st.subheader("🔎 Verification Results")
        
        verified = inaccurate = false = 0
        progress = st.progress(0)
        
        for idx, claim in enumerate(claims):
            with st.spinner(f"Verifying {idx+1}/{len(claims)}..."):
                result = verify_claim(claim)
                
                if result["status"] == "VERIFIED":
                    verified += 1
                    icon, color = "✅", "green"
                elif result["status"] == "INACCURATE":
                    inaccurate += 1
                    icon, color = "⚠️", "orange"
                else:
                    false += 1
                    icon, color = "❌", "red"
                
                with st.expander(f"{icon} {claim['claim'][:100]}...", expanded=(result["status"] != "VERIFIED")):
                    st.markdown(f"**Status:** :{color}[{result['status']}]")
                    st.markdown(f"**Category:** {claim['category']}")
                    st.markdown(f"**Correct Info:** {result['correct_info']}")
                    st.markdown(f"**Explanation:** {result['explanation']}")
                    
                    if result.get('sources'):
                        st.markdown("**Sources:**")
                        for src in result['sources'][:3]:
                            st.markdown(f"- {src}")
                
                progress.progress((idx + 1) / len(claims))
        
        st.divider()
        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Verified", verified)
        col2.metric("⚠️ Inaccurate", inaccurate)
        col3.metric("❌ False", false)
else:
    st.info("👆 Upload a PDF to begin")