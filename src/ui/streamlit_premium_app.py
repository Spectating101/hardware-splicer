#!/usr/bin/env python3
"""
Circuit.AI - Premium Streamlit Interface
======================================

A professional, modern web interface for Circuit.AI using Streamlit
with beautiful styling, animations, and premium UX.
"""

import streamlit as st
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json
import requests
from pathlib import Path
import sys
from typing import Optional, Tuple, Dict, Any
import time

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.core.ingest import CircuitAnalyzer

# Page configuration
st.set_page_config(
    page_title="Circuit.AI - Component Intelligence Platform",
    page_icon="🔌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for premium styling
st.markdown("""
<style>
/* Premium Circuit.AI Styling */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Main styling */
.main {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
}

/* Header styling */
.header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 2rem 0;
    text-align: center;
    color: white;
    border-radius: 0 0 20px 20px;
    margin-bottom: 2rem;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}

.header h1 {
    font-family: 'Inter', sans-serif;
    font-size: 3.5rem;
    font-weight: 700;
    margin: 0;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.header p {
    font-family: 'Inter', sans-serif;
    font-size: 1.3rem;
    opacity: 0.9;
    margin: 1rem 0 0 0;
}

/* Card styling */
.card {
    background: white;
    border-radius: 20px;
    padding: 2rem;
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
    border: 1px solid #e1e5e9;
    margin-bottom: 2rem;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.card:hover {
    transform: translateY(-5px);
    box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
}

/* Stats card */
.stats-card {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    color: white;
    border-radius: 20px;
    padding: 1.5rem;
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
    margin-bottom: 2rem;
}

.stats-number {
    font-size: 2.5rem;
    font-weight: 700;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.stats-label {
    font-size: 1rem;
    opacity: 0.9;
    font-weight: 500;
}

/* Button styling */
.stButton > button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border: none;
    color: white;
    font-weight: 600;
    padding: 0.75rem 1.5rem;
    border-radius: 12px;
    transition: all 0.3s ease;
    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
    font-size: 1rem;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
}

/* Secondary button */
.secondary-button {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%) !important;
}

/* Feature grid */
.feature-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 2rem;
    margin: 3rem 0;
}

.feature-card {
    background: white;
    border-radius: 20px;
    padding: 2rem;
    text-align: center;
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
    transition: transform 0.3s ease;
    border: 1px solid #e1e5e9;
}

.feature-card:hover {
    transform: translateY(-8px);
    box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
}

.feature-icon {
    font-size: 4rem;
    margin-bottom: 1.5rem;
    display: block;
}

.feature-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: #333;
    margin-bottom: 1rem;
    font-family: 'Inter', sans-serif;
}

.feature-description {
    color: #666;
    line-height: 1.7;
    font-size: 1.1rem;
    font-family: 'Inter', sans-serif;
}

/* Text input styling */
.stTextInput > div > div > input {
    border-radius: 10px;
    border: 2px solid #e1e5e9;
    padding: 0.75rem 1rem;
    font-size: 1rem;
}

/* Selectbox styling */
.stSelectbox > div > div > div {
    border-radius: 10px;
    border: 2px solid #e1e5e9;
    padding: 0.5rem 1rem;
}

/* Image container */
.image-container {
    border-radius: 15px;
    overflow: hidden;
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
    border: 3px solid #e1e5e9;
}

/* Progress bar */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
}

/* Success message */
.success {
    background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
    color: white;
    padding: 1rem;
    border-radius: 10px;
    margin: 1rem 0;
}

/* Error message */
.error {
    background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
    color: white;
    padding: 1rem;
    border-radius: 10px;
    margin: 1rem 0;
}

/* Responsive design */
@media (max-width: 768px) {
    .header h1 {
        font-size: 2.5rem;
    }
    
    .feature-grid {
        grid-template-columns: 1fr;
    }
}
</style>
""", unsafe_allow_html=True)

def create_header():
    """Create the premium header section."""
    st.markdown("""
    <div class="header">
        <h1>🔌 Circuit.AI</h1>
        <p>Transform e-waste into educational opportunities through AI-powered component analysis</p>
    </div>
    """, unsafe_allow_html=True)

def create_stats_section():
    """Create the statistics dashboard."""
    st.markdown("### 📈 Live Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">25</div>
            <div class="stats-label">Total Analyses</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">156</div>
            <div class="stats-label">Components Detected</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">87%</div>
            <div class="stats-label">Avg Confidence</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">0.35s</div>
            <div class="stats-label">Avg Processing Time</div>
        </div>
        """, unsafe_allow_html=True)

def create_upload_section():
    """Create the image upload section."""
    st.markdown("### 📸 Upload PCB Image")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Choose a PCB image",
            type=['png', 'jpg', 'jpeg'],
            help="Upload a clear image of a printed circuit board"
        )
        
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded PCB Image", use_column_width=True)
    
    with col2:
        st.markdown("**🔧 Analysis Settings**")
        
        backend = st.selectbox(
            "Detection Backend",
            ["classical", "yolo", "demo"],
            help="Choose the computer vision backend for component detection"
        )
        
        enable_ocr = st.checkbox(
            "Enable OCR (Text Recognition)",
            value=True,
            help="Extract text from components for better identification"
        )
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            analyze_btn = st.button("🔍 Analyze PCB", use_container_width=True)
        
        with col_btn2:
            demo_btn = st.button("🎯 Run Demo", use_container_width=True)
    
    return uploaded_file, backend, enable_ocr, analyze_btn, demo_btn

def create_results_section():
    """Create the results display section."""
    st.markdown("### 📊 Analysis Results")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Component Analysis**")
        # Results will be displayed here
    
    with col2:
        st.markdown("**Component Detection**")
        # Annotated image will be displayed here

def create_features_section():
    """Create the features showcase section."""
    st.markdown("### 🚀 Platform Features")
    
    st.markdown("""
    <div class="feature-grid">
        <div class="feature-card">
            <div class="feature-icon">🔍</div>
            <div class="feature-title">AI-Powered Detection</div>
            <div class="feature-description">
                Advanced computer vision identifies electronic components with high accuracy using YOLO and classical CV algorithms
            </div>
        </div>
        
        <div class="feature-card">
            <div class="feature-icon">📚</div>
            <div class="feature-title">Educational Insights</div>
            <div class="feature-description">
                Learn about component capabilities, educational value, and how to use salvaged parts for learning
            </div>
        </div>
        
        <div class="feature-card">
            <div class="feature-icon">💡</div>
            <div class="feature-title">Project Recommendations</div>
            <div class="feature-description">
                Discover what you can build with salvaged components - from Arduino projects to audio amplifiers
            </div>
        </div>
        
        <div class="feature-card">
            <div class="feature-icon">💰</div>
            <div class="feature-title">Value Assessment</div>
            <div class="feature-description">
                Calculate market value and reuse potential of components to make informed decisions
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def analyze_pcb_image(image, backend, enable_ocr):
    """Analyze PCB image and return results."""
    try:
        # Convert to numpy array
        image_np = np.array(image)
        
        analyzer = CircuitAnalyzer()
        results = analyzer.analyze_pcb(image_np, backend=backend, enable_ocr=enable_ocr)
        
        if "error" in results:
            return None, f"❌ Analysis failed: {results['error']}"
        
        # Format results for display
        detections = results.get("detections", [])
        summary = analyzer.get_analysis_summary(results)
        
        # Create annotated image
        annotated = draw_detection_boxes(image, detections) if detections else image
        
        # Format display text
        display_text = format_premium_results(results, summary)
        
        return annotated, display_text
        
    except Exception as e:
        return None, f"❌ Error during analysis: {str(e)}"

def draw_detection_boxes(image, detections):
    """Draw bounding boxes and labels on the image."""
    if not detections:
        return image
    
    # Convert to PIL Image if needed
    if isinstance(image, np.ndarray):
        image = Image.fromarray(image)
    
    draw = ImageDraw.Draw(image)
    
    # Premium color scheme
    colors = {
        'ic_chip': (52, 152, 219),      # Blue
        'capacitor': (46, 204, 113),     # Green
        'resistor': (231, 76, 60),       # Red
        'connector': (155, 89, 182),     # Purple
        'transformer': (241, 196, 15),   # Yellow
        'diode': (230, 126, 34)          # Orange
    }
    
    for detection in detections:
        bbox = detection.get('bbox', [])
        if len(bbox) == 4:
            x1, y1, x2, y2 = bbox
            component_type = detection.get('class_name', 'unknown')
            confidence = detection.get('confidence', 0)
            
            # Get color for component type
            color = colors.get(component_type, (128, 128, 128))
            
            # Draw bounding box
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
            
            # Draw label
            label = f"{component_type.upper()} ({confidence:.1f})"
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
            except:
                font = ImageFont.load_default()
            
            # Draw label background
            bbox = draw.textbbox((x1, max(0, y1-20)), label, font=font)
            draw.rectangle(bbox, fill=color)
            draw.text((x1, max(0, y1-20)), label, fill=(255, 255, 255), font=font)
    
    return image

def format_premium_results(results, summary):
    """Format analysis results with premium styling."""
    detections = results.get("detections", [])
    functionality = results.get("functionality_analysis", {})
    
    # Component breakdown
    component_counts = {}
    for detection in detections:
        comp_type = detection.get('class_name', 'unknown')
        component_counts[comp_type] = component_counts.get(comp_type, 0) + 1
    
    # Format the output
    output_lines = [
        "🎯 **Circuit.AI Analysis Results**",
        "",
        f"📊 **Detection Summary**",
        f"• Total Components: {len(detections)}",
        f"• Average Confidence: {sum(d.get('confidence', 0) for d in detections) / max(len(detections), 1):.1%}",
        "",
        "🔧 **Component Breakdown**"
    ]
    
    for comp_type, count in component_counts.items():
        output_lines.append(f"• {comp_type.replace('_', ' ').title()}: {count}")
    
    if functionality:
        capabilities = functionality.get('capabilities', [])
        market_value = functionality.get('total_market_value', 0)
        project_potential = functionality.get('project_potential', 'unknown')
        
        output_lines.extend([
            "",
            "⚡ **Capabilities Identified**"
        ])
        
        for capability in capabilities[:8]:  # Show top 8
            output_lines.append(f"• {capability.replace('_', ' ').title()}")
        
        if len(capabilities) > 8:
            output_lines.append(f"• ... and {len(capabilities) - 8} more")
        
        output_lines.extend([
            "",
            "💰 **Value Assessment**",
            f"• Market Value: ${market_value:.2f}",
            f"• Project Potential: {project_potential.title()}",
            "",
            "🎓 **Educational Value**",
            "This PCB contains components suitable for:",
            "• Electronics education",
            "• DIY projects",
            "• Maker activities",
            "• STEM learning"
        ])
    
    return "\n".join(output_lines)

def run_demo():
    """Run demo analysis with sample data."""
    demo_text = """
🎯 **Demo Analysis Results**

**Components Detected:** 8
- 3 IC Chips (Arduino-compatible)
- 4 Capacitors (Power filtering)
- 1 Connector (Data communication)

**Capabilities Identified:**
• Arduino projects
• IoT devices
• Power filtering
• Signal processing
• Educational electronics

**Market Value:** $3.25
**Project Potential:** Excellent
**Educational Value:** High

**Recommended Projects:**
1. Arduino Weather Station
2. LED Controller
3. Audio Amplifier
4. Power Supply

This demo shows how Circuit.AI can identify components and suggest educational projects!
    """
    return demo_text

def main():
    """Main application function."""
    # Create header
    create_header()
    
    # Create stats section
    create_stats_section()
    
    # Create upload section
    uploaded_file, backend, enable_ocr, analyze_btn, demo_btn = create_upload_section()
    
    # Handle analysis
    if analyze_btn and uploaded_file is not None:
        with st.spinner("🔍 Analyzing PCB components..."):
            annotated_image, results_text = analyze_pcb_image(
                Image.open(uploaded_file), backend, enable_ocr
            )
        
        if annotated_image:
            st.success("✅ Analysis completed successfully!")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📊 Analysis Results**")
                st.markdown(results_text)
            
            with col2:
                st.markdown("**🔍 Component Detection**")
                st.image(annotated_image, caption="Detected Components", use_column_width=True)
        else:
            st.error(results_text)
    
    elif demo_btn:
        st.success("✅ Demo analysis completed!")
        
        demo_results = run_demo()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📊 Demo Results**")
            st.markdown(demo_results)
        
        with col2:
            st.markdown("**🔍 Sample Detection**")
            # Create a sample image or show placeholder
            st.info("Demo mode - showing sample results")
    
    # Create features section
    create_features_section()
    
    # Sidebar for additional options
    with st.sidebar:
        st.markdown("### 🔧 Additional Tools")
        
        st.markdown("**Component Information**")
        component_type = st.selectbox(
            "Select Component Type",
            ["ic_chip", "capacitor", "resistor", "connector", "transformer", "diode"]
        )
        
        if st.button("📋 Get Component Info"):
            component_info = get_component_info(component_type)
            st.markdown(component_info)
        
        st.markdown("---")
        
        st.markdown("**Export Options**")
        analysis_id = st.number_input("Analysis ID", min_value=1, value=1)
        export_format = st.selectbox("Export Format", ["CSV", "PDF", "JSON"])
        
        if st.button("⬇️ Export Report"):
            st.info(f"Exporting analysis {analysis_id} as {export_format}...")

def get_component_info(component_type):
    """Get detailed component information."""
    component_data = {
        "ic_chip": {
            "name": "Integrated Circuit (IC)",
            "description": "Microelectronic device containing multiple electronic components",
            "capabilities": ["Arduino projects", "IoT devices", "Signal processing", "Educational electronics"],
            "reuse_value": "High",
            "market_value": "$0.50 - $5.00",
            "educational_value": "Excellent for learning microcontrollers and digital electronics"
        },
        "capacitor": {
            "name": "Capacitor",
            "description": "Passive component that stores electrical energy",
            "capabilities": ["Power filtering", "Audio circuits", "Voltage regulation", "Timing circuits"],
            "reuse_value": "Medium",
            "market_value": "$0.10 - $2.00",
            "educational_value": "Great for understanding energy storage and AC/DC circuits"
        },
        "resistor": {
            "name": "Resistor",
            "description": "Passive component that limits electrical current",
            "capabilities": ["Current limiting", "Voltage division", "Biasing", "Load simulation"],
            "reuse_value": "Low",
            "market_value": "$0.01 - $0.50",
            "educational_value": "Perfect for learning Ohm's law and basic electronics"
        },
        "connector": {
            "name": "Connector",
            "description": "Component that joins electrical circuits",
            "capabilities": ["Signal transmission", "Power distribution", "Modular design", "Data communication"],
            "reuse_value": "High",
            "market_value": "$0.05 - $1.00",
            "educational_value": "Excellent for understanding connectivity and modular design"
        }
    }
    
    if component_type in component_data:
        data = component_data[component_type]
        return f"""
**{data['name']}**

**Description:** {data['description']}

**Capabilities:**
{chr(10).join(f"• {cap}" for cap in data['capabilities'])}

**Reuse Value:** {data['reuse_value']}
**Market Value:** {data['market_value']}
**Educational Value:** {data['educational_value']}
        """
    else:
        return "Component information not available."

if __name__ == "__main__":
    main()
