import streamlit as st
from pytrends.request import TrendReq
import openai
import pandas as pd
import os

# -----------------------------
# Environment Setup
# -----------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")
pytrends = TrendReq(hl='en-US', tz=360)

# -----------------------------
# Streamlit App
# -----------------------------
st.set_page_config(page_title="Agentic Keyword Trend Detector", layout="wide")
st.title("🔍 Agentic Keyword Trend Detector")

industry = st.selectbox("Select Industry Focus", ["AI", "Finance", "Healthcare", "E-commerce", "Education"])

if st.button("Auto-Detect Weekly Trends"):
    with st.spinner("Fetching real-time trending keywords..."):
        try:
            # Step 1: Try trending searches from US, fallback to Global
            try:
                trends_now = pytrends.trending_searches(pn='united_states')
            except:
                trends_now = pytrends.trending_searches(pn='global')
            
            trend_list = trends_now[0].tolist()
            if not trend_list:
                st.warning("No trending searches found.")
                st.stop()

            # Step 2: Use GPT to filter by industry
            prompt = f"""
You're a keyword classifier. From the list of trending keywords below:
{', '.join(trend_list)}
Identify only those that are relevant to the {industry} industry. 
Respond with a concise, comma-separated list.
"""
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            filtered = response['choices'][0]['message']['content']
            relevant_keywords = [kw.strip() for kw in filtered.split(',') if kw.strip()]

            if not relevant_keywords:
                st.warning(f"No relevant trending keywords found for {industry}.")
                st.stop()
            else:
                st.success(f"✅ {len(relevant_keywords)} keywords found related to {industry}.")

            # Step 3: Pull Google Trends data for these keywords
            pytrends.build_payload(relevant_keywords, timeframe='now 7-d', geo='US')
            trend_data = pytrends.interest_over_time()

            if 'isPartial' in trend_data.columns:
                trend_data.drop(columns=['isPartial'], inplace=True)

            if trend_data.empty:
                st.warning("Trend data is unavailable for the selected keywords.")
                st.stop()

            # Step 4: Compare beginning vs end of week
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
            st.subheader("📊 Weekly Trending Keywords")
            st.dataframe(summary, use_container_width=True)

            st.subheader("📈 Interest Over Time")
            st.line_chart(trend_data)

        except Exception as e:
            st.error(f"Something went wrong: {e}")
