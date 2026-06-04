# Circuit.AI Frontend Guide

## 🎨 Frontend Architecture Overview

Circuit.AI's frontend is built with modern web technologies to provide a responsive, interactive, and user-friendly experience for PCB analysis.

### Technology Stack

```
Frontend Stack
├── Next.js 14 (React Framework)
├── TypeScript (Type Safety)
├── Tailwind CSS (Styling)
├── Shadcn/ui (Component Library)
├── Framer Motion (Animations)
├── Lucide React (Icons)
└── React Hooks (State Management)
```

---

## 🏗️ Project Structure

```
circuit-ai-frontend/
├── app/                          # Next.js App Router
│   ├── [locale]/                 # Internationalization
│   │   ├── page.tsx             # Landing page
│   │   ├── analyze/             # Analysis page
│   │   ├── dashboard/           # User dashboard
│   │   └── layout.tsx           # Root layout
│   ├── globals.css              # Global styles
│   └── layout.tsx               # App layout
├── components/                   # Reusable components
│   ├── ui/                      # Shadcn/ui components
│   ├── analysis/                # Analysis-specific components
│   ├── dashboard/               # Dashboard components
│   └── common/                  # Common components
├── lib/                         # Utility libraries
│   ├── enhanced-api.ts          # API client
│   ├── utils.ts                 # Utility functions
│   └── constants.ts             # Constants
├── hooks/                       # Custom React hooks
│   ├── useEnhancedAnalysis.ts   # Analysis hook
│   └── useWebSocket.ts          # WebSocket hook
├── types/                       # TypeScript definitions
│   └── analysis.ts              # Analysis types
└── public/                      # Static assets
```

---

## 🎯 Key Components

### 1. Landing Page (`app/[locale]/page.tsx`)

**Purpose**: Main entry point showcasing Circuit.AI capabilities

**Features**:
- Hero section with value proposition
- Feature showcase with auto-rotation
- Statistics display
- Call-to-action buttons
- Responsive design

**Key Elements**:
```tsx
// Hero Section
<div className="hero-section">
  <h1>Transform E-Waste into Educational Opportunities</h1>
  <p>Advanced AI-powered PCB analysis</p>
  <Button href="/analyze">Start Analysis</Button>
</div>

// Feature Showcase
<div className="feature-showcase">
  {features.map((feature, index) => (
    <FeatureCard key={index} {...feature} />
  ))}
</div>
```

### 2. Analysis Page (`app/[locale]/analyze/page.tsx`)

**Purpose**: Main analysis interface for PCB processing

**Features**:
- File upload with drag-and-drop
- Real-time progress tracking
- Results visualization
- Educational content display
- Project recommendations

**Key Elements**:
```tsx
// File Upload
<FileUpload 
  onFileSelect={handleFileSelect}
  acceptedTypes={['image/*']}
  maxSize={10 * 1024 * 1024} // 10MB
/>

// Progress Tracking
<ProgressTracker 
  progress={analysisProgress}
  status={analysisStatus}
  estimatedTime={estimatedTime}
/>

// Results Display
<AnalysisResults 
  components={detectedComponents}
  totalValue={totalValue}
  educationalValue={educationalValue}
/>
```

### 3. Dashboard (`app/[locale]/dashboard/page.tsx`)

**Purpose**: User dashboard with analysis history and statistics

**Features**:
- Analysis history
- Performance metrics
- System statistics
- User preferences
- Export functionality

---

## 🔧 Core Components

### 1. File Upload Component

**Location**: `components/analysis/FileUpload.tsx`

**Features**:
- Drag-and-drop support
- File validation
- Progress indication
- Error handling

```tsx
interface FileUploadProps {
  onFileSelect: (file: File) => void;
  acceptedTypes?: string[];
  maxSize?: number;
  multiple?: boolean;
}

export function FileUpload({
  onFileSelect,
  acceptedTypes = ['image/*'],
  maxSize = 10 * 1024 * 1024,
  multiple = false
}: FileUploadProps) {
  // Implementation
}
```

### 2. Progress Tracker

**Location**: `components/analysis/ProgressTracker.tsx`

**Features**:
- Real-time progress updates
- Step-by-step indication
- Time estimation
- WebSocket integration

```tsx
interface ProgressTrackerProps {
  progress: number;
  currentStep: string;
  estimatedTime: number;
  isComplete: boolean;
}

export function ProgressTracker({
  progress,
  currentStep,
  estimatedTime,
  isComplete
}: ProgressTrackerProps) {
  // Implementation
}
```

### 3. Analysis Results

**Location**: `components/analysis/AnalysisResults.tsx`

**Features**:
- Component visualization
- Value assessment
- Educational insights
- Interactive elements

```tsx
interface AnalysisResultsProps {
  components: Component[];
  totalValue: number;
  educationalValue: string;
  difficultyLevel: string;
  processingTime: number;
}

export function AnalysisResults({
  components,
  totalValue,
  educationalValue,
  difficultyLevel,
  processingTime
}: AnalysisResultsProps) {
  // Implementation
}
```

---

## 🎨 Styling System

### Tailwind CSS Configuration

**File**: `tailwind.config.ts`

```typescript
import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        // ... more colors
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
}

export default config
```

### Custom CSS Classes

**File**: `app/globals.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer components {
  .gradient-text {
    @apply bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 bg-clip-text text-transparent;
  }
  
  .glass-effect {
    @apply bg-white/10 backdrop-blur-sm border border-white/20;
  }
  
  .card-hover {
    @apply hover:shadow-xl hover:scale-105 transition-all duration-300;
  }
  
  .button-glow {
    @apply hover:shadow-lg hover:shadow-blue-500/25 transition-shadow duration-300;
  }
}
```

---

## 🔌 API Integration

### Enhanced API Client

**File**: `lib/enhanced-api.ts`

**Features**:
- WebSocket integration
- Real-time progress updates
- Error handling
- Caching support

```typescript
class EnhancedApiClient {
  private baseUrl: string;
  private wsUrl: string;
  private cache: Map<string, any>;
  private wsConnections: Map<string, WebSocket>;

  async analyzePCB(file: File, options: AnalysisOptions): Promise<AnalysisResult> {
    // Implementation with WebSocket support
  }

  async submitBatchAnalysis(files: File[]): Promise<BatchJob> {
    // Implementation
  }

  async getSystemStatistics(): Promise<SystemStats> {
    // Implementation
  }
}
```

### Custom Hooks

**File**: `hooks/useEnhancedAnalysis.ts`

**Features**:
- State management
- WebSocket handling
- Error handling
- Loading states

```typescript
export function useEnhancedAnalysis(options: UseAnalysisOptions = {}) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const analyzeImage = useCallback(async (file: File, options: AnalysisOptions) => {
    // Implementation
  }, []);

  return {
    isAnalyzing,
    progress,
    result,
    error,
    analyzeImage,
    // ... other methods
  };
}
```

---

## 🎭 Animations & Interactions

### Framer Motion Integration

**File**: `components/common/AnimatedCard.tsx`

```tsx
import { motion } from 'framer-motion';

export function AnimatedCard({ children, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      whileHover={{ scale: 1.02 }}
      className="card-hover"
    >
      {children}
    </motion.div>
  );
}
```

### Loading States

**File**: `components/common/LoadingSpinner.tsx`

```tsx
export function LoadingSpinner({ size = 'md', text = 'Loading...' }) {
  return (
    <div className="flex items-center justify-center space-x-2">
      <div className={`animate-spin rounded-full border-2 border-gray-300 border-t-blue-600 ${sizeClasses[size]}`} />
      <span className="text-gray-600">{text}</span>
    </div>
  );
}
```

---

## 📱 Responsive Design

### Breakpoint Strategy

```css
/* Mobile First Approach */
.container {
  @apply px-4; /* Mobile */
}

@media (min-width: 768px) {
  .container {
    @apply px-6; /* Tablet */
  }
}

@media (min-width: 1024px) {
  .container {
    @apply px-8; /* Desktop */
  }
}
```

### Component Responsiveness

```tsx
// Responsive Grid
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  {items.map(item => (
    <Card key={item.id}>{item.content}</Card>
  ))}
</div>

// Responsive Text
<h1 className="text-3xl md:text-4xl lg:text-6xl font-bold">
  Circuit.AI
</h1>
```

---

## ♿ Accessibility

### WCAG Compliance

**Features**:
- Semantic HTML structure
- ARIA labels and roles
- Keyboard navigation
- Screen reader support
- Color contrast compliance

```tsx
// Accessible Button
<button
  aria-label="Start PCB analysis"
  aria-describedby="analysis-description"
  className="btn-primary"
  onClick={handleAnalysis}
>
  Start Analysis
</button>
<div id="analysis-description" className="sr-only">
  Upload a PCB image to begin analysis
</div>
```

### Focus Management

```tsx
// Focus trap for modals
import { useFocusTrap } from '@/hooks/useFocusTrap';

export function Modal({ isOpen, onClose, children }) {
  const focusTrapRef = useFocusTrap(isOpen);
  
  return (
    <div ref={focusTrapRef} role="dialog" aria-modal="true">
      {children}
    </div>
  );
}
```

---

## 🧪 Testing Strategy

### Component Testing

**File**: `__tests__/components/FileUpload.test.tsx`

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { FileUpload } from '@/components/analysis/FileUpload';

describe('FileUpload', () => {
  it('should accept valid image files', () => {
    const mockOnFileSelect = jest.fn();
    render(<FileUpload onFileSelect={mockOnFileSelect} />);
    
    const file = new File(['test'], 'test.png', { type: 'image/png' });
    const input = screen.getByLabelText(/upload/i);
    
    fireEvent.change(input, { target: { files: [file] } });
    
    expect(mockOnFileSelect).toHaveBeenCalledWith(file);
  });
});
```

### Integration Testing

**File**: `__tests__/integration/analysis-flow.test.tsx`

```typescript
describe('Analysis Flow', () => {
  it('should complete full analysis workflow', async () => {
    // Test complete user journey
  });
});
```

---

## 🚀 Performance Optimization

### Code Splitting

```tsx
// Lazy load components
const AnalysisResults = lazy(() => import('@/components/analysis/AnalysisResults'));

// Suspense boundary
<Suspense fallback={<LoadingSpinner />}>
  <AnalysisResults results={results} />
</Suspense>
```

### Image Optimization

```tsx
import Image from 'next/image';

<Image
  src="/pcb-image.jpg"
  alt="PCB Analysis"
  width={800}
  height={600}
  placeholder="blur"
  blurDataURL="data:image/jpeg;base64,..."
/>
```

### Bundle Analysis

```bash
# Analyze bundle size
npm run build
npm run analyze
```

---

## 🔧 Development Workflow

### Development Commands

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Run tests
npm test

# Run linting
npm run lint

# Format code
npm run format
```

### Environment Configuration

**File**: `.env.local`

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_APP_NAME=Circuit.AI
```

---

## 📚 Related Documentation

- **[Architecture](ARCHITECTURE.md)** - System architecture overview
- **[API Reference](API_REFERENCE.md)** - Backend API documentation
- **[Testing](TESTING.md)** - Testing strategies and implementation
- **[Performance](PERFORMANCE.md)** - Performance optimization guide

