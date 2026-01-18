import streamlit as st
import google.generativeai as genai
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
    
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    return model, TavilyClient(api_key=tavily_key)

gemini_model, tavily_client = init_clients()

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
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])  # Remove first and last lines
    
    # Remove json prefix
    if text.startswith("json"):
        text = text[4:].strip()
    
    return text

def extract_claims(text):
    prompt = f"""Extract ALL verifiable factual claims from this document. Focus on:
- Statistics and percentages
- Dates and specific timeframes  
- Financial figures (stock prices, revenue, market cap, GDP)
- Technical specifications
- Numerical data
- Company/organization activities and announcements
- Economic indicators

For each claim, provide:
1. The exact claim text from the document
2. Category (financial/statistic/date/technical/economic)
3. Optimized search query to verify it

Return ONLY a JSON array with this exact structure:
[
  {{
    "claim": "exact claim text from document",
    "category": "category type",
    "search_query": "optimized google search query"
  }}
]

Document text:
{text[:10000]}

IMPORTANT: Return ONLY the JSON array, no explanation, no markdown, no additional text."""

    try:
        response = gemini_model.generate_content(prompt)
        result = clean_json_response(response.text)
        
        parsed = json.loads(result)
        
        # Handle if wrapped in object with 'claims' key
        if isinstance(parsed, dict):
            if 'claims' in parsed:
                return parsed['claims']
            # If it's a dict with array values, get first array
            for value in parsed.values():
                if isinstance(value, list):
                    return value
        
        return parsed if isinstance(parsed, list) else []
        
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
            search_context += f"\nSource {idx+1}: {result.get('title', '')}\n"
            search_context += f"URL: {result.get('url', '')}\n"
            search_context += f"Content: {result.get('content', '')[:500]}\n"
        
        analysis_prompt = f"""You are a fact-checker. Analyze if this claim is accurate based on current web data from January 2026.

CLAIM TO VERIFY: {claim_obj['claim']}

CURRENT WEB SEARCH RESULTS:
{search_context}

SEARCH ENGINE ANSWER: {search_results.get('answer', 'No direct answer provided')}

Task: Determine the accuracy of the claim and provide:

1. Status: Must be EXACTLY one of these three values:
   - "VERIFIED" - The claim matches current data accurately
   - "INACCURATE" - The claim contains outdated or wrong numbers/facts
   - "FALSE" - No evidence supports this claim, or it contradicts current data

2. Correct Information: What is the actual, current, verified information on this topic?

3. Sources: List 2-3 URLs from the search results that support your conclusion

4. Explanation: 2-3 sentences explaining why you classified it this way

Return ONLY a JSON object with this exact structure:
{{
  "status": "VERIFIED or INACCURATE or FALSE",
  "correct_info": "the actual current verified information",
  "sources": ["url1", "url2"],
  "explanation": "brief explanation of your reasoning"
}}

IMPORTANT: Return ONLY the JSON object, no markdown, no explanation outside the JSON."""

        response = gemini_model.generate_content(analysis_prompt)
        result = clean_json_response(response.text)
        
        return json.loads(result)
        
    except Exception as e:
        return {
            "status": "ERROR",
            "correct_info": "Could not verify due to error",
            "sources": [],
            "explanation": f"Verification error: {str(e)[:100]}"
        }

# UI
st.title("🔍 Fact-Checking Web App")
st.markdown("**Upload a PDF document to automatically verify factual claims against live web data.**")

with st.sidebar:
    st.header("ℹ️ How It Works")
    st.markdown("""
    1. **Upload** your PDF document
    2. **Extract** claims using AI (Gemini)
    3. **Verify** against live web data (Tavily)
    4. **Review** results with sources
    """)
    
    st.divider()
    
    st.markdown("### 🔑 Powered By")
    st.markdown("- Google Gemini 1.5 Flash")
    st.markdown("- Tavily Search API")
    
    st.divider()
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

uploaded_file = st.file_uploader("📄 Upload PDF Document", type=['pdf'])

if uploaded_file:
    st.success(f"✅ File uploaded: {uploaded_file.name}")
    
    if st.button("🚀 Start Fact-Checking", type="primary", use_container_width=True):
        # Extract text
        with st.spinner("📖 Reading PDF..."):
            text = extract_text_from_pdf(uploaded_file)
            st.info(f"Extracted {len(text)} characters from PDF")
        
        # Extract claims
        with st.spinner("🤖 Extracting claims with AI..."):
            claims = extract_claims(text)
            
            if not claims:
                st.error("No claims extracted. Please check your PDF content.")
                st.stop()
            
            st.info(f"Found {len(claims)} claims to verify")
        
        # Verify each claim
        st.subheader("🔎 Verification Results")
        
        verified_count = 0
        inaccurate_count = 0
        false_count = 0
        
        progress_bar = st.progress(0)
        
        for idx, claim in enumerate(claims):
            with st.spinner(f"Verifying claim {idx+1}/{len(claims)}..."):
                result = verify_claim(claim)
                
                # Update counts
                status = result.get("status", "ERROR").upper()
                if status == "VERIFIED":
                    verified_count += 1
                    icon = "✅"
                    color = "green"
                elif status == "INACCURATE":
                    inaccurate_count += 1
                    icon = "⚠️"
                    color = "orange"
                else:
                    false_count += 1
                    icon = "❌"
                    color = "red"
                
                # Display result
                claim_preview = claim.get('claim', 'Unknown claim')[:100]
                with st.expander(f"{icon} **{claim_preview}...**", expanded=(status != "VERIFIED")):
                    st.markdown(f"**Status:** :{color}[{status}]")
                    st.markdown(f"**Category:** {claim.get('category', 'N/A')}")
                    st.markdown(f"**Correct Information:** {result.get('correct_info', 'N/A')}")
                    st.markdown(f"**Explanation:** {result.get('explanation', 'N/A')}")
                    
                    sources = result.get('sources', [])
                    if sources:
                        st.markdown("**Sources:**")
                        for source in sources[:3]:
                            if source:
                                st.markdown(f"- {source}")
                
                progress_bar.progress((idx + 1) / len(claims))
        
        # Summary
        st.divider()
        st.subheader("📊 Summary")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Verified", verified_count)
        col2.metric("⚠️ Inaccurate", inaccurate_count)
        col3.metric("❌ False", false_count)
        
        # Accuracy percentage
        total = len(claims)
        accuracy = (verified_count / total * 100) if total > 0 else 0
        
        if accuracy < 50:
            st.error(f"⚠️ Only {accuracy:.1f}% of claims verified. This document contains significant inaccuracies.")
        elif accuracy < 80:
            st.warning(f"⚠️ {accuracy:.1f}% of claims verified. Some claims need correction.")
        else:
            st.success(f"✅ {accuracy:.1f}% of claims verified. Document is mostly accurate.")
        
        # Download results
        results_json = json.dumps({
            "document": uploaded_file.name,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_claims": total,
                "verified": verified_count,
                "inaccurate": inaccurate_count,
                "false": false_count,
                "accuracy_percentage": round(accuracy, 2)
            },
            "claims": claims
        }, indent=2)
        
        st.download_button(
            "📥 Download Full Report (JSON)",
            results_json,
            file_name=f"fact_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

else:
    st.info("👆 Upload a PDF document to begin fact-checking")
    
    with st.expander("📖 Example: What gets checked?"):
        st.markdown("""
        The app will identify and verify claims like:
        
        - **Financial**: "Bitcoin is trading at $42,500"
        - **Statistics**: "GDP growth was -1.5%"
        - **Dates**: "Starship Flight 11 launched in October 2025"
        - **Technical**: "GPT-5 delayed indefinitely"
        - **Economic**: "Unemployment rose to 6.2%"
        
        Each claim is cross-referenced with current web data and flagged as:
        - ✅ **Verified** - Matches current data
        - ⚠️ **Inaccurate** - Outdated or wrong numbers
        - ❌ **False** - No evidence or contradicts reality
        """)