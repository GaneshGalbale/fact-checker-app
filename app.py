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
        st.error("⚠️ API keys not found. Configure in Streamlit secrets.")
        st.stop()
    
    # Initialize Google GenAI client (new SDK)
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
    """Clean markdown and extract JSON from response"""
    text = text.strip()
    
    # Remove markdown code blocks
    if text.startswith("```"):
        start = text.find("```") + 3
        end = text.rfind("```")
        if end > start:
            text = text[start:end].strip()
    
    # Remove 'json' prefix
    if text.startswith("json"):
        text = text[4:].strip()
    
    return text

def extract_claims(text):
    prompt = f"""You are a fact-checking assistant. Extract ALL specific, verifiable factual claims from this document.

Focus on claims that can be verified with web search:
- Specific numbers: prices, percentages, statistics
- Dates and timeframes
- Financial data: stock prices, GDP, revenue, market caps
- Technical specifications and product details
- Company announcements and activities
- Economic indicators

For EACH claim you find, create a JSON object with:
- "claim": the exact text of the claim from the document
- "category": one of [financial, statistic, date, technical, economic, announcement]
- "search_query": an optimized Google search query to verify this claim

Return your response as a valid JSON array. Example:
[
  {{
    "claim": "Bitcoin is trading at $42,500 in January 2026",
    "category": "financial",
    "search_query": "Bitcoin price January 2026"
  }}
]

Document text:
{text[:10000]}

Return ONLY the JSON array, no explanations, no markdown."""

    try:
        response = gemini_client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8192,
            )
        )
        
        if not response or not response.text:
            st.error("Empty response from Gemini")
            return []
        
        result = clean_json_response(response.text)
        parsed = json.loads(result)
        
        # Handle different response formats
        if isinstance(parsed, dict):
            if 'claims' in parsed:
                return parsed['claims']
            for value in parsed.values():
                if isinstance(value, list):
                    return value
        
        if isinstance(parsed, list):
            return parsed
            
        return []
        
    except json.JSONDecodeError as e:
        st.error(f"JSON parsing error: {str(e)}")
        if response and response.text:
            st.code(response.text[:500])
        return []
    except Exception as e:
        st.error(f"Error extracting claims: {str(e)}")
        return []

def verify_claim(claim_obj):
    try:
        # Search the web
        search_results = tavily_client.search(
            query=claim_obj["search_query"],
            max_results=5,
            search_depth="advanced",
            include_answer=True
        )
        
        # Prepare search context
        search_context = ""
        for idx, result in enumerate(search_results.get('results', [])[:3]):
            search_context += f"\n--- Source {idx+1} ---\n"
            search_context += f"Title: {result.get('title', 'N/A')}\n"
            search_context += f"URL: {result.get('url', 'N/A')}\n"
            search_context += f"Content: {result.get('content', 'N/A')[:400]}\n"
        
        analysis_prompt = f"""You are a professional fact-checker. Verify if this claim is accurate based on current January 2026 web data.

CLAIM TO VERIFY:
"{claim_obj['claim']}"

CURRENT WEB SEARCH RESULTS (January 2026):
{search_context}

SEARCH ENGINE SUMMARY:
{search_results.get('answer', 'No summary available')}

Return a JSON object with:
{{
  "status": "VERIFIED" or "INACCURATE" or "FALSE",
  "correct_info": "What is the actual current information",
  "sources": ["url1", "url2"],
  "explanation": "Brief explanation why"
}}

Status definitions:
- VERIFIED: Claim matches current January 2026 data
- INACCURATE: Wrong numbers, outdated data, or factual errors
- FALSE: No evidence or contradicts current data

Return ONLY the JSON object."""

        response = gemini_client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=analysis_prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=2048,
            )
        )
        
        if not response or not response.text:
            raise Exception("Empty response from Gemini")
        
        result = clean_json_response(response.text)
        verified_result = json.loads(result)
        
        # Ensure sources is a list
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
st.markdown("**Upload a PDF document to automatically verify factual claims against live web data.**")

with st.sidebar:
    st.header("ℹ️ How It Works")
    st.markdown("""
    1. **Upload** PDF document
    2. **Extract** claims using AI
    3. **Verify** against live web
    4. **Review** results with sources
    """)
    
    st.divider()
    st.markdown("### 🔑 Powered By")
    st.markdown("- Google Gemini 2.0 Flash")
    st.markdown("- Tavily Search API")
    st.divider()
    st.caption(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

uploaded_file = st.file_uploader("📄 Upload PDF Document", type=['pdf'])

if uploaded_file:
    st.success(f"✅ File uploaded: {uploaded_file.name}")
    
    if st.button("🚀 Start Fact-Checking", type="primary", use_container_width=True):
        with st.spinner("📖 Reading PDF..."):
            text = extract_text_from_pdf(uploaded_file)
            st.info(f"Extracted {len(text)} characters")
        
        with st.spinner("🤖 Extracting claims..."):
            claims = extract_claims(text)
            
            if not claims:
                st.error("❌ No claims extracted.")
                st.info("💡 Make sure your PDF contains specific factual claims.")
                st.stop()
            
            st.success(f"✅ Found {len(claims)} claims to verify")
        
        st.subheader("🔎 Verification Results")
        
        verified_count = 0
        inaccurate_count = 0
        false_count = 0
        error_count = 0
        
        progress_bar = st.progress(0)
        
        for idx, claim in enumerate(claims):
            with st.spinner(f"Verifying {idx+1}/{len(claims)}..."):
                result = verify_claim(claim)
                
                status = result.get("status", "ERROR").upper()
                if status == "VERIFIED":
                    verified_count += 1
                    icon, color = "✅", "green"
                elif status == "INACCURATE":
                    inaccurate_count += 1
                    icon, color = "⚠️", "orange"
                elif status == "ERROR":
                    error_count += 1
                    icon, color = "🔧", "gray"
                else:
                    false_count += 1
                    icon, color = "❌", "red"
                
                claim_preview = claim.get('claim', 'Unknown')[:100]
                with st.expander(f"{icon} **{claim_preview}...**", expanded=(status != "VERIFIED")):
                    st.markdown(f"**Status:** :{color}[{status}]")
                    st.markdown(f"**Category:** {claim.get('category', 'N/A')}")
                    st.markdown(f"**Correct Info:** {result.get('correct_info', 'N/A')}")
                    st.markdown(f"**Explanation:** {result.get('explanation', 'N/A')}")
                    
                    sources = result.get('sources', [])
                    if sources and isinstance(sources, list):
                        st.markdown("**Sources:**")
                        for source in sources[:3]:
                            if source:
                                st.markdown(f"- {source}")
                
                progress_bar.progress((idx + 1) / len(claims))
        
        st.divider()
        st.subheader("📊 Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("✅ Verified", verified_count)
        col2.metric("⚠️ Inaccurate", inaccurate_count)
        col3.metric("❌ False", false_count)
        col4.metric("🔧 Errors", error_count)
        
        total = len(claims) - error_count
        if total > 0:
            accuracy = (verified_count / total * 100)
            
            if accuracy < 50:
                st.error(f"⚠️ Only {accuracy:.1f}% verified. Document has significant inaccuracies.")
            elif accuracy < 80:
                st.warning(f"⚠️ {accuracy:.1f}% verified. Some claims need correction.")
            else:
                st.success(f"✅ {accuracy:.1f}% verified. Document is mostly accurate.")
        
        results_json = json.dumps({
            "document": uploaded_file.name,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_claims": len(claims),
                "verified": verified_count,
                "inaccurate": inaccurate_count,
                "false": false_count,
                "errors": error_count,
                "accuracy_percentage": round(accuracy, 2) if total > 0 else 0
            }
        }, indent=2)
        
        st.download_button(
            "📥 Download Report (JSON)",
            results_json,
            file_name=f"fact_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

else:
    st.info("👆 Upload a PDF document to begin fact-checking")