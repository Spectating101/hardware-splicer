# Circuit.AI JavaScript SDK

Official JavaScript SDK for the Circuit.AI PCB Analysis API platform.

## Installation

```bash
npm install circuit-ai-sdk
```

## Quick Start

```javascript
import CircuitAI from 'circuit-ai-sdk';

// Initialize the client
const client = new CircuitAI({
  apiKey: 'your-api-key'
});

// Analyze a PCB image
const result = await client.analyzePCB('path/to/pcb_image.jpg');

console.log(`Found ${result.components.length} components`);
result.components.forEach(component => {
  console.log(`- ${component.name}: $${component.value}`);
});
```

## Features

- **PCB Analysis**: Upload and analyze PCB images for component detection
- **Component Information**: Get detailed information about electronic components
- **Project Templates**: Access educational project recommendations
- **Educational Content**: Retrieve learning materials and tutorials
- **Batch Processing**: Analyze multiple images in a single request
- **Usage Statistics**: Monitor your API usage and quotas
- **TypeScript Support**: Full TypeScript definitions included

## API Reference

### CircuitAI

#### `new CircuitAI(config)`

Initialize the Circuit.AI client.

**Parameters:**
- `config.apiKey` (string): Your Circuit.AI API key
- `config.baseURL` (string, optional): Base URL for the API (default: production)
- `config.timeout` (number, optional): Request timeout in seconds (default: 30)
- `config.maxRetries` (number, optional): Maximum number of retries (default: 3)

### Analysis Methods

#### `analyzePCB(image, options?)`

Analyze a PCB image for component detection and value assessment.

**Parameters:**
- `image` (File|Blob|string): File, Blob, or base64 string
- `options.backend` (string, optional): Detection backend ("yolo" or "enhanced")
- `options.enableOCR` (boolean, optional): Enable OCR text extraction (default: false)

**Returns:** `Promise<AnalysisResult>`

#### `analyzePCBBatch(images, options?)`

Analyze multiple PCB images in a single request.

**Parameters:**
- `images` (Array): Array of File, Blob, or base64 strings
- `options.backend` (string, optional): Detection backend ("yolo" or "enhanced")
- `options.enableOCR` (boolean, optional): Enable OCR text extraction (default: false)

**Returns:** `Promise<AnalysisResult[]>`

### Information Methods

#### `getComponents(options?)`

Get information about supported electronic components.

**Parameters:**
- `options.search` (string, optional): Search term for component names
- `options.category` (string, optional): Filter by component category
- `options.limit` (number, optional): Maximum number of components to return (default: 50)
- `options.offset` (number, optional): Number of components to skip (default: 0)

**Returns:** `Promise<Component[]>`

#### `getProjects(options?)`

Get educational project templates and recommendations.

**Parameters:**
- `options.difficulty` (string, optional): Filter by difficulty level ("beginner", "intermediate", "advanced")
- `options.components` (string[], optional): Filter by required components
- `options.limit` (number, optional): Maximum number of projects to return (default: 20)
- `options.offset` (number, optional): Number of projects to skip (default: 0)

**Returns:** `Promise<ProjectTemplate[]>`

#### `getEducationalContent(componentId)`

Get educational content and tutorials for a specific component.

**Parameters:**
- `componentId` (string): Component identifier

**Returns:** `Promise<EducationalContent>`

### History and Usage

#### `getAnalysisHistory(options?)`

Get user's analysis history.

**Parameters:**
- `options.limit` (number, optional): Maximum number of analyses to return (default: 20)
- `options.offset` (number, optional): Number of analyses to skip (default: 0)
- `options.dateFrom` (string, optional): Start date filter (ISO format)
- `options.dateTo` (string, optional): End date filter (ISO format)

**Returns:** `Promise<AnalysisResult[]>`

#### `getAnalysis(analysisId)`

Get a specific analysis by ID.

**Parameters:**
- `analysisId` (string): Analysis identifier

**Returns:** `Promise<AnalysisResult>`

#### `getUsageStats()`

Get API usage statistics for the current user.

**Returns:** `Promise<UsageStats>`

## Data Models

### AnalysisResult

```typescript
interface AnalysisResult {
  success: boolean;
  analysis_id: string;
  components: Component[];
  total_value: number;
  analysis_time: number;
  timestamp: string;
  metadata?: AnalysisMetadata;
  error?: string;
}
```

### Component

```typescript
interface Component {
  type: string;
  name: string;
  confidence: number;
  bbox: number[];
  center: { x: number; y: number };
  value: number;
  function: string;
  specifications?: Record<string, any>;
  educational_value: string;
  reuse_value: string;
}
```

### ProjectTemplate

```typescript
interface ProjectTemplate {
  id: string;
  name: string;
  description: string;
  difficulty: DifficultyLevel;
  time_estimate: string;
  components_needed: string[];
  components_optional: string[];
  tools_needed: string[];
  skills_learned: string[];
  educational_value: string;
  estimated_cost: number;
  safety_level: string;
  prerequisites: string[];
  resources: Record<string, string>;
}
```

## Error Handling

The SDK provides specific error types for different error scenarios:

```javascript
import { CircuitAIError, AuthenticationError, RateLimitError, APIError } from 'circuit-ai-sdk';

try {
  const result = await client.analyzePCB('image.jpg');
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.log('Invalid API key');
  } else if (error instanceof RateLimitError) {
    console.log('Rate limit exceeded');
  } else if (error instanceof APIError) {
    console.log(`API error: ${error.message}`);
  } else if (error instanceof CircuitAIError) {
    console.log('General SDK error');
  }
}
```

## Examples

### Basic Analysis

```javascript
import CircuitAI from 'circuit-ai-sdk';

const client = new CircuitAI({ apiKey: 'your-api-key' });

// Analyze a single image
const result = await client.analyzePCB('pcb_image.jpg');

console.log(`Analysis ID: ${result.analysis_id}`);
console.log(`Total Value: $${result.total_value.toFixed(2)}`);
console.log(`Components Found: ${result.components.length}`);

result.components.forEach(component => {
  console.log(`- ${component.name}: $${component.value.toFixed(2)} (confidence: ${component.confidence.toFixed(2)})`);
});
```

### Batch Analysis

```javascript
// Analyze multiple images
const images = ['pcb1.jpg', 'pcb2.jpg', 'pcb3.jpg'];
const results = await client.analyzePCBBatch(images);

results.forEach((result, index) => {
  console.log(`Image ${index + 1}: ${result.components.length} components, $${result.total_value.toFixed(2)}`);
});
```

### Component Information

```javascript
// Get component information
const components = await client.getComponents({ search: 'arduino', limit: 10 });

components.forEach(component => {
  console.log(`${component.name}: ${component.description}`);
  console.log(`  Capabilities: ${component.capabilities.join(', ')}`);
  console.log(`  Market Value: $${component.market_value_range.min.toFixed(2)} - $${component.market_value_range.max.toFixed(2)}`);
});
```

### Project Recommendations

```javascript
// Get project recommendations
const projects = await client.getProjects({ 
  difficulty: 'beginner', 
  components: ['arduino', 'led'] 
});

projects.forEach(project => {
  console.log(`${project.name}: ${project.description}`);
  console.log(`  Difficulty: ${project.difficulty}`);
  console.log(`  Time: ${project.time_estimate}`);
  console.log(`  Cost: $${project.estimated_cost.toFixed(2)}`);
});
```

### Educational Content

```javascript
// Get educational content for a component
const content = await client.getEducationalContent('arduino-uno');

console.log(`Title: ${content.title}`);
console.log(`Description: ${content.description}`);
console.log(`Duration: ${content.duration}`);
console.log(`Topics: ${content.topics_covered.join(', ')}`);

content.resources.forEach(resource => {
  console.log(`- ${resource.title}: ${resource.url}`);
});
```

### File Upload

```javascript
// Upload from file input
const fileInput = document.getElementById('fileInput');
const file = fileInput.files[0];

if (file) {
  const result = await client.analyzePCB(file);
  console.log('Analysis complete:', result);
}
```

### Base64 Image

```javascript
// Analyze base64 encoded image
const base64Image = 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ...';
const result = await client.analyzePCB(base64Image);
console.log('Analysis complete:', result);
```

## Rate Limits

The API has different rate limits based on your plan:

- **Free**: 10 requests/minute, 100/hour
- **Pro**: 60 requests/minute, 1000/hour
- **Enterprise**: 300 requests/minute, 5000/hour

The SDK automatically handles rate limiting and will throw `RateLimitError` when limits are exceeded.

## TypeScript Support

The SDK includes full TypeScript definitions:

```typescript
import CircuitAI, { AnalysisResult, Component, ProjectTemplate } from 'circuit-ai-sdk';

const client = new CircuitAI({ apiKey: 'your-api-key' });

const result: AnalysisResult = await client.analyzePCB('image.jpg');
const components: Component[] = result.components;
```

## Browser Support

The SDK works in all modern browsers that support:
- ES2018+ features
- Fetch API or Axios
- File API
- Blob API

## Node.js Support

The SDK also works in Node.js environments:

```javascript
import CircuitAI from 'circuit-ai-sdk';
import fs from 'fs';

const client = new CircuitAI({ apiKey: 'your-api-key' });

// Read file and analyze
const imageBuffer = fs.readFileSync('pcb_image.jpg');
const result = await client.analyzePCB(imageBuffer);
```

## Support

For support and questions:

- Documentation: https://docs.circuit-ai.com
- Email: support@circuit-ai.com
- GitHub: https://github.com/circuit-ai/circuit-ai-js-sdk

## License

This SDK is licensed under the MIT License. See the LICENSE file for details.
