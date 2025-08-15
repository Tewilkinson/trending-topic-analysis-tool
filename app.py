import streamlit as st
import openai
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pytrends.request import TrendReq
import os

# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="Agentic Keyword Trend Detector", layout="wide")
st.title("🔍 Agentic Keyword Trend Detector")

openai.api_key = os.getenv("OPENAI_API_KEY")
pytrends = TrendReq(hl='en-US', tz=360)

# -----------------------------
# Function: Scrape Daily Trending Keywords from Google Trends
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
# Streamlit UI
# -----------------------------
industry = st.selectbox("Select Industry Focus", ["AI", "Finance", "Healthcare", "E-commerce", "Education"])

if st.button("Auto-Detect Weekly Trends"):
    with st.spinner("Fetching daily trending keywords..."):
        try:
            # Step 1: Scrape trending keywords from HTML
            trend_list = scrape_trending_keywords_html(geo='US')

            if not trend_list:
                st.warning("No trending keywords found.")
                st.stop()

            # Step 2: Filter with OpenAI
            prompt = f"""
You're an SEO assistant. From this list of trending keywords:
{', '.join(trend_list)}
Return only those relevant to the {industry} industry. Just respond with a comma-separated list.
"""
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            filtered = response['choices'][0]['message']['content']
            relevant_keywords = [kw.strip() for kw in filtered.split(',') if kw.strip()]

            if not relevant_keywords:
                st.warning(f"No relevant keywords found for {industry}.")
                st.stop()
            else:
                st.success(f"✅ {len(relevant_keywords)} relevant keywords found.")

            # Step 3: Pull trend data for filtered terms
            pytrends.build_payload(relevant_keywords, timeframe='now 7-d', geo='US')
            trend_data = pytrends.interest_over_time()
            if 'isPartial' in trend_data.columns:
                trend_data.drop(columns=['isPartial'], inplace=True)

            if trend_data.empty:
                st.warning("Trend data is unavailable for the selected keywords.")
                st.stop()

            # Step 4: Analyze trend changes
            latest = trend_data.iloc[-1]
            previous = trend_data.iloc[0]
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

            # Step 5: Display
            st.subheader("📊 Trending Keywords This Week")
            st.dataframe(summary, use_container_width=True)

            st.subheader("📈 Interest Over Time")
            st.line_chart(trend_data)

        except Exception as e:
            st.error(f"Something went wrong: {e}")
