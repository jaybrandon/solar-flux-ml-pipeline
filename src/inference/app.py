import requests
import streamlit as st

from src.util import load_env

API_BASE_URL = load_env("API_BASE_URL")

st.set_page_config(page_title="Solar Flare Early Warning System", layout="wide")


def fetch_latest_prediction():
    try:
        response = requests.get(f"{API_BASE_URL}/predictions/latest", timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"API Connection Failed: {e}")
        return None


st.title("Solar Flare Early Warning System")
st.markdown("Monitoring GOES Satellite X-Ray Flux to predict M-Class threshold passes.")


if st.button("Sync with Latest Satellite Data"):
    with st.spinner("Fetching prediction..."):
        result = fetch_latest_prediction()
        if result:
            st.metric(
                label="24-Hour Max Flux Forecast (W/m²)",
                value=f"{result['predicted_max_flux_24h']:.2e}",
            )

            if result.get("m_class_alert"):
                st.error("HIGH RISK: M-Class Flare Threshold Exceeded!")
            else:
                st.success("Nominal: No critical flares predicted.")

            st.caption(
                f"Served by Model Version: {result.get('model_version', 'Unknown')} | Run ID: {result.get('wandb_run_id', 'Unknown')}"
            )
