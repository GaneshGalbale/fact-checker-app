import streamlit as st
import anthropic
from tavily import TavilyClient
import PyPDF2
import json
import os
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Fact Checker",
    page_icon="🔍",
    layout="wide"
)

# Initialize clients
@st.cache_resource
def init_clients():
    anthropic_key = os.getenv("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY", "")
    tavily_key = os.getenv("TAVILY_API_KEY") or st.secrets.get("TAVILY_API_KEY", "")
    
    if not anthropic_key or not tavily_key:
        st.error("⚠️ API keys not found. Please configure in Streamlit secrets.")
        st.stop()
    
    return anthropic.Anthropic(api_key=anthropic_key), TavilyClient(api_key=tavily_key)

claude_client, tavily_client = init_clients()

def extract_text_from_pdf(pdf_file):
    """Extract text from uploaded PDF"""
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def extract_claims(text):
    """Use Claude to extract verifiable claims"""
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

Return ONLY a JSON array of objects with this structure:
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

    message = claude_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response_text = message.content[0].text.strip()
    # Remove markdown if present
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    
    return json.loads(response_text.strip())

def verify_claim(claim_obj):
    """Verify a single claim using Tavily search"""
    try:
        # Search the web
        search_results = tavily_client.search(
            query=claim_obj["search_query"],
            max_results=5,
            search_depth="advanced",
            include_answer=True
        )
        
        # Use Claude to analyze results
        analysis_prompt = f"""You are a fact-checker. Analyze if this claim is accurate based on current web data.

CLAIM: {claim_obj['claim']}

SEARCH RESULTS:
{json.dumps(search_results.get('results', [])[:3], indent=2)}

TAVILY ANSWER: {search_results.get('answer', 'No answer provided')}

Determine:
1. Status: "VERIFIED" (claim matches current data), "INACCURATE" (outdated/wrong numbers), or "FALSE" (no evidence/contradicts)
2. Correct information: What is the actual current data?
3. Sources: Which URLs support your conclusion?
4. Explanation: Brief reasoning (2-3 sentences)

Return ONLY a JSON object:
{{
  "status": "VERIFIED|INACCURATE|FALSE",
  "correct_info": "what is actually true",
  "sources": ["url1", "url2"],
  "explanation": "brief explanation"
}}"""

        analysis = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": analysis_prompt}]
        )
        
        result_text = analysis.content[0].text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        
        return json.loads(result_text.strip())
        
    except Exception as e:
        return {
            "status": "ERROR",
            "correct_info": "Could not verify",
            "sources": [],
            "explanation": f"Error during verification: {str(e)}"
        }

# UI
st.title("🔍 Fact-Checking Web App")
st.markdown("**Upload a PDF document to automatically verify factual claims against live web data.**")

# Sidebar
with st.sidebar:
    st.header("ℹ️ How It Works")
    st.markdown("""
    1. **Upload** your PDF document
    2. **Extract** claims using AI
    3. **Verify** against live web data
    4. **Review** results with sources
    """)
    
    st.divider()
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# File upload
uploaded_file = st.file_uploader("📄 Upload PDF Document", type=['pdf'])

if uploaded_file:
    st.success(f"✅ File uploaded: {uploaded_file.name}")
    
    if st.button("🚀 Start Fact-Checking", type="primary", use_container_width=True):
        # Extract text
        with st.spinner("📖 Reading PDF..."):
            text = extract_text_from_pdf(uploaded_file)
            st.info(f"Extracted {len(text)} characters")
        
        # Extract claims
        with st.spinner("🤖 Extracting claims with AI..."):
            claims = extract_claims(text)
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
                if result["status"] == "VERIFIED":
                    verified_count += 1
                    icon = "✅"
                    color = "green"
                elif result["status"] == "INACCURATE":
                    inaccurate_count += 1
                    icon = "⚠️"
                    color = "orange"
                else:
                    false_count += 1
                    icon = "❌"
                    color = "red"
                
                # Display result
                with st.expander(f"{icon} **{claim['claim'][:100]}...**", expanded=(result["status"] != "VERIFIED")):
                    st.markdown(f"**Status:** :{color}[{result['status']}]")
                    st.markdown(f"**Category:** {claim['category']}")
                    st.markdown(f"**Correct Information:** {result['correct_info']}")
                    st.markdown(f"**Explanation:** {result['explanation']}")
                    
                    if result['sources']:
                        st.markdown("**Sources:**")
                        for source in result['sources'][:3]:
                            st.markdown(f"- {source}")
                
                progress_bar.progress((idx + 1) / len(claims))
        
        # Summary
        st.divider()
        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Verified", verified_count)
        col2.metric("⚠️ Inaccurate", inaccurate_count)
        col3.metric("❌ False", false_count)
        
        # Download results option
        results_json = json.dumps({
            "document": uploaded_file.name,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "verified": verified_count,
                "inaccurate": inaccurate_count,
                "false": false_count
            },
            "claims": claims
        }, indent=2)
        
        st.download_button(
            "📥 Download Results (JSON)",
            results_json,
            file_name=f"fact_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

else:
    st.info("👆 Upload a PDF document to begin fact-checking")
```

#### **File 3: `.gitignore`**
```
.env
__pycache__/
*.pyc
.DS_Store
*.pdf
.streamlit/secrets.toml
