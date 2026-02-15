#!/usr/bin/env python3
"""
Circuit.AI - Premium Gradio Interface
====================================

A professional, premium-looking web interface for Circuit.AI
with modern styling, better layout, and enhanced user experience.
"""

import gradio as gr
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json
import requests
from pathlib import Path
import sys
from typing import Optional, Tuple, Dict, Any

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.core.ingest import CircuitAnalyzer


# Custom CSS for premium styling
CUSTOM_CSS = """
/* Premium Circuit.AI Styling */
.gradio-container {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    padding: 20px;
}

.main-container {
    background: rgba(255, 255, 255, 0.95);
    border-radius: 20px;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
    backdrop-filter: blur(10px);
    margin: 20px;
    padding: 30px;
}

.header {
    text-align: center;
    margin-bottom: 40px;
    padding: 30px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 15px;
    color: white;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}

.header h1 {
    font-size: 3em;
    font-weight: 700;
    margin: 0;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.header p {
    font-size: 1.3em;
    opacity: 0.9;
    margin: 15px 0 0 0;
}

.upload-section {
    background: white;
    border-radius: 15px;
    padding: 30px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
    margin-bottom: 30px;
    border: 1px solid #e1e5e9;
}

.results-section {
    background: white;
    border-radius: 15px;
    padding: 30px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
    margin-bottom: 30px;
    border: 1px solid #e1e5e9;
}

.stats-section {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    border-radius: 15px;
    padding: 25px;
    color: white;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
    margin-bottom: 30px;
}

.component-card {
    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    border-radius: 10px;
    padding: 15px;
    margin: 10px 0;
    color: white;
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin: 20px 0;
}

.stat-card {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 20px;
    text-align: center;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.2);
}

.stat-number {
    font-size: 2.5em;
    font-weight: 700;
    color: white;
    margin: 0;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.stat-label {
    color: rgba(255, 255, 255, 0.9);
    font-size: 1em;
    margin: 5px 0 0 0;
    font-weight: 500;
}

.button-primary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    padding: 15px 30px !important;
    border-radius: 12px !important;
    transition: all 0.3s ease !important;
    font-size: 1.1em !important;
    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3) !important;
}

.button-primary:hover {
    transform: translateY(-3px) !important;
    box-shadow: 0 15px 30px rgba(102, 126, 234, 0.4) !important;
}

.button-secondary {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    padding: 12px 24px !important;
    border-radius: 10px !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 5px 15px rgba(240, 147, 251, 0.3) !important;
}

.button-secondary:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 10px 20px rgba(240, 147, 251, 0.4) !important;
}

.dropdown-styled {
    border-radius: 10px !important;
    border: 2px solid #e1e5e9 !important;
    padding: 12px 16px !important;
    font-size: 1em !important;
}

.textbox-styled {
    border-radius: 10px !important;
    border: 2px solid #e1e5e9 !important;
    padding: 15px !important;
    font-size: 1em !important;
    background: #fafbfc !important;
}

.image-container {
    border-radius: 15px;
    overflow: hidden;
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
    border: 3px solid #e1e5e9;
}

.loading-animation {
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 3px solid #f3f3f3;
    border-top: 3px solid #667eea;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.progress-bar {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    height: 8px;
    border-radius: 4px;
    transition: width 0.3s ease;
}

.feature-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 25px;
    margin: 40px 0;
}

.feature-card {
    background: white;
    border-radius: 20px;
    padding: 30px;
    text-align: center;
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
    transition: all 0.3s ease;
    border: 1px solid #e1e5e9;
}

.feature-card:hover {
    transform: translateY(-8px);
    box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
}

.feature-icon {
    font-size: 4em;
    margin-bottom: 20px;
    display: block;
}

.feature-title {
    font-size: 1.5em;
    font-weight: 700;
    color: #333;
    margin-bottom: 15px;
}

.feature-description {
    color: #666;
    line-height: 1.7;
    font-size: 1.1em;
}

/* Custom styling for specific elements */
#component-info {
    background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
    border-radius: 15px;
    padding: 25px;
    margin: 20px 0;
}

#analysis-results {
    background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
    border-radius: 15px;
    padding: 25px;
    margin: 20px 0;
}

/* Responsive design */
@media (max-width: 768px) {
    .header h1 {
        font-size: 2em;
    }
    
    .feature-grid {
        grid-template-columns: 1fr;
    }
    
    .stats-grid {
        grid-template-columns: 1fr;
    }
}
"""


def create_premium_interface():
    """Create a premium-looking Gradio interface."""
    
    with gr.Blocks(css=CUSTOM_CSS, title="Circuit.AI - Component Intelligence Platform") as interface:
        
        # Header Section
        gr.HTML("""
        <div class="header">
            <h1>🔌 Circuit.AI</h1>
            <p>Transform e-waste into educational opportunities through AI-powered component analysis</p>
        </div>
        """)
        
        # Main Content
        with gr.Row():
            with gr.Column(scale=2):
                
                # Upload Section
                with gr.Group(elem_classes="upload-section"):
                    gr.Markdown("### 📸 Upload PCB Image")
                    
                    with gr.Row():
                        with gr.Column(scale=2):
                            image_input = gr.Image(
                                label="Upload PCB Image",
                                type="pil",
                                height=350,
                                elem_classes="image-container"
                            )
                        
                        with gr.Column(scale=1):
                            gr.Markdown("**🔧 Analysis Settings**")
                            
                            backend_dropdown = gr.Dropdown(
                                choices=["classical", "yolo", "demo"],
                                value="classical",
                                label="Detection Backend",
                                elem_classes="dropdown-styled"
                            )
                            
                            ocr_checkbox = gr.Checkbox(
                                label="Enable OCR (Text Recognition)",
                                value=True
                            )
                            
                            analyze_btn = gr.Button(
                                "🔍 Analyze PCB",
                                variant="primary",
                                elem_classes="button-primary",
                                size="lg"
                            )
                            
                            demo_btn = gr.Button(
                                "🎯 Run Demo",
                                variant="secondary",
                                elem_classes="button-secondary"
                            )
                
                # Results Section
                with gr.Group(elem_classes="results-section"):
                    gr.Markdown("### 📊 Analysis Results")
                    
                    with gr.Row():
                        with gr.Column(scale=1):
                            results_output = gr.Textbox(
                                label="Analysis Results",
                                lines=20,
                                interactive=False,
                                elem_classes="textbox-styled"
                            )
                        
                        with gr.Column(scale=1):
                            annotated_image = gr.Image(
                                label="Component Detection",
                                height=350,
                                elem_classes="image-container"
                            )
                
                # Component Information
                with gr.Group(elem_classes="results-section"):
                    gr.Markdown("### 🔧 Component Information")
                    
                    with gr.Row():
                        component_dropdown = gr.Dropdown(
                            choices=["ic_chip", "capacitor", "resistor", "connector", "transformer", "diode"],
                            value="ic_chip",
                            label="Select Component Type",
                            elem_classes="dropdown-styled"
                        )
                        
                        component_info_btn = gr.Button(
                            "📋 Get Component Info",
                            variant="secondary",
                            elem_classes="button-secondary"
                        )
                    
                    component_info_output = gr.Textbox(
                        label="Component Details",
                        lines=10,
                        interactive=False,
                        elem_classes="textbox-styled"
                    )
            
            with gr.Column(scale=1):
                
                # Statistics Dashboard
                with gr.Group(elem_classes="stats-section"):
                    gr.Markdown("### 📈 Live Statistics")
                    
                    with gr.Row():
                        with gr.Column(scale=1):
                            total_analyses = gr.Number(
                                label="Total Analyses",
                                value=0,
                                interactive=False
                            )
                        
                        with gr.Column(scale=1):
                            total_components = gr.Number(
                                label="Components Detected",
                                value=0,
                                interactive=False
                            )
                    
                    with gr.Row():
                        with gr.Column(scale=1):
                            avg_confidence = gr.Number(
                                label="Avg Confidence",
                                value=0.0,
                                interactive=False
                            )
                        
                        with gr.Column(scale=1):
                            processing_time = gr.Number(
                                label="Avg Processing Time (s)",
                                value=0.0,
                                interactive=False
                            )
                    
                    refresh_stats_btn = gr.Button(
                        "🔄 Refresh Statistics",
                        variant="secondary",
                        elem_classes="button-secondary"
                    )
                
                # Recent Analyses
                with gr.Group(elem_classes="results-section"):
                    gr.Markdown("### 📋 Recent Analyses")
                    
                    recent_analyses_output = gr.Textbox(
                        label="Recent Activity",
                        lines=12,
                        interactive=False,
                        elem_classes="textbox-styled"
                    )
                    
                    load_recent_btn = gr.Button(
                        "📥 Load Recent",
                        variant="secondary",
                        elem_classes="button-secondary"
                    )
                
                # Export Options
                with gr.Group(elem_classes="results-section"):
                    gr.Markdown("### 📤 Export Options")
                    
                    with gr.Row():
                        export_id_input = gr.Number(
                            label="Analysis ID",
                            value=1,
                            minimum=1
                        )
                        
                        export_format = gr.Dropdown(
                            choices=["CSV", "PDF", "JSON"],
                            value="CSV",
                            label="Export Format",
                            elem_classes="dropdown-styled"
                        )
                    
                    export_btn = gr.Button(
                        "⬇️ Export Report",
                        variant="primary",
                        elem_classes="button-primary"
                    )
                    
                    export_status = gr.Textbox(
                        label="Export Status",
                        lines=3,
                        interactive=False,
                        elem_classes="textbox-styled"
                    )
        
        # Features Section
        gr.HTML("""
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
        """)
        
        # Event Handlers
        def analyze_pcb(image, backend, enable_ocr):
            """Analyze PCB image with premium formatting."""
            if image is None:
                return "Please upload a PCB image to begin analysis.", None, 0, 0, 0.0, 0.0
            
            try:
                # Convert to numpy array
                if isinstance(image, np.ndarray):
                    image_np = image
                else:
                    image_np = np.array(image)
                
                analyzer = CircuitAnalyzer()
                results = analyzer.analyze_pcb(image_np, backend=backend, enable_ocr=enable_ocr)
                
                if "error" in results:
                    return f"❌ Analysis failed: {results['error']}", None, 0, 0, 0.0, 0.0
                
                # Format results for display
                detections = results.get("detections", [])
                summary = analyzer.get_analysis_summary(results)
                
                # Create annotated image
                annotated = draw_detection_boxes(image, detections) if detections else image
                
                # Format display text
                display_text = format_premium_results(results, summary)
                
                # Update statistics
                total_components = len(detections)
                avg_confidence = sum(d.get('confidence', 0) for d in detections) / max(len(detections), 1)
                processing_time = results.get('analysis_metadata', {}).get('timing_seconds', 0.0)
                
                return display_text, annotated, 1, total_components, avg_confidence, processing_time
                
            except Exception as e:
                return f"❌ Error during analysis: {str(e)}", None, 0, 0, 0.0, 0.0
        
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
            return demo_text, None, 1, 8, 0.85, 0.35
        
        def refresh_statistics():
            """Refresh system statistics."""
            try:
                response = requests.get("http://localhost:8000/statistics")
                if response.status_code == 200:
                    stats = response.json()
                    return (
                        stats.get('total_analyses', 0),
                        stats.get('total_components', 0),
                        stats.get('average_confidence', 0.0),
                        stats.get('average_processing_time', 0.0)
                    )
                else:
                    return 0, 0, 0.0, 0.0
            except Exception:
                return 0, 0, 0.0, 0.0
        
        def load_recent_analyses():
            """Load recent analysis history."""
            try:
                response = requests.get("http://localhost:8000/analyses?limit=5")
                if response.status_code == 200:
                    analyses = response.json()
                    if analyses:
                        lines = ["**Recent Analyses:**"]
                        for analysis in analyses[:5]:
                            lines.append(f"• Analysis #{analysis.get('id', 'N/A')} - {analysis.get('timestamp', 'Unknown')}")
                        return "\n".join(lines)
                    else:
                        return "No recent analyses found."
                else:
                    return "Unable to load recent analyses."
            except Exception:
                return "Unable to connect to analysis service."
        
        def export_report(analysis_id, export_format):
            """Export analysis report."""
            try:
                analysis_id = int(analysis_id)
                if export_format == "CSV":
                    url = f"http://localhost:8000/analyses/{analysis_id}/export.csv"
                elif export_format == "PDF":
                    url = f"http://localhost:8000/analyses/{analysis_id}/report.pdf"
                else:
                    url = f"http://localhost:8000/analyses/{analysis_id}/export.json"
                
                response = requests.get(url)
                if response.status_code == 200:
                    filename = f"circuit_ai_analysis_{analysis_id}.{export_format.lower()}"
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    return f"✅ Report exported successfully to {filename}"
                else:
                    return f"❌ Export failed: HTTP {response.status_code}"
            except Exception as e:
                return f"❌ Export error: {str(e)}"
        
        # Connect event handlers
        analyze_btn.click(
            fn=analyze_pcb,
            inputs=[image_input, backend_dropdown, ocr_checkbox],
            outputs=[results_output, annotated_image, total_analyses, total_components, avg_confidence, processing_time]
        )
        
        demo_btn.click(
            fn=run_demo,
            outputs=[results_output, annotated_image, total_analyses, total_components, avg_confidence, processing_time]
        )
        
        component_info_btn.click(
            fn=get_component_info,
            inputs=[component_dropdown],
            outputs=[component_info_output]
        )
        
        refresh_stats_btn.click(
            fn=refresh_statistics,
            outputs=[total_analyses, total_components, avg_confidence, processing_time]
        )
        
        load_recent_btn.click(
            fn=load_recent_analyses,
            outputs=[recent_analyses_output]
        )
        
        export_btn.click(
            fn=export_report,
            inputs=[export_id_input, export_format],
            outputs=[export_status]
        )
    
    return interface


def draw_detection_boxes(image, detections):
    """Draw bounding boxes and labels on the image with premium styling."""
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
            
            # Draw bounding box with rounded corners effect
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
            
            # Draw label with background
            label = f"{component_type.upper()} ({confidence:.1f})"
            try:
                # Try to use a nice font
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
            except Exception:
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


if __name__ == "__main__":
    # Create and launch premium interface
    interface = create_premium_interface()
    import os
    port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
    interface.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=False,
        show_error=True
    )
