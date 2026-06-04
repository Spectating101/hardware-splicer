export interface Detection {
  class_name: string;
  confidence: number;
  bbox: number[];
  center?: { x: number; y: number };
  area?: number;
}

export interface Component {
  id: string;
  type: string;
  capabilities: string[];
  reuse_value: 'low' | 'medium' | 'high';
  market_value: number;
  educational_value: 'low' | 'medium' | 'high';
  datasheet_url?: string;
  manufacturer?: string;
  part_number?: string;
  description?: string;
  pin_count?: number;
  package_type?: string;
}

export interface FunctionalityData {
  components: Component[];
  capabilities: string[];
  total_market_value: number;
  project_potential: 'poor' | 'fair' | 'good' | 'excellent';
  complexity_score: number;
  educational_score: number;
  reusability_score: number;
}

export interface AnalysisSummary {
  total_components: number;
  total_market_value: number;
  project_potential: 'poor' | 'fair' | 'good' | 'excellent';
  educational_potential: 'low' | 'medium' | 'high';
  capabilities: string[];
  processing_time: number;
  confidence_score: number;
  image_quality: 'low' | 'medium' | 'high';
}

export interface AnalysisMetadata {
  backend: string;
  ocr: boolean;
  detection_quality: 'low' | 'medium' | 'high';
  project_potential: 'poor' | 'fair' | 'good' | 'excellent';
  timestamp: string;
  version: string;
}

export interface CircuitAnalyzer {
  success: boolean;
  analysis_id: number;
  results: {
    detections: Detection[];
    functionality_data: FunctionalityData;
  };
  summary: AnalysisSummary;
  analysis_metadata: AnalysisMetadata;
  recommendations?: ProjectRecommendation[];
  educational_content?: EducationalContent[];
}

export interface ProjectRecommendation {
  id: string;
  name: string;
  description: string;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  components_needed: string[];
  estimated_cost: number;
  time_required: string;
  skills_developed: string[];
  tutorial_url?: string;
  score: number;
}

export interface EducationalContent {
  component_type: string;
  title: string;
  content: string;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  video_url?: string;
  interactive_demo?: string;
  quiz_questions?: QuizQuestion[];
}

export interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
  correct_answer: number;
  explanation: string;
}

export interface AnalysisProgress {
  step: string;
  progress: number;
  message: string;
  timestamp: string;
}

export interface UserPreferences {
  default_backend: string;
  enable_ocr: boolean;
  auto_save: boolean;
  notifications: boolean;
  theme: 'light' | 'dark' | 'auto';
  language: string;
}

export interface AnalysisHistory {
  id: number;
  filename: string;
  timestamp: string;
  summary: AnalysisSummary;
  thumbnail_url?: string;
  favorite: boolean;
  tags: string[];
}
