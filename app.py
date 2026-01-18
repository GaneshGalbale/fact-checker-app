import streamlit as st
from google import genai
from google.genai import types
from tavily import TavilyClient
import PyPDF2
import json
import os
from datetime import datetime

st.set_page_config(page_title="Fact Checker", page_icon="🔍", layout="wide")

@st.cache_resource
def init_clients():
    gemini_key = os.getenv("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY", "")
    tavily_key = os.getenv("TAVILY_API_KEY") or st.secrets.get("TAVILY_API_KEY", "")
    
    if not gemini_key or not tavily_key:
        st.error("⚠️ API keys not found.")
        st.stop()
    
    client = genai.Client(api_key=gemini_key)
    return client, TavilyClient(api_key=tavily_key)

gemini_client, tavily_client = init_clients()

def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def clean_json_response(text):
    text = text.strip()
    if text.startswith("```"):
        start = text.find("```") + 3
        end = text.rfind("```")
        if end > start:
            text = text[start:end].strip()
    if text.startswith("json"):
        text = text[4:].strip()
    return text

def extract_claims(text):
    prompt = f"""Extract ALL verifiable factual claims from this document.

Focus on:
- Numbers: prices, percentages, statistics
- Dates and timeframes
- Financial data: stock prices, GDP, revenue
- Technical specs
- Company announcements
- Economic indicators

Return JSON array:
[
  {{
    "claim": "exact claim text",
    "category": "financial/statistic/date/technical/economic",
    "search_query": "optimized search query"
  }}
]

Document:
{text[:10000]}

Return ONLY JSON array, no markdown."""

    try:
        response = gemini_client.models.generate_content(
            model='models/gemini-1.5-flash',  # ✅ Correct format
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8192,
            )
        )
        
        if not response or not response.text:
            return []
        
        result = clean_json_response(response.text)
        parsed = json.loads(result)
        
        if isinstance(parsed, dict):
            if 'claims' in parsed:
                return parsed['claims']
            for value in parsed.values():
                if isinstance(value, list):
                    return value
        
        return parsed if isinstance(parsed, list) else []
        
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return []

def verify_claim(claim_obj):
    try:
        search_results = tavily_client.search(
            query=claim_obj["search_query"],
            max_results=5,
            search_depth="advanced",
            include_answer=True
        )
        
        search_context = ""
        for idx, result in enumerate(search_results.get('results', [])[:3]):
            search_context += f"\nSource {idx+1}: {result.get('title', 'N/A')}\n"
            search_context += f"URL: {result.get('url', 'N/A')}\n"
            search_context += f"Content: {result.get('content', 'N/A')[:400]}\n"
        
        analysis_prompt = f"""Fact-check this claim against January 2026 web data.

CLAIM: "{claim_obj['claim']}"

WEB RESULTS:
{search_context}

SUMMARY: {search_results.get('answer', 'N/A')}

Return JSON:
{{
  "status": "VERIFIED/INACCURATE/FALSE",
  "correct_info": "actual current information",
  "sources": ["url1", "url2"],
  "explanation": "brief reasoning"
}}

Definitions:
- VERIFIED: Matches current data
- INACCURATE: Wrong/outdated numbers
- FALSE: No evidence or contradicts data"""

        response = gemini_client.models.generate_content(
            model='models/gemini-1.5-flash',  # ✅ Correct format
            contents=analysis_prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=2048,
            )
        )
        
        if not response or not response.text:
            raise Exception("Empty response")
        
        result = clean_json_response(response.text)
        verified_result = json.loads(result)
        
        if 'sources' not in verified_result:
            verified_result['sources'] = []
        elif isinstance(verified_result['sources'], str):
            verified_result['sources'] = [verified_result['sources']]
        
        return verified_result
        
    except Exception as e:
        return {
            "status": "ERROR",
            "correct_info": "Could not verify",
            "sources": [],
            "explanation": f"Error: {str(e)[:150]}"
        }

# UI
st.title("🔍 Fact-Checking Web App")
st.markdown("**Upload PDF to verify claims against live web data.**")

with st.sidebar:
    st.header("ℹ️ How It Works")
    st.markdown("""
    1. Upload PDF
    2. Extract claims (AI)
    3. Verify with web search
    4. Review results
    """)
    st.divider()
    st.markdown("### 🔑 Powered By")
    st.markdown("- Google Gemini 1.5 Flash")
    st.markdown("- Tavily Search API")
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
            
            if not claims:
                st.error("❌ No claims extracted.")
                st.stop()
            
            st.success(f"✅ Found {len(claims)} claims")
        
        st.subheader("🔎 Verification Results")
        
        verified = inaccurate = false = errors = 0
        progress = st.progress(0)
        
        for idx, claim in enumerate(claims):
            with st.spinner(f"Verifying {idx+1}/{len(claims)}..."):
                result = verify_claim(claim)
                
                status = result.get("status", "ERROR").upper()
                if status == "VERIFIED":
                    verified += 1
                    icon, color = "✅", "green"
                elif status == "INACCURATE":
                    inaccurate += 1
                    icon, color = "⚠️", "orange"
                elif status == "ERROR":
                    errors += 1
                    icon, color = "🔧", "gray"
                else:
                    false += 1
                    icon, color = "❌", "red"
                
                with st.expander(f"{icon} {claim.get('claim', '')[:100]}...", expanded=(status != "VERIFIED")):
                    st.markdown(f"**Status:** :{color}[{status}]")
                    st.markdown(f"**Category:** {claim.get('category', 'N/A')}")
                    st.markdown(f"**Correct Info:** {result.get('correct_info', 'N/A')}")
                    st.markdown(f"**Explanation:** {result.get('explanation', 'N/A')}")
                    
                    if result.get('sources'):
                        st.markdown("**Sources:**")
                        for src in result['sources'][:3]:
                            if src:
                                st.markdown(f"- {src}")
                
                progress.progress((idx + 1) / len(claims))
        
        st.divider()
        st.subheader("📊 Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("✅ Verified", verified)
        col2.metric("⚠️ Inaccurate", inaccurate)
        col3.metric("❌ False", false)
        col4.metric("🔧 Errors", errors)
        
        total = len(claims) - errors
        if total > 0:
            accuracy = (verified / total * 100)
            
            if accuracy < 50:
                st.error(f"⚠️ Only {accuracy:.1f}% verified. Significant inaccuracies.")
            elif accuracy < 80:
                st.warning(f"⚠️ {accuracy:.1f}% verified. Some corrections needed.")
            else:
                st.success(f"✅ {accuracy:.1f}% verified. Mostly accurate.")
        
        results = json.dumps({
            "document": uploaded_file.name,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": len(claims),
                "verified": verified,
                "inaccurate": inaccurate,
                "false": false,
                "errors": errors,
                "accuracy": round(accuracy, 2) if total > 0 else 0
            }
        }, indent=2)
        
        st.download_button(
            "📥 Download Report",
            results,
            file_name=f"fact_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

else:
    st.info("👆 Upload a PDF to begin")