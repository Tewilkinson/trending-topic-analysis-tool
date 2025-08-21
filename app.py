# trending_dashboard.py
import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import os
import openai
import pickle

# -----------------------------
# Config
# -----------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")  # Set in your .env

CATEGORIES = ["AI/ML"]  # Start with AI/ML only
CACHE_FILE = "topic_cache.pkl"  # Cache OpenAI classifications

RSS_FEEDS = {
    "daily": "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US",
    "realtime": "https://trends.google.com/trends/trendingsearches/realtime/rss?geo=US"
}

# -----------------------------
# Load or initialize OpenAI cache
# -----------------------------
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "rb") as f:
        topic_cache = pickle.load(f)
else:
    topic_cache = {}

# -----------------------------
# Helper Functions
# -----------------------------
def fetch_rss(url):
    """Fetch RSS feed and return list of items"""
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, 'xml')
    items = []
    for item in soup.find_all('item'):
        title = item.title.text
        pub_date = datetime.strptime(item.pubDate.text, "%a, %d %b %Y %H:%M:%S %Z")
        traffic = item.find('ht:approx_traffic').text if item.find('ht:approx_traffic') else "N/A"
        items.append({"topic": title, "published_at": pub_date, "traffic": traffic})
    return items

def categorize_topic_openai(topic):
    """Use OpenAI to classify topic into categories"""
    if topic in topic_cache:
        return topic_cache[topic]

    prompt = f"""
You are an expert in technology and AI. Categorize this topic into one of these categories: ['AI/ML', 'Other']. 
Only return the category. Ignore irrelevant topics.
Topic: "{topic}"
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        category = response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"OpenAI API error for topic '{topic}': {e}")
        category = "Other"

    # Only keep relevant categories
    if category not in CATEGORIES:
        category = None

    topic_cache[topic] = category
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(topic_cache, f)

    return category

def load_trends():
    """Fetch and categorize trends from all feeds"""
    all_items = []
    for feed_name, feed_url in RSS_FEEDS.items():
        items = fetch_rss(feed_url)
        for item in items:
            category = categorize_topic_openai(item['topic'])
            if category:
                item['category'] = category
                all_items.append(item)
    df = pd.DataFrame(all_items)
    if not df.empty:
        df = df.drop_duplicates(subset=['topic', 'published_at'])
        df['published_at'] = pd.to_datetime(df['published_at'])
    return df

def filter_time_period(df, period="24h"):
    now = datetime.utcnow()
    if period == "24h":
        return df[df['published_at'] >= now - timedelta(hours=24)]
    elif period == "48h":
        return df[df['published_at'] >= now - timedelta(hours=48)]
    elif period == "7d":
        return df[df['published_at'] >= now - timedelta(days=7)]
    else:
        return df

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Google Trending Now Dashboard", layout="wide")
st.title("Google Trending Now - AI/ML Dashboard")

# Sidebar
time_period = st.sidebar.selectbox("Time Period", ["24h", "48h", "7d"])
category_filter = st.sidebar.selectbox("Category", CATEGORIES)

st.sidebar.markdown("---")
st.sidebar.markdown("This dashboard fetches trending topics from Google Trends RSS feeds and categorizes them into AI/ML using OpenAI GPT.")

# Fetch and process trends
with st.spinner("Fetching trending topics..."):
    df_trends = load_trends()

if df_trends.empty:
    st.warning("No trending topics found.")
else:
    # Filter
    df_filtered = df_trends[df_trends['category'] == category_filter]
    df_filtered = filter_time_period(df_filtered, time_period)

    if df_filtered.empty:
        st.info(f"No {category_filter} topics found in the last {time_period}.")
    else:
        # Display table
        st.subheader(f"Trending {category_filter} Topics - Last {time_period}")
        st.dataframe(df_filtered[['topic', 'traffic', 'published_at', 'category']].sort_values(by='published_at', ascending=False))

        # Display bar chart by traffic
        st.subheader("Top Trends by Search Volume")
        # Convert traffic to numeric if possible
        def parse_traffic(val):
            try:
                return int(val.replace(',', '').replace('+', ''))
            except:
                return 0
        df_filtered['traffic_numeric'] = df_filtered['traffic'].apply(parse_traffic)
        top_trends = df_filtered.groupby('topic')['traffic_numeric'].max().sort_values(ascending=False)
        st.bar_chart(top_trends)
