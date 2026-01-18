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
    
    # Configure Gemini with correct model name
    genai.configure(api_key=gemini_key)
    
    # Use the correct model identifier
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash-latest',
        generation_config={
            'temperature': 0.1,
            'top_p': 0.95,
            'top_k': 40,
            'max_output_tokens': 8192,
        }
    )
    
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
        # Find the content between ``` markers
        start = text.find("```") + 3
        end = text.rfind("```")
        if end > start:
            text = text[start:end].strip()
    
    # Remove 'json' prefix if present
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
- "search_query": an optimized Google search query to verify this claim (be specific, include dates/numbers)

Return your response as a valid JSON array of objects. Example format:
[
  {{
    "claim": "Bitcoin is trading at $42,500 in January 2026",
    "category": "financial",
    "search_query": "Bitcoin price January 2026"
  }},
  {{
    "claim": "US GDP growth was -1.5% in 2025",
    "category": "economic",
    "search_query": "US GDP growth 2025 actual data"
  }}
]

Document text to analyze:
{text[:10000]}

Return ONLY the JSON array, nothing else. No explanations, no markdown formatting."""

    try:
        response = gemini_model.generate_content(prompt)
        
        if not response or not response.text:
            st.error("Empty response from Gemini")
            return []
        
        result = clean_json_response(response.text)
        
        # Parse JSON
        parsed = json.loads(result)
        
        # Handle different response formats
        if isinstance(parsed, dict):
            if 'claims' in parsed:
                return parsed['claims']
            # Get first list value from dict
            for value in parsed.values():
                if isinstance(value, list):
                    return value
        
        if isinstance(parsed, list):
            return parsed
            
        return []
        
    except json.JSONDecodeError as e:
        st.error(f"JSON parsing error: {str(e)}")
        st.code(response.text[:500] if response and response.text else "No response")
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
        
        analysis_prompt = f"""You are a professional fact-checker. Your job is to verify if a claim is accurate based on current January 2026 web data.

CLAIM TO VERIFY:
"{claim_obj['claim']}"

CURRENT WEB SEARCH RESULTS (January 2026):
{search_context}

SEARCH ENGINE SUMMARY:
{search_results.get('answer', 'No summary available')}

Your task:
1. Compare the claim against the search results
2. Determine if the claim is accurate as of January 2026
3. Provide the correct current information

Return a JSON object with these exact fields:
{{
  "status": "VERIFIED" or "INACCURATE" or "FALSE",
  "correct_info": "What is the actual current information on this topic as of January 2026",
  "sources": ["url1", "url2"],
  "explanation": "Brief 2-3 sentence explanation of why you classified it this way"
}}

Status definitions:
- VERIFIED: The claim accurately matches current January 2026 data
- INACCURATE: The claim has wrong numbers, outdated data, or minor factual errors
- FALSE: No evidence supports the claim, or it directly contradicts current data

Return ONLY the JSON object, no other text."""

        response = gemini_model.generate_content(analysis_prompt)
        
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
        
    except json.JSONDecodeError as e:
        return {
            "status": "ERROR",
            "correct_info": "JSON parsing failed",
            "sources": [],
            "explanation": f"Could not parse verification result: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "correct_info": "Could not verify due to error",
            "sources": [],
            "explanation": f"Verification error: {str(e)[:150]}"
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
                st.error("❌ No claims extracted. The AI couldn't identify verifiable claims in this PDF.")
                st.info("💡 Tip: Make sure your PDF contains specific factual claims like numbers, dates, or statistics.")
                st.stop()
            
            st.success(f"✅ Found {len(claims)} claims to verify")
        
        # Verify each claim
        st.subheader("🔎 Verification Results")
        
        verified_count = 0
        inaccurate_count = 0
        false_count = 0
        error_count = 0
        
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
                elif status == "ERROR":
                    error_count += 1
                    icon = "🔧"
                    color = "gray"
                else:  # FALSE
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
                    if sources and isinstance(sources, list):
                        st.markdown("**Sources:**")
                        for source in sources[:3]:
                            if source:
                                st.markdown(f"- {source}")
                
                progress_bar.progress((idx + 1) / len(claims))
        
        # Summary
        st.divider()
        st.subheader("📊 Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("✅ Verified", verified_count)
        col2.metric("⚠️ Inaccurate", inaccurate_count)
        col3.metric("❌ False", false_count)
        col4.metric("🔧 Errors", error_count)
        
        # Accuracy percentage
        total = len(claims) - error_count
        if total > 0:
            accuracy = (verified_count / total * 100)
            
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
                "total_claims": len(claims),
                "verified": verified_count,
                "inaccurate": inaccurate_count,
                "false": false_count,
                "errors": error_count,
                "accuracy_percentage": round(accuracy, 2) if total > 0 else 0
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