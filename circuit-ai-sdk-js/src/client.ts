/**
 * Circuit.AI JavaScript SDK Client
 * 
 * Main client class for interacting with the Circuit.AI API.
 */

import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { 
  Component, 
  AnalysisResult, 
  ProjectTemplate, 
  EducationalContent, 
  UsageStats 
} from './models';
import { 
  CircuitAIError, 
  AuthenticationError, 
  RateLimitError, 
  APIError 
} from './errors';
import { BackendType } from './types';

export interface CircuitAIConfig {
  apiKey: string;
  baseURL?: string;
  timeout?: number;
  maxRetries?: number;
}

export class CircuitAI {
  private client: AxiosInstance;
  private config: CircuitAIConfig;

  /**
   * Initialize the Circuit.AI client.
   * 
   * @param config - Configuration object
   * @param config.apiKey - Your Circuit.AI API key
   * @param config.baseURL - Base URL for the API (default: production)
   * @param config.timeout - Request timeout in seconds (default: 30)
   * @param config.maxRetries - Maximum number of retries (default: 3)
   */
  constructor(config: CircuitAIConfig) {
    this.config = {
      baseURL: 'https://api.circuit-ai.com',
      timeout: 30,
      maxRetries: 3,
      ...config
    };

    this.client = axios.create({
      baseURL: this.config.baseURL,
      timeout: this.config.timeout! * 1000,
      headers: {
        'Authorization': `Bearer ${this.config.apiKey}`,
        'User-Agent': 'circuit-ai-js-sdk/1.0.0',
        'Content-Type': 'application/json'
      }
    });

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response) {
          const { status, data } = error.response;
          
          if (status === 401) {
            throw new AuthenticationError('Invalid API key');
          } else if (status === 429) {
            const retryAfter = error.response.headers['retry-after'] || '60';
            throw new RateLimitError(`Rate limit exceeded. Retry after ${retryAfter} seconds`);
          } else if (status >= 400) {
            const message = data?.error?.message || `HTTP ${status} error`;
            throw new APIError(message, status, data?.error?.code);
          }
        }
        
        throw new CircuitAIError(`Request failed: ${error.message}`);
      }
    );
  }

  /**
   * Analyze a PCB image for component detection and value assessment.
   * 
   * @param image - File, Blob, or base64 string
   * @param options - Analysis options
   * @returns Promise<AnalysisResult>
   */
  async analyzePCB(
    image: File | Blob | string,
    options: {
      backend?: BackendType;
      enableOCR?: boolean;
    } = {}
  ): Promise<AnalysisResult> {
    try {
      const formData = new FormData();
      
      if (typeof image === 'string') {
        // Base64 string
        const base64Data = image.replace(/^data:image\/[a-z]+;base64,/, '');
        const byteCharacters = atob(base64Data);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'image/jpeg' });
        formData.append('file', blob, 'image.jpg');
      } else {
        // File or Blob
        formData.append('file', image, 'image.jpg');
      }

      if (options.backend) {
        formData.append('backend', options.backend);
      }
      if (options.enableOCR) {
        formData.append('enable_ocr', 'true');
      }

      const response = await this.client.post('/v1/analyze', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      return AnalysisResult.fromJSON(response.data);
    } catch (error) {
      if (error instanceof (CircuitAIError || AuthenticationError || RateLimitError || APIError)) {
        throw error;
      }
      throw new CircuitAIError(`Failed to analyze PCB: ${error}`);
    }
  }

  /**
   * Analyze multiple PCB images in a single request.
   * 
   * @param images - Array of File, Blob, or base64 strings
   * @param options - Analysis options
   * @returns Promise<AnalysisResult[]>
   */
  async analyzePCBBatch(
    images: (File | Blob | string)[],
    options: {
      backend?: BackendType;
      enableOCR?: boolean;
    } = {}
  ): Promise<AnalysisResult[]> {
    try {
      const batchItems = await Promise.all(
        images.map(async (image, index) => {
          let base64Data: string;
          
          if (typeof image === 'string') {
            base64Data = image.replace(/^data:image\/[a-z]+;base64,/, '');
          } else {
            // Convert File/Blob to base64
            const arrayBuffer = await image.arrayBuffer();
            const uint8Array = new Uint8Array(arrayBuffer);
            const binaryString = Array.from(uint8Array, byte => String.fromCharCode(byte)).join('');
            base64Data = btoa(binaryString);
          }

          return {
            filename: `image_${index}.jpg`,
            content_base64: base64Data,
            backend: options.backend,
            enable_ocr: options.enableOCR
          };
        })
      );

      const response = await this.client.post('/v1/analyze/batch', {
        images: batchItems
      });

      return response.data.results.map((item: any) => AnalysisResult.fromJSON(item));
    } catch (error) {
      if (error instanceof (CircuitAIError || AuthenticationError || RateLimitError || APIError)) {
        throw error;
      }
      throw new CircuitAIError(`Failed to analyze PCB batch: ${error}`);
    }
  }

  /**
   * Get information about supported electronic components.
   * 
   * @param options - Query options
   * @returns Promise<Component[]>
   */
  async getComponents(options: {
    search?: string;
    category?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<Component[]> {
    const params = new URLSearchParams();
    
    if (options.search) params.append('search', options.search);
    if (options.category) params.append('category', options.category);
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.offset) params.append('offset', options.offset.toString());

    const response = await this.client.get(`/v1/components?${params}`);
    
    return response.data.data.components.map((comp: any) => Component.fromJSON(comp));
  }

  /**
   * Get educational project templates and recommendations.
   * 
   * @param options - Query options
   * @returns Promise<ProjectTemplate[]>
   */
  async getProjects(options: {
    difficulty?: string;
    components?: string[];
    limit?: number;
    offset?: number;
  } = {}): Promise<ProjectTemplate[]> {
    const params = new URLSearchParams();
    
    if (options.difficulty) params.append('difficulty', options.difficulty);
    if (options.components) params.append('components', options.components.join(','));
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.offset) params.append('offset', options.offset.toString());

    const response = await this.client.get(`/v1/projects?${params}`);
    
    return response.data.data.projects.map((proj: any) => ProjectTemplate.fromJSON(proj));
  }

  /**
   * Get educational content and tutorials for a specific component.
   * 
   * @param componentId - Component identifier
   * @returns Promise<EducationalContent>
   */
  async getEducationalContent(componentId: string): Promise<EducationalContent> {
    const response = await this.client.get(`/v1/educational/${componentId}`);
    return EducationalContent.fromJSON(response.data.data);
  }

  /**
   * Get user's analysis history.
   * 
   * @param options - Query options
   * @returns Promise<AnalysisResult[]>
   */
  async getAnalysisHistory(options: {
    limit?: number;
    offset?: number;
    dateFrom?: string;
    dateTo?: string;
  } = {}): Promise<AnalysisResult[]> {
    const params = new URLSearchParams();
    
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.offset) params.append('offset', options.offset.toString());
    if (options.dateFrom) params.append('date_from', options.dateFrom);
    if (options.dateTo) params.append('date_to', options.dateTo);

    const response = await this.client.get(`/v1/analyses?${params}`);
    
    return response.data.data.analyses.map((analysis: any) => AnalysisResult.fromJSON(analysis));
  }

  /**
   * Get a specific analysis by ID.
   * 
   * @param analysisId - Analysis identifier
   * @returns Promise<AnalysisResult>
   */
  async getAnalysis(analysisId: string): Promise<AnalysisResult> {
    const response = await this.client.get(`/v1/analyses/${analysisId}`);
    return AnalysisResult.fromJSON(response.data.data);
  }

  /**
   * Export analysis results as CSV.
   * 
   * @param analysisId - Analysis identifier
   * @returns Promise<string>
   */
  async exportAnalysisCSV(analysisId: string): Promise<string> {
    const response = await this.client.get(`/v1/analyses/${analysisId}/export.csv`, {
      responseType: 'text'
    });
    return response.data;
  }

  /**
   * Get API usage statistics for the current user.
   * 
   * @returns Promise<UsageStats>
   */
  async getUsageStats(): Promise<UsageStats> {
    const response = await this.client.get('/v1/usage');
    return UsageStats.fromJSON(response.data.data);
  }

  /**
   * Check API health status.
   * 
   * @returns Promise<any>
   */
  async healthCheck(): Promise<any> {
    const response = await this.client.get('/v1/health');
    return response.data;
  }
}
