import httpx
import streamlit as st

API_BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="InvestAd", layout="wide")

st.sidebar.title("InvestAd")
page = st.sidebar.radio("Navigate", ["Dashboard", "Recommendations", "Scenarios"])

st.title(page)

if page == "Dashboard":
    st.write("Portfolio dashboard placeholder — wires up in build order step 9.")

    st.subheader("Backend connectivity check")
    try:
        response = httpx.get(f"{API_BASE_URL}/health", timeout=3.0)
        response.raise_for_status()
        st.success(f"FastAPI backend reachable: {response.json()}")
    except httpx.HTTPError as exc:
        st.error(f"Could not reach FastAPI backend at {API_BASE_URL}: {exc}")

elif page == "Recommendations":
    st.write("Recommendation review/refinement chat placeholder — wires up in build order step 5.")

elif page == "Scenarios":
    st.write("Scenario comparison placeholder — wires up in build order step 7.")
