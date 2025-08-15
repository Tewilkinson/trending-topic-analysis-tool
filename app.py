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
st.title("🔍 Agentic Keyword Trend Detector")
industry = st.selectbox("Select Industry Focus", ["AI", "Finance", "Healthcare", "E-commerce", "Education"])

if st.button("Auto-Detect Weekly Trends"):
    with st.spinner("Fetching real-time trending keywords..."):
        try:
            # Step 1: Get trending now
            trends_now = pytrends.trending_searches(pn='united_states').head(20)
            trend_list = trends_now[0].tolist()

            # Step 2: Filter using LLM for relevance
            prompt = f"""
You're a keyword classification system. From this list of trending terms:
{', '.join(trend_list)}
Only return those relevant to the industry: "{industry}".
Respond with a comma-separated list only.
"""
            llm_response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            relevant_keywords = llm_response['choices'][0]['message']['content'].strip().split(',')
            relevant_keywords = [kw.strip() for kw in relevant_keywords if kw.strip()]

            if not relevant_keywords:
                st.warning("No relevant keywords found.")
            else:
                st.success(f"{len(relevant_keywords)} keywords found for {industry}")

                # Step 3: Fetch trend data for relevant keywords
                pytrends.build_payload(relevant_keywords, timeframe='now 7-d', geo='US')
                trend_data = pytrends.interest_over_time()

                if 'isPartial' in trend_data.columns:
                    trend_data.drop(columns=['isPartial'], inplace=True)

                # Step 4: Summarize trend growth
                latest = trend_data.iloc[-1]
                previous = trend_data.iloc[0]
                summary = pd.DataFrame({
                    'Keyword': latest.index,
                    'This Week': latest.values,
                    'Start of Week': previous.values,
                    'WoW Change (%)': ((latest - previous) / previous * 100).round(1)
                })
                summary['Status'] = summary['WoW Change (%)'].apply(lambda x: '⬆ Rising' if x > 20 else ('↓ Falling' if x < -10 else '→ Stable'))
                summary.sort_values('WoW Change (%)', ascending=False, inplace=True)

                # Step 5: Display
                st.subheader("📊 Trending Keywords This Week")
                st.dataframe(summary, use_container_width=True)

                st.subheader("📈 Keyword Interest Over Time")
                st.line_chart(trend_data)

        except Exception as e:
            st.error(f"Something went wrong: {e}")
