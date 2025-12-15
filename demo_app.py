import streamlit as st
import asyncio
import os
import sys
import base64
from PIL import Image
import io

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from circuit_agent import CircuitAgent

# Page Config
st.set_page_config(
    page_title="Circuit-AI Platform",
    page_icon="👁️",
    layout="wide"
)

st.title("👁️ Circuit-AI Platform")
st.markdown("### The Visual Intelligence Engine for Electronics")

# Sidebar: Mode Selection
st.sidebar.header("Select Product Mode")
mode = st.sidebar.radio(
    "Choose Application:",
    ("Standard Repair", "Circuit-Scout (Reseller)", "Retro-Check (Gamer)", "Pocket-AOI (Beta)")
)

mode_map = {
    "Standard Repair": "standard",
    "Circuit-Scout (Reseller)": "salvage",
    "Retro-Check (Gamer)": "retro",
    "Pocket-AOI (Beta)": "inspect"
}

selected_mode = mode_map[mode]

# Main Content
col1, col2 = st.columns(2)

with col1:
    st.header("1. Upload Board Image")
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "png", "jpeg"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Image", use_column_width=True)
        
        if st.button("Analyze Board"):
            with st.spinner(f"Running {mode} Analysis..."):
                # Convert to Base64
                buffered = io.BytesIO()
                image.save(buffered, format="JPEG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                # Initialize Agent
                # NOTE: In production, agent should be cached
                agent = CircuitAgent(knowledge_path="knowledge_base")
                
                # Run Analysis
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                response = loop.run_until_complete(
                    agent.process_request(f"Analyze this in {selected_mode} mode", image_b64=img_str, mode=selected_mode)
                )
                
                # Display Results
                with col2:
                    st.header("2. Intelligence Report")
                    
                    if response.get("augmented_image_b64"):
                        aug_img = Image.open(io.BytesIO(base64.b64decode(response["augmented_image_b64"])))
                        st.image(aug_img, caption="Augmented Reality View", use_column_width=True)
                    
                    st.subheader("System Findings:")
                    st.text(response["vision_report"])
                    
                    st.subheader("AI Consultant:")
                    st.markdown(response["llm_response"])

# Footer
st.markdown("---")
st.caption("Powered by Circuit-AI | YOLOv8 | Cerebras Llama-3")
