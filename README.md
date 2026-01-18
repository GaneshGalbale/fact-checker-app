# 🔍 Fact-Checking Web App

Automated claim verification system that extracts factual claims from PDF documents and verifies them against live web data.

## 🚀 Live Demo

**App URL:** https://fact-checker-app-ganeshgalbale.streamlit.app
**App URL:** https://drive.google.com/file/d/1NKfLIJJVl-VomKdhWDNImHFS1LIrgRbY/view?usp=drive_link


## 📋 Overview

This web application automatically:
1. Extracts verifiable claims from uploaded PDF documents
2. Searches the web for current information on each claim
3. Classifies claims as **Verified**, **Inaccurate**, or **False**
4. Provides sources and explanations for each verification

## 🛠️ Tech Stack

- **Framework**: Streamlit
- **AI Model**: Google Gemini 2.5 Flash
- **Search API**: Tavily AI
- **PDF Processing**: PyPDF2
- **Deployment**: Streamlit Cloud

## ✨ Features

- PDF text extraction
- AI-powered claim identification
- Real-time web verification
- Source citations
- Clear verification status (✅ Verified, ⚠️ Inaccurate, ❌ False)
- Summary statistics

## 🚀 Quick Start

### Local Setup

1. **Clone the repository**
```bash
   git clone https://github.com/yourusername/fact-checker-app.git
   cd fact-checker-app
```

2. **Install dependencies**
```bash
   pip install -r requirements.txt
```

3. **Set up API keys**
   
   Create `.streamlit/secrets.toml`:
```toml
   GOOGLE_API_KEY = "your-google-gemini-api-key"
   TAVILY_API_KEY = "your-tavily-api-key"
```

4. **Run the app**
```bash
   streamlit run app.py
```

### Get API Keys (Free)

- **Google Gemini**: https://aistudio.google.com/app/apikey
- **Tavily Search**: https://tavily.com (1,000 free searches/month)

## 📦 Requirements
```
streamlit
google-genai
tavily-python
PyPDF2
```

## 🎯 How It Works

1. **Upload**: User uploads a PDF document
2. **Extract**: Gemini AI identifies specific factual claims (numbers, dates, statistics)
3. **Search**: Tavily searches the web for current information
4. **Verify**: Gemini compares claims against search results
5. **Report**: App displays verification status with sources

## 📊 Verification Categories

The app verifies:
- Financial data (stock prices, revenue, market caps)
- Statistics and percentages
- Dates and timelines
- Technical specifications
- Economic indicators (GDP, unemployment, etc.)

## ✅ Verification Status

- **VERIFIED**: Claim matches current web data
- **INACCURATE**: Claim contains outdated or incorrect information
- **FALSE**: No evidence supports the claim

## 📁 Project Structure
```
fact-checker-app/
├── app.py              # Main application
├── requirements.txt    # Dependencies
├── README.md          # Documentation
└── .gitignore         # Git ignore file
```

## 🧪 Testing

Tested with documents containing:
- False cryptocurrency prices → Correctly flagged as INACCURATE
- Outdated GDP statistics → Correctly flagged as INACCURATE
- Fabricated company announcements → Correctly flagged as FALSE

## 🚀 Deployment

Deployed on Streamlit Cloud:
1. Push code to GitHub
2. Go to https://share.streamlit.io
3. Connect your repository
4. Add API keys in app settings
5. Deploy

## 📝 License

MIT

## 👤 Author

Ganesh Galbale
- App: https://fact-checker-app-ganeshgalbale.streamlit.app
- Contact: galbaleganesh@gmail.com
---

**Built for automated fact-checking and claim verification.**