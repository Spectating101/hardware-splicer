import { CircuitAnalyzer } from '@/types/analysis';

class ApiClient {
  private baseUrl: string;
  private cache: Map<string, any>;
  private eventSource: EventSource | null = null;

  constructor() {
    this.baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    this.cache = new Map();
  }

  // Real-time analysis with WebSocket support
  async analyzePCB(file: File, options: {
    backend?: string;
    enableOcr?: boolean;
    onProgress?: (progress: number, step: string) => void;
    onResult?: (result: any) => void;
  }): Promise<CircuitAnalyzer> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('backend', options.backend || 'classical');
    formData.append('enable_ocr', options.enableOcr?.toString() || 'true');

    try {
      const response = await fetch(`${this.baseUrl}/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Analysis failed: ${response.statusText}`);
      }

      const result = await response.json();
      
      // Cache the result
      const cacheKey = `analysis_${Date.now()}`;
      this.cache.set(cacheKey, result);
      
      return result;
    } catch (error) {
      console.error('API Error:', error);
      throw error;
    }
  }

  // Get analysis history
  async getAnalysisHistory(): Promise<CircuitAnalyzer[]> {
    try {
      const response = await fetch(`${this.baseUrl}/analyses`);
      if (!response.ok) throw new Error('Failed to fetch history');
      return await response.json();
    } catch (error) {
      console.error('Failed to fetch analysis history:', error);
      return [];
    }
  }

  // Get component database
  async getComponentDatabase(): Promise<any[]> {
    try {
      const response = await fetch(`${this.baseUrl}/components`);
      if (!response.ok) throw new Error('Failed to fetch components');
      return await response.json();
    } catch (error) {
      console.error('Failed to fetch component database:', error);
      return [];
    }
  }

  // Get system statistics
  async getStatistics(): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/statistics`);
      if (!response.ok) throw new Error('Failed to fetch statistics');
      return await response.json();
    } catch (error) {
      console.error('Failed to fetch statistics:', error);
      return {};
    }
  }

  // Health check
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      return response.ok;
    } catch (error) {
      return false;
    }
  }

  // Clear cache
  clearCache(): void {
    this.cache.clear();
  }

  // Get cached data
  getCached(key: string): any {
    return this.cache.get(key);
  }
}

export const apiClient = new ApiClient();
