import streamlit as st
import openai
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pytrends.request import TrendReq
import os
import json

# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="🔍 AI/Data Keyword Watcher", layout="wide")
st.title("🚀 Agentic Keyword Trend Dashboard")

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pytrends = TrendReq(hl='en-US', tz=360)

# -----------------------------
# Categories we want to classify into
# -----------------------------
CATEGORIES = ['AI and Machine Learning', 'Data Engineering', 'Data Science and Analytics']

# -----------------------------
# Scrape Google Trends Trending Now keywords
# -----------------------------
def scrape_trending_keywords_html(geo='US'):
    url = f"https://trends.google.com/trends/trendingsearches/daily?geo={geo}"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise Exception(f"Trending page returned {r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")
    titles = soup.select("div.feed-item h2 a")
    return [t.text.strip() for t in titles if t.text.strip()]

# -----------------------------
# Use GPT to classify keywords into buckets
# -----------------------------
def classify_keywords(keywords, categories):
    prompt = f"""
You are a keyword classifier. Given the list of trending keywords:

{', '.join(keywords)}

Categorize each keyword into one of the following categories if relevant:
{', '.join(categories)}

Respond in the following JSON format:
{{
  "AI and Machine Learning": [...],
  "Data Engineering": [...],
  "Data Science and Analytics": [...]
}}

Only include keywords that are clearly relevant to the category. Do not make up keywords.
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(response.choices[0].message.content)

# -----------------------------
# Get search volume from pytrends
# -----------------------------
def fetch_search_volume(keywords):
    pytrends.build_payload(keywords, timeframe='now 7-d', geo='US')
    data = pytrends.interest_over_time()
    if 'isPartial' in data.columns:
        data.drop(columns=['isPartial'], inplace=True)
    latest = data.iloc[-1] if not data.empty else pd.Series([0]*len(keywords), index=keywords)
    return latest.to_dict()

# -----------------------------
# Display tables with search volume
# -----------------------------
with st.spinner("🔎 Fetching and categorizing trending keywords..."):
    try:
        trend_list = scrape_trending_keywords_html()
        classified = classify_keywords(trend_list, CATEGORIES)

        for category in CATEGORIES:
            keywords = classified.get(category, [])
            st.subheader(f"📂 {category}")
            if not keywords:
                st.info("No relevant keywords found.")
            else:
                volumes = fetch_search_volume(keywords)
                df = pd.DataFrame({
                    "Trending Keywords": keywords,
                    "Search Volume Score (US)": [volumes.get(kw, 0) for kw in keywords]
                }).sort_values(by="Search Volume Score (US)", ascending=False)
                st.table(df)

    except Exception as e:
        st.error(f"❌ Something went wrong: {e}")
