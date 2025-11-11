import { CircuitAnalyzer, AnalysisProgress, Detection, Component, FunctionalityData, AnalysisSummary, AnalysisMetadata, ProjectRecommendation, EducationalContent, QuizQuestion, AnalysisProgress as Progress, UserPreferences, AnalysisHistory } from '@/types/analysis';

class EnhancedApiClient {
  private baseUrl: string;
  private wsUrl: string;
  private cache: Map<string, any>;
  private wsConnections: Map<string, WebSocket>;
  private eventListeners: Map<string, Set<(data: any) => void>>;

  constructor() {
    this.baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    this.wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
    this.cache = new Map();
    this.wsConnections = new Map();
    this.eventListeners = new Map();
  }

  // Real-time analysis with WebSocket support
  async analyzePCB(file: File, options: {
    backend?: string;
    enableOcr?: boolean;
    enableQualityAssessment?: boolean;
    enableCaching?: boolean;
    onProgress?: (progress: Progress) => void;
    onResult?: (result: CircuitAnalyzer) => void;
    onError?: (error: Error) => void;
  }): Promise<CircuitAnalyzer> {
    const clientId = this.generateClientId();
    const analysisId = this.generateAnalysisId();

    // Setup WebSocket connection for real-time updates
    await this.setupWebSocketConnection(clientId, analysisId, options);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('backend', options.backend || 'ensemble');
    formData.append('enable_ocr', options.enableOcr?.toString() || 'true');
    formData.append('enable_quality_assessment', options.enableQualityAssessment?.toString() || 'true');
    formData.append('enable_caching', options.enableCaching?.toString() || 'true');

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
      const cacheKey = `analysis_${analysisId}`;
      this.cache.set(cacheKey, result);
      
      // Cleanup WebSocket connection
      this.cleanupWebSocketConnection(clientId);
      
      return result;
    } catch (error) {
      this.cleanupWebSocketConnection(clientId);
      console.error('API Error:', error);
      throw error;
    }
  }

  // Batch analysis
  async submitBatchAnalysis(imagePaths: string[], options: {
    backend?: string;
    enableOcr?: boolean;
    enableQualityAssessment?: boolean;
    enableCaching?: boolean;
  }): Promise<{ jobId: string; status: string; imageCount: number }> {
    try {
      const response = await fetch(`${this.baseUrl}/batch_analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          image_paths: imagePaths,
          analysis_options: options
        }),
      });

      if (!response.ok) {
        throw new Error(`Batch analysis submission failed: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Batch Analysis Error:', error);
      throw error;
    }
  }

  // Get batch job status
  async getBatchJobStatus(jobId: string): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/job/${jobId}`);
      if (!response.ok) {
        throw new Error(`Failed to get job status: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Job Status Error:', error);
      throw error;
    }
  }

  // WebSocket connection management
  private async setupWebSocketConnection(clientId: string, analysisId: string, options: {
    onProgress?: (progress: Progress) => void;
    onResult?: (result: CircuitAnalyzer) => void;
    onError?: (error: Error) => void;
  }): Promise<void> {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(`${this.wsUrl}/ws/${clientId}`);
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        this.wsConnections.set(clientId, ws);
        
        // Subscribe to analysis updates
        ws.send(JSON.stringify({
          type: 'subscribe_analysis',
          analysis_id: analysisId
        }));
        
        resolve();
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          switch (message.type) {
            case 'analysis_progress':
              if (options.onProgress) {
                options.onProgress(message.data);
              }
              break;
              
            case 'analysis_complete':
              if (options.onResult) {
                options.onResult(message.data.result);
              }
              break;
              
            case 'subscription_confirmed':
              console.log('Subscribed to analysis updates');
              break;
              
            case 'pong':
              // Handle ping/pong for connection health
              break;
              
            default:
              console.log('Unknown WebSocket message:', message);
          }
        } catch (error) {
          console.error('WebSocket message error:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.wsConnections.delete(clientId);
      };
    });
  }

  private cleanupWebSocketConnection(clientId: string): void {
    const ws = this.wsConnections.get(clientId);
    if (ws) {
      ws.close();
      this.wsConnections.delete(clientId);
    }
  }

  // System health check
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      return response.ok;
    } catch (error) {
      return false;
    }
  }

  // Get comprehensive system statistics
  async getSystemStatistics(): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/statistics`);
      if (!response.ok) throw new Error('Failed to fetch statistics');
      return await response.json();
    } catch (error) {
      console.error('Failed to fetch system statistics:', error);
      return {};
    }
  }

  // Get cache statistics
  async getCacheStats(): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/cache/stats`);
      if (!response.ok) throw new Error('Failed to fetch cache stats');
      return await response.json();
    } catch (error) {
      console.error('Failed to fetch cache statistics:', error);
      return {};
    }
  }

  // Get queue statistics
  async getQueueStats(): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/queue/stats`);
      if (!response.ok) throw new Error('Failed to fetch queue stats');
      return await response.json();
    } catch (error) {
      console.error('Failed to fetch queue statistics:', error);
      return {};
    }
  }

  // Get WebSocket statistics
  async getWebSocketStats(): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/ws/stats`);
      if (!response.ok) throw new Error('Failed to fetch WebSocket stats');
      return await response.json();
    } catch (error) {
      console.error('Failed to fetch WebSocket statistics:', error);
      return {};
    }
  }

  // Clear cache
  async clearCache(pattern?: string): Promise<{ deleted_entries: number }> {
    try {
      const url = pattern ? `${this.baseUrl}/cache/clear?pattern=${pattern}` : `${this.baseUrl}/cache/clear`;
      const response = await fetch(url, { method: 'POST' });
      if (!response.ok) throw new Error('Failed to clear cache');
      return await response.json();
    } catch (error) {
      console.error('Failed to clear cache:', error);
      throw error;
    }
  }

  // Get component database
  async getComponentDatabase(): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/components`);
      if (!response.ok) throw new Error('Failed to fetch component database');
      return await response.json();
    } catch (error) {
      console.error('Failed to fetch component database:', error);
      return {};
    }
  }

  // Get project templates
  async getProjectTemplates(): Promise<ProjectRecommendation[]> {
    try {
      const response = await fetch(`${this.baseUrl}/projects`);
      if (!response.ok) throw new Error('Failed to fetch project templates');
      const data = await response.json();
      return data.projects || [];
    } catch (error) {
      console.error('Failed to fetch project templates:', error);
      return [];
    }
  }

  // Get educational content
  async getEducationalContent(): Promise<EducationalContent[]> {
    try {
      const response = await fetch(`${this.baseUrl}/educational`);
      if (!response.ok) throw new Error('Failed to fetch educational content');
      const data = await response.json();
      return data.content || [];
    } catch (error) {
      console.error('Failed to fetch educational content:', error);
      return [];
    }
  }

  // Get repair guides
  async getRepairGuides(): Promise<any[]> {
    try {
      const response = await fetch(`${this.baseUrl}/repair`);
      if (!response.ok) throw new Error('Failed to fetch repair guides');
      const data = await response.json();
      return data.guides || [];
    } catch (error) {
      console.error('Failed to fetch repair guides:', error);
      return [];
    }
  }

  // Enhanced analysis history with caching
  async getAnalysisHistory(): Promise<AnalysisHistory[]> {
    const cacheKey = 'analysis_history';
    const cached = this.cache.get(cacheKey);
    
    if (cached && Date.now() - cached.timestamp < 5 * 60 * 1000) { // 5 minutes cache
      return cached.data;
    }

    try {
      // This would be implemented when we have a proper database
      // For now, return mock data
      const mockHistory: AnalysisHistory[] = [
        {
          id: 1,
          filename: "arduino_uno_pcb.jpg",
          timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
          summary: {
            total_components: 12,
            total_market_value: 8.50,
            project_potential: "good",
            educational_potential: "high",
            capabilities: ["arduino_projects", "iot_devices", "power_filtering"],
            processing_time: 8.3,
            confidence_score: 0.85,
            image_quality: "high"
          },
          thumbnail_url: "/api/thumbnails/1",
          favorite: true,
          tags: ["arduino", "beginner", "educational"]
        },
        {
          id: 2,
          filename: "raspberry_pi_board.jpg",
          timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(), // 5 hours ago
          summary: {
            total_components: 18,
            total_market_value: 15.20,
            project_potential: "excellent",
            educational_potential: "high",
            capabilities: ["iot_devices", "data_processing", "sensor_control"],
            processing_time: 12.1,
            confidence_score: 0.92,
            image_quality: "high"
          },
          thumbnail_url: "/api/thumbnails/2",
          favorite: false,
          tags: ["raspberry_pi", "intermediate", "iot"]
        }
      ];

      this.cache.set(cacheKey, {
        data: mockHistory,
        timestamp: Date.now()
      });

      return mockHistory;
    } catch (error) {
      console.error('Failed to fetch analysis history:', error);
      return [];
    }
  }

  // User preferences management
  async getUserPreferences(): Promise<UserPreferences> {
    const cacheKey = 'user_preferences';
    const cached = this.cache.get(cacheKey);
    
    if (cached) {
      return cached;
    }

    // Default preferences
    const defaultPreferences: UserPreferences = {
      default_backend: "ensemble",
      enable_ocr: true,
      auto_save: true,
      notifications: true,
      theme: "auto",
      language: "en"
    };

    this.cache.set(cacheKey, defaultPreferences);
    return defaultPreferences;
  }

  async updateUserPreferences(preferences: Partial<UserPreferences>): Promise<UserPreferences> {
    const current = await this.getUserPreferences();
    const updated = { ...current, ...preferences };
    
    this.cache.set('user_preferences', updated);
    return updated;
  }

  // Utility methods
  private generateClientId(): string {
    return `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private generateAnalysisId(): string {
    return `analysis_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  // Clear all cache
  clearCache(): void {
    this.cache.clear();
  }

  // Get cached data
  getCached(key: string): any {
    return this.cache.get(key);
  }

  // Event listener management
  addEventListener(event: string, listener: (data: any) => void): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, new Set());
    }
    this.eventListeners.get(event)!.add(listener);
  }

  removeEventListener(event: string, listener: (data: any) => void): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      listeners.delete(listener);
    }
  }

  private emitEvent(event: string, data: any): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      listeners.forEach(listener => listener(data));
    }
  }
}

export const enhancedApiClient = new EnhancedApiClient();
