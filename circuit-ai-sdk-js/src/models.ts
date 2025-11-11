/**
 * Circuit.AI JavaScript SDK Models
 * 
 * Data models for the Circuit.AI API responses and requests.
 */

import { ComponentType, DifficultyLevel } from './types';

export interface ComponentData {
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

export class Component {
  public type: string;
  public name: string;
  public confidence: number;
  public bbox: number[];
  public center: { x: number; y: number };
  public value: number;
  public function: string;
  public specifications?: Record<string, any>;
  public educational_value: string;
  public reuse_value: string;

  constructor(data: ComponentData) {
    this.type = data.type;
    this.name = data.name;
    this.confidence = data.confidence;
    this.bbox = data.bbox;
    this.center = data.center;
    this.value = data.value;
    this.function = data.function;
    this.specifications = data.specifications;
    this.educational_value = data.educational_value;
    this.reuse_value = data.reuse_value;
  }

  static fromJSON(data: any): Component {
    return new Component(data);
  }
}

export interface AnalysisMetadataData {
  analysis_id: string;
  user_id?: string;
  timestamp: string;
  processing_time: number;
  file_name?: string;
  file_size?: number;
  backend_used: string;
  ocr_enabled: boolean;
}

export class AnalysisMetadata {
  public analysis_id: string;
  public user_id?: string;
  public timestamp: string;
  public processing_time: number;
  public file_name?: string;
  public file_size?: number;
  public backend_used: string;
  public ocr_enabled: boolean;

  constructor(data: AnalysisMetadataData) {
    this.analysis_id = data.analysis_id;
    this.user_id = data.user_id;
    this.timestamp = data.timestamp;
    this.processing_time = data.processing_time;
    this.file_name = data.file_name;
    this.file_size = data.file_size;
    this.backend_used = data.backend_used;
    this.ocr_enabled = data.ocr_enabled;
  }

  static fromJSON(data: any): AnalysisMetadata {
    return new AnalysisMetadata(data);
  }
}

export interface AnalysisResultData {
  success: boolean;
  analysis_id: string;
  components: ComponentData[];
  total_value: number;
  analysis_time: number;
  timestamp: string;
  metadata?: AnalysisMetadataData;
  error?: string;
}

export class AnalysisResult {
  public success: boolean;
  public analysis_id: string;
  public components: Component[];
  public total_value: number;
  public analysis_time: number;
  public timestamp: string;
  public metadata?: AnalysisMetadata;
  public error?: string;

  constructor(data: AnalysisResultData) {
    this.success = data.success;
    this.analysis_id = data.analysis_id;
    this.components = data.components.map(comp => Component.fromJSON(comp));
    this.total_value = data.total_value;
    this.analysis_time = data.analysis_time;
    this.timestamp = data.timestamp;
    this.metadata = data.metadata ? AnalysisMetadata.fromJSON(data.metadata) : undefined;
    this.error = data.error;
  }

  static fromJSON(data: any): AnalysisResult {
    return new AnalysisResult(data);
  }
}

export interface ProjectTemplateData {
  id: string;
  name: string;
  description: string;
  difficulty: DifficultyLevel;
  time_estimate: string;
  components_needed: string[];
  components_optional?: string[];
  tools_needed?: string[];
  skills_learned?: string[];
  educational_value: string;
  estimated_cost: number;
  safety_level: string;
  prerequisites?: string[];
  resources?: Record<string, string>;
}

export class ProjectTemplate {
  public id: string;
  public name: string;
  public description: string;
  public difficulty: DifficultyLevel;
  public time_estimate: string;
  public components_needed: string[];
  public components_optional: string[];
  public tools_needed: string[];
  public skills_learned: string[];
  public educational_value: string;
  public estimated_cost: number;
  public safety_level: string;
  public prerequisites: string[];
  public resources: Record<string, string>;

  constructor(data: ProjectTemplateData) {
    this.id = data.id;
    this.name = data.name;
    this.description = data.description;
    this.difficulty = data.difficulty;
    this.time_estimate = data.time_estimate;
    this.components_needed = data.components_needed;
    this.components_optional = data.components_optional || [];
    this.tools_needed = data.tools_needed || [];
    this.skills_learned = data.skills_learned || [];
    this.educational_value = data.educational_value;
    this.estimated_cost = data.estimated_cost;
    this.safety_level = data.safety_level;
    this.prerequisites = data.prerequisites || [];
    this.resources = data.resources || {};
  }

  static fromJSON(data: any): ProjectTemplate {
    return new ProjectTemplate(data);
  }
}

export interface EducationalContentData {
  component_id: string;
  title: string;
  description: string;
  content_type: string;
  difficulty: DifficultyLevel;
  duration?: string;
  topics_covered?: string[];
  resources?: Array<{ title: string; url: string }>;
  prerequisites?: string[];
  learning_objectives?: string[];
}

export class EducationalContent {
  public component_id: string;
  public title: string;
  public description: string;
  public content_type: string;
  public difficulty: DifficultyLevel;
  public duration?: string;
  public topics_covered: string[];
  public resources: Array<{ title: string; url: string }>;
  public prerequisites: string[];
  public learning_objectives: string[];

  constructor(data: EducationalContentData) {
    this.component_id = data.component_id;
    this.title = data.title;
    this.description = data.description;
    this.content_type = data.content_type;
    this.difficulty = data.difficulty;
    this.duration = data.duration;
    this.topics_covered = data.topics_covered || [];
    this.resources = data.resources || [];
    this.prerequisites = data.prerequisites || [];
    this.learning_objectives = data.learning_objectives || [];
  }

  static fromJSON(data: any): EducationalContent {
    return new EducationalContent(data);
  }
}

export interface UsageStatsData {
  user_id: string;
  period: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  total_analysis_time: number;
  average_analysis_time: number;
  components_detected: number;
  images_processed: number;
  quota_used: number;
  quota_remaining: number;
  rate_limit_remaining: number;
}

export class UsageStats {
  public user_id: string;
  public period: string;
  public total_requests: number;
  public successful_requests: number;
  public failed_requests: number;
  public total_analysis_time: number;
  public average_analysis_time: number;
  public components_detected: number;
  public images_processed: number;
  public quota_used: number;
  public quota_remaining: number;
  public rate_limit_remaining: number;

  constructor(data: UsageStatsData) {
    this.user_id = data.user_id;
    this.period = data.period;
    this.total_requests = data.total_requests;
    this.successful_requests = data.successful_requests;
    this.failed_requests = data.failed_requests;
    this.total_analysis_time = data.total_analysis_time;
    this.average_analysis_time = data.average_analysis_time;
    this.components_detected = data.components_detected;
    this.images_processed = data.images_processed;
    this.quota_used = data.quota_used;
    this.quota_remaining = data.quota_remaining;
    this.rate_limit_remaining = data.rate_limit_remaining;
  }

  static fromJSON(data: any): UsageStats {
    return new UsageStats(data);
  }
}
