/**
 * Circuit.AI JavaScript SDK
 * 
 * Official JavaScript SDK for the Circuit.AI PCB Analysis API platform.
 */

export { CircuitAI } from './client';
export { 
  Component,
  AnalysisResult,
  ProjectTemplate,
  EducationalContent,
  UsageStats,
  AnalysisMetadata
} from './models';
export {
  CircuitAIError,
  AuthenticationError,
  RateLimitError,
  APIError
} from './errors';
export { 
  ComponentType,
  DifficultyLevel,
  BackendType
} from './types';

// Version information
export const VERSION = '1.0.0';
