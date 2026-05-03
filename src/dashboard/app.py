import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import os
from datetime import datetime

# --- CONFIGURATION ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="AI Chatbot Analytics", layout="wide")

st.title("📊 AI-Powered Chatbot Analytics Dashboard")
st.markdown("Real-time monitoring of intent recognition, sentiment, and system health.")

# --- DATA FETCHING ---
def fetch_analytics():
    try:
        resp = requests.get(f"{BACKEND_URL}/analytics", timeout=5)
        return resp.json()
    except Exception as e:
        st.error(f"Failed to fetch analytics: {e}")
        return None

def fetch_health():
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
        return resp.json()
    except Exception:
        return {"status": "offline", "lucene_up": False}

# --- SIDEBAR & REFRESH ---
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

health = fetch_health()
data = fetch_analytics()

# --- TOP METRICS ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("System Status", health.get("status", "unknown").upper())
with col2:
    total_msgs = data.get("total_messages", 0) if data else 0
    st.metric("Total Messages", total_msgs)
with col3:
    avg_sent = data.get("avg_sentiment", 0) if data else 0
    st.metric("Avg Sentiment", f"{avg_sent:.2f}")
with col4:
    lucene = "ONLINE" if health.get("lucene_up") else "OFFLINE"
    st.metric("Lucene Engine", lucene)

if data:
    # --- CHARTS ---
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("🎯 Intent Distribution")
        intents = data.get("intent_distribution", {})
        if intents:
            df_intents = pd.DataFrame(list(intents.items()), columns=["Intent", "Count"])
            fig_pie = px.pie(df_intents, values="Count", names="Intent", hole=0.3)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No intent data available yet.")

    with col_right:
        st.subheader("💬 Sentiment Analysis")
        # Mocking a trend if history isn't available, or showing current distribution
        sentiments = data.get("sentiment_summary", {"Positive": 0, "Neutral": 0, "Negative": 0})
        df_sent = pd.DataFrame(list(sentiments.items()), columns=["Sentiment", "Count"])
        fig_bar = px.bar(df_sent, x="Sentiment", y="Count", color="Sentiment", 
                         color_discrete_map={"Positive": "green", "Neutral": "gray", "Negative": "red"})
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- SESSION STATS ---
    st.subheader("👥 Conversation Dynamics")
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Average Conversation Length:**", f"{data.get('avg_conv_length', 0):.1f} messages")
    with c2:
        st.write("**Top Active User ID:**", data.get("top_user", "N/A"))

else:
    st.warning("Please ensure the Backend API is accessible to view detailed charts.")

st.divider()
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Environment: {os.getenv('ENV', 'Production')}")
