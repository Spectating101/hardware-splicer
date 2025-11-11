import gradio as gr
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.core.ingest import CircuitAnalyzer
from src.demo.enhanced_demo_system import EnhancedDemoSystem


def draw_detection_boxes(image, detections):
    """Draw bounding boxes and labels on the image."""
    if not detections:
        return image
    
    # Convert to PIL Image if needed
    if isinstance(image, np.ndarray):
        image = Image.fromarray(image)
    
    draw = ImageDraw.Draw(image)
    
    # Color scheme for different component types
    colors = {
        'ic_chip': (255, 0, 0),      # Red
        'capacitor': (0, 255, 0),     # Green
        'resistor': (0, 0, 255),      # Blue
        'connector': (255, 255, 0),   # Yellow
        'transformer': (255, 0, 255), # Magenta
        'diode': (0, 255, 255)        # Cyan
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
            draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
            
            # Draw label
            label = f"{component_type} ({confidence:.2f})"
            draw.text((x1, max(0, y1-18)), label, fill=color)

            # Draw OCR/part number if available
            ocr_text = detection.get('ocr_text') or detection.get('part_number')
            if ocr_text:
                try:
                    draw.text((x1, min(y2 + 2, image.height - 12)), str(ocr_text)[:30], fill=color)
                except Exception:
                    pass
    
    return image


def analyze_pcb_image(image, backend: str, enable_ocr: bool):
    """Analyze uploaded PCB image using selected backend with optional OCR."""
    if image is None:
        return "Please upload a PCB image.", None
    
    try:
        # Convert to numpy array
        if isinstance(image, np.ndarray):
            image_np = image
        else:
            image_np = np.array(image)
        
        if backend == 'demo':
            demo_system = EnhancedDemoSystem()
            detections = demo_system.generate_realistic_detections(image_np)
            summary = demo_system.generate_analysis_summary(detections)
            recommendations = demo_system.generate_project_recommendations(detections)
            annotated_image = demo_system.create_enhanced_demo_image(detections, image_np)
            display_text = format_enhanced_results_for_display(detections, summary, recommendations)
            return display_text, annotated_image
        else:
            analyzer = CircuitAnalyzer()
            results = analyzer.analyze_pcb(image_np, backend=backend, enable_ocr=enable_ocr)
            if "error" in results:
                return f"❌ Analysis failed: {results['error']}", None
            summary = analyzer.get_analysis_summary(results)
            # Draw detection boxes on image
            detections = results.get("detections", [])
            annotated = draw_detection_boxes(image, detections) if detections else image
            display_text = format_results_for_display(results, summary)
            return display_text, annotated
        
    except Exception as e:
        return f"❌ Error during analysis: {str(e)}", None


def format_results_for_display(results, summary):
    """Format analysis results for Gradio display with enhanced information."""
    detection_summary = results.get("detection_summary", {})
    functionality_data = results.get("functionality_analysis", {})
    recommendations = results.get("project_recommendations", [])
    
    # Build display text
    display_text = f"🔍 Circuit.AI Analysis Results\n"
    display_text += "=" * 50 + "\n\n"
    
    # Detection results
    total_components = detection_summary.get("total_components", 0)
    detection_quality = detection_summary.get("detection_quality", "unknown")
    avg_confidence = detection_summary.get("average_confidence", 0)
    
    display_text += f"📊 Detection Results:\n"
    display_text += f"   • Total Components: {total_components}\n"
    display_text += f"   • Detection Quality: {detection_quality}\n"
    display_text += f"   • Average Confidence: {avg_confidence:.2f}\n\n"
    
    # Component breakdown with market values
    components_by_type = detection_summary.get("components_by_type", {})
    if components_by_type:
        display_text += f"🔧 Component Breakdown:\n"
        total_value = 0
        for comp_type, count in components_by_type.items():
            # Get market value from functionality data
            market_value = 0.0
            for comp in functionality_data.get("components", []):
                if comp.get("type") == comp_type:
                    market_value = comp.get("market_value", 0.0)
                    break
            
            component_value = market_value * count
            total_value += component_value
            
            display_text += f"   • {comp_type}: {count} units (${component_value:.2f})\n"
        
        display_text += f"   💰 Total Estimated Value: ${total_value:.2f}\n\n"
    
    # Capabilities
    capabilities = functionality_data.get("capabilities", [])
    if capabilities:
        display_text += f"⚡ Capabilities Detected:\n"
        for capability in capabilities:
            display_text += f"   • {capability}\n"
        display_text += "\n"
    
    # Project potential
    project_potential = functionality_data.get("project_potential", "none")
    educational_potential = functionality_data.get("educational_potential", "none")
    display_text += f"🎯 Project Potential: {project_potential.upper()}\n"
    display_text += f"📚 Educational Potential: {educational_potential.upper()}\n\n"
    
    # Recommendations with enhanced details
    if recommendations:
        display_text += f"💡 Top Project Recommendations:\n"
        for i, rec in enumerate(recommendations[:3], 1):
            display_text += f"   {i}. {rec['name']}\n"
            display_text += f"      Difficulty: {rec['difficulty']}\n"
            display_text += f"      Time: {rec['time_estimate']}\n"
            display_text += f"      Score: {rec['score']:.2f}\n"
            display_text += f"      Market Value: ${rec.get('market_value', 0):.2f}\n"
            display_text += f"      Skills: {', '.join(rec.get('skills_learned', []))}\n"
            display_text += f"      Description: {rec['description']}\n\n"
    
    # Summary
    display_text += f"📝 Summary:\n"
    display_text += f"   {summary.get('summary_text', 'No summary available.')}\n"
    
    return display_text


def format_enhanced_results_for_display(detections, summary, recommendations):
    """Format enhanced analysis results for display."""
    output = []
    
    # Header
    output.append("🔍 **Circuit.AI Enhanced Analysis Results**")
    output.append("=" * 50)
    output.append("")
    
    # Detection Summary
    if summary:
        output.append("📊 **Component Detection:**")
        total_components = summary.get("total_components", 0)
        output.append(f"   • Total Components: {total_components}")
        
        component_types = summary.get("component_types", {})
        if component_types:
            output.append("   • Component Breakdown:")
            for comp_type, count in component_types.items():
                output.append(f"     - {comp_type}: {count}")
        
        total_value = summary.get("total_market_value", 0)
        output.append(f"   • Total Market Value: ${total_value:.2f}")
        
        educational_potential = summary.get("educational_potential", "unknown")
        output.append(f"   • Educational Potential: {educational_potential}")
        
        reuse_potential = summary.get("reuse_potential", "unknown")
        output.append(f"   • Reuse Potential: {reuse_potential}")
        output.append("")
    
    # Component Details
    if detections:
        output.append("🔧 **Detected Components:**")
        for i, detection in enumerate(detections, 1):
            comp_type = detection.get("class_name", "unknown")
            confidence = detection.get("confidence", 0)
            variant = detection.get("variant", "")
            market_value = detection.get("market_value", 0)
            capabilities = detection.get("capabilities", [])
            
            output.append(f"   {i}. **{comp_type}** ({variant})")
            output.append(f"      Confidence: {confidence:.2f}")
            output.append(f"      Market Value: ${market_value:.2f}")
            output.append(f"      Capabilities: {', '.join(capabilities[:3])}")
            output.append("")
    
    # Project Recommendations
    if recommendations:
        output.append("💡 **Top Project Recommendations:**")
        for i, rec in enumerate(recommendations, 1):
            output.append(f"   {i}. **{rec['name']}**")
            output.append(f"      Description: {rec['description']}")
            output.append(f"      Difficulty: {rec['difficulty']}")
            output.append(f"      Time: {rec['time_estimate']}")
            output.append(f"      Score: {rec['score']:.2f}")
            output.append(f"      Estimated Cost: {rec['estimated_cost']}")
            output.append(f"      Safety Level: {rec['safety_level']}")
            output.append(f"      Skills: {', '.join(rec['skills_learned'][:3])}")
            output.append("")
    
    return "\n".join(output)


def demo_analysis():
    """Run demo analysis with sample data."""
    analyzer = CircuitAnalyzer()
    results = analyzer.generate_demo_data()
    summary = analyzer.get_analysis_summary(results)
    
    return format_results_for_display(results, summary), None


def get_component_info(component_type):
    """Get detailed information about a specific component type."""
    analyzer = CircuitAnalyzer()
    mapper = analyzer.mapper
    
    component_info = mapper.component_database.get(component_type, {})
    
    if not component_info:
        return f"No information available for {component_type}"
    
    info_text = f"📋 Component Information: {component_type.upper()}\n"
    info_text += "=" * 40 + "\n\n"
    
    info_text += f"Type: {component_info.get('type', 'Unknown')}\n"
    info_text += f"Reuse Value: {component_info.get('reuse_value', 'Unknown')}\n"
    info_text += f"Difficulty: {component_info.get('difficulty', 'Unknown')}\n"
    info_text += f"Market Value: ${component_info.get('market_value', 0):.2f}\n"
    info_text += f"Educational Value: {component_info.get('educational_value', 'Unknown')}\n\n"
    
    info_text += f"Capabilities:\n"
    for capability in component_info.get('capabilities', []):
        info_text += f"  • {capability}\n"
    
    info_text += f"\nRepair Guide:\n{component_info.get('repair_guide', 'No repair guide available')}\n"
    
    return info_text


# Create Gradio interface
def create_interface():
    """Create the enhanced Gradio interface."""
    
    with gr.Blocks(
        title="Circuit.AI - Component Intelligence Platform",
        theme=gr.themes.Soft()
    ) as interface:
        
        gr.Markdown("""
        # 🔍 Circuit.AI - Component Intelligence Platform
        
        Transform electronic waste into educational and creative opportunities through AI-powered component analysis.
        
        **How it works:**
        1. Upload a PCB image
        2. AI detects and analyzes components
        3. Get functional insights and project recommendations
        4. Learn what you can build with salvaged parts
        """)
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📁 Upload PCB Image")
                image_input = gr.Image(
                    label="Upload PCB Image",
                    type="pil",
                    height=300
                )
                backend_dropdown = gr.Dropdown(
                    choices=["classical", "yolo", "demo"],
                    value="classical",
                    label="Detection backend"
                )
                ocr_checkbox = gr.Checkbox(value=True, label="Enable OCR (IC/connector text)")
                
                with gr.Row():
                    analyze_btn = gr.Button("🔍 Analyze PCB", variant="primary")
                    demo_btn = gr.Button("📊 Run Demo", variant="secondary")
                
                gr.Markdown("### 🔧 Component Information")
                component_dropdown = gr.Dropdown(
                    choices=["ic_chip", "capacitor", "resistor", "connector", "transformer", "diode"],
                    label="Select Component Type",
                    value="ic_chip"
                )
                component_info_btn = gr.Button("📋 Get Component Info")
            
            with gr.Column(scale=1):
                gr.Markdown("### 📊 Analysis Results")
                api_base = gr.Textbox(value="http://localhost:8000", label="API Base URL")
                results_output = gr.Textbox(
                    label="Analysis Results",
                    lines=25,
                    max_lines=30,
                    interactive=False
                )
                recent_btn = gr.Button("🕘 Load Recent Analyses")
                with gr.Row():
                    page_size = gr.Number(value=10, precision=0, label="Page Size")
                    page_offset = gr.Number(value=0, precision=0, label="Offset")
                with gr.Row():
                    date_from = gr.Textbox(value="", label="From (YYYY-MM-DD)")
                    date_to = gr.Textbox(value="", label="To (YYYY-MM-DD)")
                with gr.Row():
                    backend_filter = gr.Dropdown(choices=["", "classical", "yolo", "demo"], value="", label="Backend")
                    min_conf = gr.Number(value=None, label="Min Confidence")
                recent_output = gr.Textbox(label="Recent Analyses", lines=8, interactive=False)
                export_id_input = gr.Number(label="Analysis ID for Export", precision=0)
                with gr.Row():
                    export_csv_btn = gr.Button("⬇️ Export CSV")
                    export_pdf_btn = gr.Button("🧾 Export PDF")
                export_msg = gr.Textbox(label="Export Status", lines=2, interactive=False)
                
                gr.Markdown("### 🖼️ Annotated Image")
                annotated_image_output = gr.Image(
                    label="Component Detection",
                    height=300
                )
        
        # Event handlers
        analyze_btn.click(
            fn=analyze_pcb_image,
            inputs=[image_input, backend_dropdown, ocr_checkbox],
            outputs=[results_output, annotated_image_output]
        )
        
        demo_btn.click(
            fn=analyze_pcb_image,
            inputs=[image_input, gr.State("demo"), gr.State(False)],
            outputs=[results_output, annotated_image_output]
        )

        def load_recent(limit=10, offset=0, date_from_val="", date_to_val="", backend_val="", min_conf_val=None, api="http://localhost:8000"):
            import requests
            try:
                params = {"limit": int(limit), "offset": int(offset)}
                if date_from_val:
                    params["date_from"] = date_from_val
                if date_to_val:
                    params["date_to"] = date_to_val
                if backend_val:
                    params["backend"] = backend_val
                if min_conf_val is not None and min_conf_val != "":
                    params["min_conf"] = float(min_conf_val)
                data = requests.get(f"{api}/analyses", params=params).json()
                lines = [f"{a['id']}: {a['image_path']} ({a['analysis_date']}) - {a['total_components']} comps" for a in data.get('analyses', [])]
                return "\n".join(lines[:10]) or "No recent analyses"
            except Exception as e:
                return f"Failed to load: {e}"

        recent_btn.click(fn=load_recent, inputs=[page_size, page_offset, date_from, date_to, backend_filter, min_conf, api_base], outputs=[recent_output])

        def export_csv(analysis_id, api="http://localhost:8000"):
            import requests
            try:
                analysis_id = int(analysis_id)
                url = f"{api}/analyses/{analysis_id}/export.csv"
                r = requests.get(url)
                if r.status_code == 200:
                    # Save to downloads folder
                    from pathlib import Path
                    out = Path.cwd() / f"analysis_{analysis_id}.csv"
                    out.write_bytes(r.content)
                    return f"Saved to {out}"
                return f"Failed: {r.status_code}"
            except Exception as e:
                return f"Error: {e}"

        export_csv_btn.click(fn=export_csv, inputs=[export_id_input, api_base], outputs=[export_msg])

        def export_pdf(analysis_id, api="http://localhost:8000"):
            import requests
            try:
                analysis_id = int(analysis_id)
                url = f"{api}/analyses/{analysis_id}/report.pdf"
                r = requests.get(url)
                if r.status_code == 200:
                    from pathlib import Path
                    out = Path.cwd() / f"analysis_{analysis_id}.pdf"
                    out.write_bytes(r.content)
                    return f"Saved to {out}"
                return f"Failed: {r.status_code}"
            except Exception as e:
                return f"Error: {e}"

        export_pdf_btn.click(fn=export_pdf, inputs=[export_id_input, api_base], outputs=[export_msg])

        # Stats panel
        with gr.Accordion("📈 System Statistics", open=False):
            stats_btn = gr.Button("Refresh Stats")
            stats_output = gr.Textbox(label="Stats", lines=12, interactive=False)

        def load_stats(api="http://localhost:8000"):
            import requests
            try:
                data = requests.get(f"{api}/statistics").json()
                comp = data.get("component_statistics", {})
                proj = data.get("project_statistics", {})
                perf = data.get("performance", {})
                lines = [
                    "Component Stats:", json.dumps(comp, indent=2),
                    "\nProject Stats:", json.dumps(proj, indent=2),
                    "\nPerformance:", json.dumps(perf, indent=2),
                ]
                return "\n".join(lines)
            except Exception as e:
                return f"Failed to load stats: {e}"

        stats_btn.click(fn=load_stats, inputs=[api_base], outputs=[stats_output])
        
        component_info_btn.click(
            fn=get_component_info,
            inputs=[component_dropdown],
            outputs=[results_output]
        )
        
        # Instructions
        gr.Markdown("""
        ### 🎯 What Circuit.AI Does
        
        **Component Detection:**
        - Identifies ICs, capacitors, resistors, connectors, transformers, diodes
        - Assesses component condition and reusability
        - Calculates detection confidence and market value
        
        **Functional Intelligence:**
        - Maps components to their capabilities
        - Identifies educational and project potential
        - Suggests what can be built with available parts
        
        **Project Recommendations:**
        - Arduino weather stations
        - Audio amplifiers
        - LED controllers
        - Power supplies
        - Data loggers
        - And many more educational projects
        
        ### 🚀 Getting Started
        
        1. **Upload a PCB image** from a discarded electronic device
        2. **Click "Analyze PCB"** to run the AI analysis
        3. **Review the results** to see detected components and capabilities
        4. **Explore project recommendations** to learn what you can build
        5. **Try the demo** to see sample results
        6. **Get component info** to learn about specific parts
        
        ### 💡 Educational Value
        
        Circuit.AI transforms e-waste from "trash" to "educational resources" by:
        - Teaching electronics through salvaged components
        - Encouraging hands-on learning and experimentation
        - Reducing waste through intelligent reuse
        - Building maker skills and creativity
        - Providing repair guides and safety information
        """)
    
    return interface


if __name__ == "__main__":
    # Create and launch interface
    interface = create_interface()
    import os
    port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
    interface.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=False
    )