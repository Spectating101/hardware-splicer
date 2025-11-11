#!/usr/bin/env python3
"""
Circuit.AI - Streamlit Interface
===============================

Alternative web interface for Circuit.AI using Streamlit.
Perfect for deployment on Streamlit Cloud.
"""

import streamlit as st
import sys
import os
from pathlib import Path
import tempfile
import requests
import json
from PIL import Image
import io

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.core.ingest import CircuitAnalyzer

# Page configuration
st.set_page_config(
    page_title="Circuit.AI - PCB Analysis",
    page_icon="🔌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize analyzer
@st.cache_resource
def get_analyzer():
    return CircuitAnalyzer()

analyzer = get_analyzer()

# Main app
def main():
    st.title("🔌 Circuit.AI - PCB Component Intelligence")
    st.markdown("**Transform e-waste into educational opportunities through AI-powered component analysis**")
    
    # Sidebar
    st.sidebar.header("⚙️ Settings")
    
    # Detection backend selection
    backend = st.sidebar.selectbox(
        "Detection Backend",
        ["classical", "yolo", "demo"],
        help="Choose the computer vision backend for component detection"
    )
    
    # OCR toggle
    enable_ocr = st.sidebar.checkbox(
        "Enable OCR",
        value=True,
        help="Enable text recognition on PCB components"
    )
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📤 Upload PCB Image")
        
        uploaded_file = st.file_uploader(
            "Choose a PCB image file",
            type=['png', 'jpg', 'jpeg'],
            help="Upload a clear image of a printed circuit board"
        )
        
        if uploaded_file is not None:
            # Display uploaded image
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded PCB Image", use_column_width=True)
            
            # Analysis button
            if st.button("🔍 Analyze PCB", type="primary"):
                with st.spinner("Analyzing PCB components..."):
                    try:
                        # Save uploaded file temporarily
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                            image.save(tmp_file.name)
                            
                            # Analyze the image
                            results = analyzer.analyze_from_file(tmp_file.name)
                            
                            # Clean up
                            os.unlink(tmp_file.name)
                        
                        # Store results in session state
                        st.session_state.analysis_results = results
                        st.success("Analysis complete!")
                        
                    except Exception as e:
                        st.error(f"Analysis failed: {str(e)}")
    
    with col2:
        st.header("📊 Analysis Results")
        
        if 'analysis_results' in st.session_state:
            results = st.session_state.analysis_results
            
            if "error" in results:
                st.error(f"Analysis Error: {results['error']}")
            else:
                # Detection summary
                detection_summary = results.get("detection_summary", {})
                total_components = detection_summary.get("total_components", 0)
                confidence = detection_summary.get("average_confidence", 0)
                
                st.metric("Components Detected", total_components)
                st.metric("Average Confidence", f"{confidence:.2f}")
                
                # Component breakdown
                if total_components > 0:
                    st.subheader("🔧 Component Breakdown")
                    component_counts = {}
                    detected_components = results.get("detected_components", [])
                    
                    for comp in detected_components:
                        comp_type = comp.get("class_name", "unknown")
                        component_counts[comp_type] = component_counts.get(comp_type, 0) + 1
                    
                    for comp_type, count in component_counts.items():
                        st.write(f"• **{comp_type}**: {count}")
                    
                    # Capabilities
                    functionality = results.get("functionality_analysis", {})
                    capabilities = functionality.get("capabilities", [])
                    
                    if capabilities:
                        st.subheader("⚡ Capabilities Detected")
                        for capability in capabilities:
                            st.write(f"• {capability}")
                    
                    # Project recommendations
                    recommendations = results.get("project_recommendations", [])
                    
                    if recommendations:
                        st.subheader("🎯 Project Recommendations")
                        for i, project in enumerate(recommendations[:3], 1):
                            name = project.get("name", "Unknown Project")
                            difficulty = project.get("difficulty", "unknown")
                            description = project.get("description", "No description")
                            
                            with st.expander(f"{i}. {name} ({difficulty})"):
                                st.write(description)
                else:
                    st.warning("No components detected. Try uploading a clearer image.")
        else:
            st.info("Upload a PCB image and click 'Analyze PCB' to see results.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
        <p>🔌 Circuit.AI - Transforming e-waste into educational opportunities through AI</p>
        <p>Built with FastAPI, OpenCV, and Streamlit</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
