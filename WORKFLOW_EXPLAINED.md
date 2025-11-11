# Circuit.AI - Complete Workflow Explained

## How Everything Works Together

---

## **The 3 Main Systems**

### 1. **Vision System** (ML - Trained)
- **What**: YOLOv8m model detects components in PCB images
- **Status**: ✅ Trained (93.8% accuracy)
- **Input**: PCB image
- **Output**: List of components with bounding boxes
```python
# Example output:
[
  {"class": "Arduino-Nano", "confidence": 0.96, "bbox": [100, 100, 200, 200]},
  {"class": "Capacitor", "confidence": 0.85, "bbox": [250, 150, 270, 170]},
  {"class": "Resistor", "confidence": 0.82, "bbox": [300, 200, 320, 210]}
]
```

### 2. **Knowledge Base** (Database - Ready)
- **What**: 28K fault patterns + 35K Q&A from experts
- **Status**: ✅ Built (112 MB)
- **Input**: Symptom keywords
- **Output**: Matching repair patterns
```python
# Example:
User: "Arduino won't turn on"
Search keywords: ["not", "turn", "on", "arduino"]
Results: 234 matching fault patterns with diagnostic steps
```

### 3. **Intelligence Modules** (Algorithms - Ready)
- **What**: 9 specialized analysis modules (no ML training needed)
- **Status**: ✅ All functional
- **Examples**:
  - Circuit topology analysis
  - Electrical calculations (power, voltage, current)
  - Trace following
  - Component value extraction
  - Safety validation
  - Repair guidance generation

---

## **Complete User Journey**

### **Step 1: User Uploads Image**
```
User → Frontend → WebSocket API → Backend
```
- User takes photo of broken PCB
- Uploads via web interface
- Image sent to server via WebSocket

### **Step 2: Component Detection** ✨ (Uses trained ML model)
```python
# Backend code
model = YOLO("pcb_runs/electrocom61_full_production/weights/best.pt")
results = model.predict(user_image)

detected = [
    "Arduino-Nano",
    "CH340G",  # USB chip
    "Voltage-Regulator",
    "Capacitor" (x3),
    "LED",
    "Resistor" (x2)
]
```

**What happens**: ML model identifies all components visually

### **Step 3: Pin-Level Analysis** (Uses pinout database)
```python
# For known ICs
if "Arduino-Nano" in detected:
    pinout = load_pinout("ATmega328P")
    # Returns:
    # Pin 7 = VCC (5V power)
    # Pin 8 = GND
    # Pin 9 = PB6/XTAL1
    # etc...
```

**What happens**: System knows exactly what each pin does

### **Step 4: Circuit Analysis** (Algorithmic - no ML)
```python
from src.intelligence.circuit_analyzer import circuit_intelligence

topology = circuit_intelligence.analyze_circuit(detected, image)

# Returns:
{
    "device_type": "arduino",
    "device_confidence": 0.95,
    "power_budget": "0.76W",
    "thermal_estimate": "32.6°C",
    "functional_blocks": [
        "microcontroller",
        "usb_serial",
        "power_regulation"
    ]
}
```

**What happens**: System understands the circuit's purpose

### **Step 5: User Describes Problem**
```
User: "My Arduino won't upload code. Computer doesn't recognize it."
```

### **Step 6: Symptom Search** (Uses knowledge base)
```python
# Backend searches 28K patterns
symptoms = ["not recognized", "won't upload", "usb"]
matches = search_knowledge_base(symptoms)

# Top matches:
1. "USB chip overheating" (confidence: 0.87)
   - Symptom: Computer doesn't recognize
   - Component: CH340G
   - Steps: Check if chip is hot, measure voltage at pins

2. "USB cable damaged" (confidence: 0.72)
   - Symptom: Not recognized
   - Steps: Try different cable

3. "Bootloader corruption" (confidence: 0.65)
   - Symptom: Won't upload
   - Steps: Re-burn bootloader via ISP
```

**What happens**: Knowledge base finds relevant repair patterns

### **Step 7: Conversational Diagnosis** (Your API key + our data)
```python
import openai

# Build context from our data
context = f"""
Detected components:
{detected}

Pin information for ATmega328P:
{pinout}

User problem: {user_problem}

Relevant fault patterns:
{top_3_matches}

Previous measurements (if any):
{measurement_history}
"""

# Call YOUR API
response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are an expert electronics repair technician."},
        {"role": "user", "content": context}
    ]
)

# LLM intelligently interprets everything
chatbot_response = response.choices[0].message.content
```

**What happens**:
- Our system provides the facts (detected components, pinouts, fault patterns)
- Your LLM API provides the intelligence (reasoning, asking questions, explaining)

### **Step 8: Interactive Troubleshooting**
```
Chatbot: "I see you have a CH340G USB chip. Can you feel if it's warm or hot to touch?"
User: "Yes, it's really hot!"
Chatbot: "⚠️ CRITICAL: Disconnect USB immediately! The CH340G is overheating."

[Updates state to DIAGNOSING → MEASURING]

Chatbot: "Once it cools, measure voltage at Pin 4 (VCC). Should be 3.3V. What do you get?"
User: "I measure 5.2V"
Chatbot: "That's the problem! The chip is getting 5V instead of 3.3V. The voltage regulator might be broken..."
```

**What happens**:
- State machine tracks conversation flow
- LLM asks relevant follow-up questions
- System updates based on user responses

### **Step 9: Visual Overlay** (Algorithmic)
```python
from src.intelligence.visual_overlay import overlay_generator

annotated_image = overlay_generator.create_overlay(
    original_image=user_image,
    instructions=[
        {"type": "arrow", "point": (120, 150), "label": "Measure voltage here"},
        {"type": "circle", "bbox": ch340_bbox, "color": "red", "label": "HOT!"},
        {"type": "arrow", "point": (200, 180), "label": "Check this regulator"}
    ]
)
```

**What happens**: User sees exactly where to measure/fix on their specific board

### **Step 10: Guided Repair**
```
Chatbot shows step-by-step with images:

Step 1: ⚠️ Disconnect all power
Step 2: 📸 [Shows image with arrow] Remove this regulator
Step 3: 🔍 [Shows datasheet] Replace with AMS1117-3.3
Step 4: ⚡ [Shows soldering technique] Solder new regulator
Step 5: ✅ Power on and test voltage (should be 3.3V now)
```

---

## **What Each System Does**

### Vision Model (Trained ML)
**Purpose**: See what components are on the board
**Analogy**: Like having eyes - can identify things visually
**How it works**:
- Trained on 1,478 images with 61 component types
- Uses YOLO object detection
- Returns bounding boxes + class names + confidence

**Example**:
```
Input: Photo of Arduino
Output: "Arduino-Nano at 96% confidence at position (100,100)"
```

### Knowledge Base (Structured Data)
**Purpose**: Remember 28K ways electronics break and how to fix them
**Analogy**: Like a massive repair manual
**How it works**:
- 28K fault patterns from Stack Exchange experts
- 35K Q&A pairs
- Keyword search index (6,951 keywords)
- No ML - just fast lookup

**Example**:
```
Input: "won't turn on"
Output: 234 patterns mentioning power issues with fix steps
```

### Intelligence Modules (Algorithms)
**Purpose**: Understand circuits and calculate electrical properties
**Analogy**: Like an engineer's brain - knows circuit theory
**How it works**:
- Hard-coded electrical formulas
- Circuit topology pattern matching
- Trace following algorithms
- Safety checks

**Example**:
```python
# Calculate LED resistor
electrical_analyzer.calculate_led_resistor(
    supply_voltage=5.0,
    led_voltage=2.0,
    led_current=0.020
)
# Returns: 150Ω resistor, 0.060W power dissipation
```

---

## **Data Flow Diagram**

```
┌─────────────┐
│ User Image  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│  Vision Model (ML)      │ ← Trained YOLOv8m
│  93.8% accuracy         │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│ Component List          │
│ [Arduino, LED, etc]     │
└──────┬──────────────────┘
       │
       ├──────────────────────────┐
       │                          │
       ▼                          ▼
┌─────────────┐        ┌──────────────────┐
│ Pinout DB   │        │ Circuit Analyzer │
│ (26 ICs)    │        │ (Algorithmic)    │
└──────┬──────┘        └────────┬─────────┘
       │                        │
       └────────┬───────────────┘
                │
                ▼
        ┌───────────────┐
        │ Circuit Info  │
        │ + Pin Details │
        └───────┬───────┘
                │
    ┌───────────┴───────────┐
    │                       │
    ▼                       ▼
┌─────────────┐     ┌──────────────┐
│ User Query  │     │ Knowledge    │
│ "Won't work"│     │ Base (28K)   │
└──────┬──────┘     └──────┬───────┘
       │                   │
       └────────┬──────────┘
                │
                ▼
        ┌───────────────┐
        │ Matched       │
        │ Fault         │
        │ Patterns      │
        └───────┬───────┘
                │
                ▼
        ┌───────────────────────────┐
        │ LLM API (Your Key)        │
        │ Context:                  │
        │ - Detected components     │
        │ - Pin info                │
        │ - Circuit analysis        │
        │ - Fault patterns          │
        │ - User measurements       │
        └───────┬───────────────────┘
                │
                ▼
        ┌───────────────┐
        │ Intelligent   │
        │ Response +    │
        │ Visual Overlay│
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │ User sees     │
        │ repair steps  │
        └───────────────┘
```

---

## **What You Need to Add**

### 1. Set Your API Key
```bash
# Option 1: Environment variable
export OPENAI_API_KEY="sk-..."

# Option 2: In code
import os
os.environ["OPENAI_API_KEY"] = "your-key-here"
```

### 2. Modify the Chatbot
File: `src/intelligence/repair_chatbot.py`

Change this:
```python
# Current (mock responses)
def get_response(self, user_message):
    return "Mock response based on keywords"
```

To this:
```python
import openai

def get_response(self, user_message):
    # Build context from our data
    context = self._build_context(
        user_message=user_message,
        detected_components=self.detected_components,
        pinout_info=self.pinout_info,
        fault_patterns=self.matched_patterns,
        measurements=self.measurement_history
    )

    # Call your API
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": context}
        ]
    )

    return response.choices[0].message.content
```

---

## **Quick Test**

```bash
# 1. Test vision model
python scripts/test_complete_system.py

# 2. Test with real image
python -c "
from ultralytics import YOLO
model = YOLO('pcb_runs/electrocom61_full_production/weights/best.pt')
results = model.predict('path/to/your/pcb/image.jpg')
results[0].show()  # Display detections
"

# 3. Test knowledge base search
python -c "
import json
kb = json.load(open('data/knowledge_base/complete_knowledge_base.json'))
print(f'Fault patterns: {kb[\"statistics\"][\"total_fault_patterns\"]:,}')
print(f'Search keywords: {len(kb[\"search_index\"]):,}')
"
```

---

## **Summary**

**What works NOW**:
- ✅ Vision model detects 61 component types at 93.8% accuracy
- ✅ Knowledge base has 28K fault patterns + 35K Q&A
- ✅ 9 intelligence modules for circuit analysis
- ✅ WebSocket API for real-time communication
- ✅ State machine for conversation flow

**What needs YOUR input**:
- ⏳ API key for LLM (OpenAI, Anthropic, etc.)
- ⏳ Integration in `repair_chatbot.py`

**How it all works together**:
1. User uploads image → **Vision model** detects components
2. User describes problem → **Knowledge base** finds relevant patterns
3. System builds context → **Your LLM** provides intelligent responses
4. **Intelligence modules** calculate electrical properties
5. **Visual overlay** shows user exactly where to fix

**The magic**: Our system provides the "eyes" (vision model), "memory" (knowledge base), and "engineering knowledge" (algorithms). Your API provides the "intelligence" (natural language understanding and reasoning).

---

**Next step**: Add your API key and test the full conversational repair flow!
