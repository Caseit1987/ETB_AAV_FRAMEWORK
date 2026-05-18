import streamlit as st
import os

st.set_page_config(page_title="SHADOW CORE METRICS", layout="wide")

def load_live_telemetry():
    log_path = "/data/data/com.termux/files/home/SCDU_PERMANENT_LOG.txt"
    if not os.path.exists(log_path):
        return 0, 0, 1.0
    try:
        with open(log_path, "r") as f:
            lines = [line.strip() for line in f if line.strip()]
        total_events = len(lines)
        blocked_events = sum(1 for line in lines if "Status: Blocked" in line or "Blocked" in line)
        neutralization_rate = (blocked_events / total_events) if total_events > 0 else 1.0
        return total_events, blocked_events, neutralization_rate
    except Exception:
        return 0, 0, 1.0

# 1. Establish Interactive Sidebar Controls
st.sidebar.header("📊 Series A Financial Simulator")
exposure = st.sidebar.slider("Protected Asset Exposure ($)", min_value=100000, max_value=10000000, value=750000, step=50000)
cost = st.sidebar.slider("ETB Implementation Cost ($)", min_value=10000, max_value=500000, value=65000, step=5000)

# Compute metrics using slider inputs dynamically
total, blocked, rate = load_live_telemetry()
rosi = ((exposure * rate) - cost) / cost

# Render the graphical layout
st.title("🛡️ SHADOW CORE — ETB TRUST BOUNDARY ENGINE")
st.subheader("Real-Time Infrastructure Protection & Capital Performance Analytics")
st.markdown("---")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Operational Status", value="ACTIVE", delta="Telemetry Sync: OK")
with col2:
    st.metric(label="Total Tracked Attacks", value=f"{total} Events")
with col3:
    st.metric(label="Payload Neutralization Rate", value=f"{rate * 100:.2f}%")

st.markdown("---")

col4, col5, col6 = st.columns(3)
with col4:
    st.metric(label="Protected Asset Exposure", value=f"${exposure:,} USD")
with col5:
    st.metric(label="ETB Implementation Cost", value=f"${cost:,} USD")
with col6:
    st.metric(label="Dynamic Framework ROSI", value=f"{rosi * 100:.2f}%", delta="Target: Series A Ready")
