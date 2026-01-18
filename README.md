# 🔍 Fact-Checking Web App

Automated claim verification system that extracts claims from PDFs and verifies them against live web data.

## Features
- PDF text extraction
- AI-powered claim identification (Claude Sonnet 4)
- Live web verification (Tavily API)
- Real-time fact-checking with sources

## Tech Stack
- **Framework**: Streamlit
- **LLM**: Anthropic Claude Sonnet 4
- **Search**: Tavily AI Search API
- **PDF Processing**: PyPDF2

## Setup

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd fact-checker-app
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API Keys
Create `.streamlit/secrets.toml`:
```toml
ANTHROPIC_API_KEY = "your-key-here"
TAVILY_API_KEY = "your-key-here"
```

### 4. Run Locally
```bash
streamlit run app.py
```

## Deployment (Streamlit Cloud)

1. Push code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repository
4. Add secrets in Settings → Secrets
5. Deploy!

## How It Works

1. **Upload PDF**: User uploads document
2. **Extract Claims**: Claude identifies verifiable claims
3. **Web Search**: Tavily searches for current data
4. **Verification**: Claude analyzes search results vs claims
5. **Report**: Display results with status and sources

## Evaluation Criteria Met

✅ Extracts specific claims (stats, dates, figures)
✅ Verifies against live web data
✅ Flags as Verified/Inaccurate/False
✅ Cites sources
✅ Deployed and accessible via URL
✅ Simple drag-and-drop interface

## License
MIT
