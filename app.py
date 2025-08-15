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
st.title("🚀 Agentic Keyword Trend Analyzer")

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pytrends = TrendReq(hl='en-US', tz=360)

# -----------------------------
# Categories we want to classify into
# -----------------------------
CATEGORIES = ['AI/ML', 'Data Engineering', 'Analytics']

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
  "AI/ML": [...],
  "Data Engineering": [...],
  "Analytics": [...]
}}

Only include keywords that are clearly relevant to the category. Do not make up keywords.
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(response.choices[0].message.content)

# -----------------------------
# Pull Google Trends data + change
# -----------------------------
def analyze_trends(keywords):
    if not keywords:
        return pd.DataFrame()
    pytrends.build_payload(keywords, timeframe='now 7-d', geo='US')
    data = pytrends.interest_over_time()
    if 'isPartial' in data.columns:
        data.drop(columns=['isPartial'], inplace=True)

    latest = data.iloc[-1]
    previous = data.iloc[0]
    summary = pd.DataFrame({
        'Keyword': latest.index,
        'This Week': latest.values,
        'Start of Week': previous.values,
        'WoW Change (%)': ((latest - previous) / previous.replace(0, 1) * 100).round(1)
    })

    def status(change):
        if change > 20:
            return '⬆ Rising'
        elif change < -10:
            return '↓ Falling'
        else:
            return '→ Stable'

    summary['Status'] = summary['WoW Change (%)'].apply(status)
    summary.sort_values(by='WoW Change (%)', ascending=False, inplace=True)
    return summary

# -----------------------------
# Run the tool
# -----------------------------
with st.spinner("🔎 Fetching and classifying trends..."):
    try:
        # Step 1: Scrape trending now
        trend_list = scrape_trending_keywords_html()

        # Step 2: Classify into categories
        classified = classify_keywords(trend_list, CATEGORIES)

        # Step 3: Display tables per category
        for cat in CATEGORIES:
            st.header(f"📂 {cat} Trends")
            keywords = classified.get(cat, [])
            if not keywords:
                st.info(f"No trending keywords found for {cat} this week.")
                continue

            trend_summary = analyze_trends(keywords)
            st.dataframe(trend_summary, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Something went wrong: {e}")
