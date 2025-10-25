# Affine News

A personal project for detecting bias in news reporting by surfacing international perspectives.

## What is this?

Affine.news is a tool for detecting bias in news reporting. Instead of surfacing news from within your country, we show what every other country says. Some narratives line up, others clash, and we surface all of it.

**How it works:** We collect and translate the "international" section of news outlets globally. Think of it as: "What is Country A saying about the events in Country B?" Then we give you a search interface to compare narratives side by side.

**Why "Affine"?** In math, an affine space has no notion of a "center". You can't talk about the absolute position of something, only the relative position between two things.

## Tech Stack

**Frontend:**
- Vanilla JavaScript SPA (`web/js/app.js`, `web/css/app.css`)
- Datamaps.js for world map visualization
- No build tools or frameworks

**Backend:**
- Python Vercel serverless functions (`web/api/query2.py`)
- Neon PostgreSQL database with pgvector extension
- Google Gemini API for LLM-powered spectrum analysis

**Data Pipeline:**
- Python crawlers using BeautifulSoup and newspaper3k
- Google Cloud Translate API for translation
- GitHub Actions for automated crawling, translation, embedding, and topic generation
- Vercel Blob Storage for daily topics JSON