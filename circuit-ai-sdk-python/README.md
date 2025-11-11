# Circuit.AI Python SDK

Official Python SDK for the Circuit.AI PCB Analysis API platform.

## Installation

```bash
pip install circuit-ai
```

## Quick Start

```python
import circuitai

# Initialize the client
client = circuitai.Client(api_key="your-api-key")

# Analyze a PCB image
result = client.analyze_pcb("path/to/pcb_image.jpg")

print(f"Found {len(result.components)} components")
for component in result.components:
    print(f"- {component.name}: ${component.value}")
```

## Features

- **PCB Analysis**: Upload and analyze PCB images for component detection
- **Component Information**: Get detailed information about electronic components
- **Project Templates**: Access educational project recommendations
- **Educational Content**: Retrieve learning materials and tutorials
- **Batch Processing**: Analyze multiple images in a single request
- **Usage Statistics**: Monitor your API usage and quotas

## API Reference

### Client

#### `Client(api_key, base_url=None, timeout=30, max_retries=3)`

Initialize the Circuit.AI client.

**Parameters:**
- `api_key` (str): Your Circuit.AI API key
- `base_url` (str, optional): Base URL for the API (default: production)
- `timeout` (int, optional): Request timeout in seconds (default: 30)
- `max_retries` (int, optional): Maximum number of retries (default: 3)

### Analysis Methods

#### `analyze_pcb(image, backend=None, enable_ocr=False)`

Analyze a PCB image for component detection and value assessment.

**Parameters:**
- `image` (str|Path|BinaryIO): Path to image file, file-like object, or base64 string
- `backend` (str, optional): Detection backend ("yolo" or "enhanced")
- `enable_ocr` (bool, optional): Enable OCR text extraction (default: False)

**Returns:** `AnalysisResult` object

#### `analyze_pcb_batch(images, backend=None, enable_ocr=False)`

Analyze multiple PCB images in a single request.

**Parameters:**
- `images` (List): List of image paths, file-like objects, or base64 strings
- `backend` (str, optional): Detection backend ("yolo" or "enhanced")
- `enable_ocr` (bool, optional): Enable OCR text extraction (default: False)

**Returns:** List of `AnalysisResult` objects

### Information Methods

#### `get_components(search=None, category=None, limit=50, offset=0)`

Get information about supported electronic components.

**Parameters:**
- `search` (str, optional): Search term for component names
- `category` (str, optional): Filter by component category
- `limit` (int, optional): Maximum number of components to return (default: 50)
- `offset` (int, optional): Number of components to skip (default: 0)

**Returns:** List of `Component` objects

#### `get_projects(difficulty=None, components=None, limit=20, offset=0)`

Get educational project templates and recommendations.

**Parameters:**
- `difficulty` (str, optional): Filter by difficulty level ("beginner", "intermediate", "advanced")
- `components` (List[str], optional): Filter by required components
- `limit` (int, optional): Maximum number of projects to return (default: 20)
- `offset` (int, optional): Number of projects to skip (default: 0)

**Returns:** List of `ProjectTemplate` objects

#### `get_educational_content(component_id)`

Get educational content and tutorials for a specific component.

**Parameters:**
- `component_id` (str): Component identifier

**Returns:** `EducationalContent` object

### History and Usage

#### `get_analysis_history(limit=20, offset=0, date_from=None, date_to=None)`

Get user's analysis history.

**Parameters:**
- `limit` (int, optional): Maximum number of analyses to return (default: 20)
- `offset` (int, optional): Number of analyses to skip (default: 0)
- `date_from` (str, optional): Start date filter (ISO format)
- `date_to` (str, optional): End date filter (ISO format)

**Returns:** List of `AnalysisResult` objects

#### `get_analysis(analysis_id)`

Get a specific analysis by ID.

**Parameters:**
- `analysis_id` (str): Analysis identifier

**Returns:** `AnalysisResult` object

#### `get_usage_stats()`

Get API usage statistics for the current user.

**Returns:** `UsageStats` object

## Data Models

### AnalysisResult

```python
class AnalysisResult:
    success: bool
    analysis_id: str
    components: List[Component]
    total_value: float
    analysis_time: float
    timestamp: str
    metadata: Optional[AnalysisMetadata]
    error: Optional[str]
```

### Component

```python
class Component:
    type: str
    name: str
    confidence: float
    bbox: List[float]
    center: Dict[str, float]
    value: float
    function: str
    specifications: Optional[Dict[str, Any]]
    educational_value: str
    reuse_value: str
```

### ProjectTemplate

```python
class ProjectTemplate:
    id: str
    name: str
    description: str
    difficulty: DifficultyLevel
    time_estimate: str
    components_needed: List[str]
    components_optional: List[str]
    tools_needed: List[str]
    skills_learned: List[str]
    educational_value: str
    estimated_cost: float
    safety_level: str
    prerequisites: List[str]
    resources: Dict[str, str]
```

## Error Handling

The SDK provides specific exception types for different error scenarios:

```python
from circuitai import CircuitAIError, AuthenticationError, RateLimitError, APIError

try:
    result = client.analyze_pcb("image.jpg")
except AuthenticationError:
    print("Invalid API key")
except RateLimitError:
    print("Rate limit exceeded")
except APIError as e:
    print(f"API error: {e.message}")
except CircuitAIError:
    print("General SDK error")
```

## Examples

### Basic Analysis

```python
import circuitai

client = circuitai.Client(api_key="your-api-key")

# Analyze a single image
result = client.analyze_pcb("pcb_image.jpg")

print(f"Analysis ID: {result.analysis_id}")
print(f"Total Value: ${result.total_value:.2f}")
print(f"Components Found: {len(result.components)}")

for component in result.components:
    print(f"- {component.name}: ${component.value:.2f} (confidence: {component.confidence:.2f})")
```

### Batch Analysis

```python
# Analyze multiple images
images = ["pcb1.jpg", "pcb2.jpg", "pcb3.jpg"]
results = client.analyze_pcb_batch(images)

for i, result in enumerate(results):
    print(f"Image {i+1}: {len(result.components)} components, ${result.total_value:.2f}")
```

### Component Information

```python
# Get component information
components = client.get_components(search="arduino", limit=10)

for component in components:
    print(f"{component.name}: {component.description}")
    print(f"  Capabilities: {', '.join(component.capabilities)}")
    print(f"  Market Value: ${component.market_value_range['min']:.2f} - ${component.market_value_range['max']:.2f}")
```

### Project Recommendations

```python
# Get project recommendations
projects = client.get_projects(difficulty="beginner", components=["arduino", "led"])

for project in projects:
    print(f"{project.name}: {project.description}")
    print(f"  Difficulty: {project.difficulty}")
    print(f"  Time: {project.time_estimate}")
    print(f"  Cost: ${project.estimated_cost:.2f}")
```

### Educational Content

```python
# Get educational content for a component
content = client.get_educational_content("arduino-uno")

print(f"Title: {content.title}")
print(f"Description: {content.description}")
print(f"Duration: {content.duration}")
print(f"Topics: {', '.join(content.topics_covered)}")

for resource in content.resources:
    print(f"- {resource['title']}: {resource['url']}")
```

## Rate Limits

The API has different rate limits based on your plan:

- **Free**: 10 requests/minute, 100/hour
- **Pro**: 60 requests/minute, 1000/hour
- **Enterprise**: 300 requests/minute, 5000/hour

The SDK automatically handles rate limiting and will raise `RateLimitError` when limits are exceeded.

## Support

For support and questions:

- Documentation: https://docs.circuit-ai.com
- Email: support@circuit-ai.com
- GitHub: https://github.com/circuit-ai/circuit-ai-python-sdk

## License

This SDK is licensed under the MIT License. See the LICENSE file for details.
