"use client";

import { useState, useCallback, useRef, useEffect } from 'react';
import { CircuitAnalyzer, AnalysisProgress, Detection } from '@/types/analysis';
import { enhancedApiClient } from '@/lib/enhanced-api';

interface UseEnhancedAnalysisOptions {
  onProgress?: (progress: AnalysisProgress) => void;
  onComplete?: (result: CircuitAnalyzer) => void;
  onError?: (error: Error) => void;
  onWebSocketConnect?: () => void;
  onWebSocketDisconnect?: () => void;
}

export function useEnhancedAnalysis(options: UseEnhancedAnalysisOptions = {}) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progress, setProgress] = useState<AnalysisProgress | null>(null);
  const [result, setResult] = useState<CircuitAnalyzer | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [webSocketConnected, setWebSocketConnected] = useState(false);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Enhanced analysis steps with real-time progress
  const analysisSteps = [
    { step: 'uploading', message: 'Processing uploaded image...', duration: 1000 },
    { step: 'detecting', message: 'Detecting components using enhanced algorithms...', duration: 2000 },
    { step: 'analyzing', message: 'Analyzing component capabilities and functionality...', duration: 1800 },
    { step: 'recommending', message: 'Generating personalized project recommendations...', duration: 1500 },
    { step: 'educating', message: 'Creating educational content and learning materials...', duration: 1200 },
    { step: 'finalizing', message: 'Finalizing analysis results...', duration: 800 }
  ];

  const analyzeImage = useCallback(async (file: File, params: {
    backend?: string;
    enableOcr?: boolean;
    enableQualityAssessment?: boolean;
    enableCaching?: boolean;
  } = {}) => {
    setIsAnalyzing(true);
    setError(null);
    setResult(null);
    setIsPaused(false);
    setProgress(null);

    // Create abort controller for cancellation
    abortControllerRef.current = new AbortController();

    try {
      // Generate analysis ID
      const currentAnalysisId = `analysis_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      setAnalysisId(currentAnalysisId);

      // Start real-time analysis with WebSocket support
      const analysisResult = await enhancedApiClient.analyzePCB(file, {
        backend: params.backend || 'ensemble',
        enableOcr: params.enableOcr ?? true,
        enableQualityAssessment: params.enableQualityAssessment ?? true,
        enableCaching: params.enableCaching ?? true,
        onProgress: (progressData: AnalysisProgress) => {
          setProgress(progressData);
          options.onProgress?.(progressData);
        },
        onResult: (analysisResult: CircuitAnalyzer) => {
          setResult(analysisResult);
          setProgress({
            step: 'complete',
            progress: 100,
            message: 'Analysis complete!',
            timestamp: new Date().toISOString()
          });
          options.onComplete?.(analysisResult);
        },
        onError: (analysisError: Error) => {
          setError(analysisError);
          options.onError?.(analysisError);
        }
      });

      // Set WebSocket connection status
      setWebSocketConnected(true);
      options.onWebSocketConnect?.();

      return analysisResult;

    } catch (err) {
      const analysisError = err instanceof Error ? err : new Error('Analysis failed');
      setError(analysisError);
      options.onError?.(analysisError);
      throw analysisError;
    } finally {
      setIsAnalyzing(false);
      abortControllerRef.current = null;
      setWebSocketConnected(false);
      options.onWebSocketDisconnect?.();
    }
  }, [options]);

  // Batch analysis functionality
  const [batchJobId, setBatchJobId] = useState<string | null>(null);
  const [batchStatus, setBatchStatus] = useState<any>(null);

  const submitBatchAnalysis = useCallback(async (files: File[], options: {
    backend?: string;
    enableOcr?: boolean;
    enableQualityAssessment?: boolean;
    enableCaching?: boolean;
  } = {}) => {
    try {
      // Convert files to paths (in a real implementation, you'd upload files first)
      const imagePaths = files.map((_, index) => `/uploads/image_${index}.jpg`);
      
      const batchResult = await enhancedApiClient.submitBatchAnalysis(imagePaths, {
        backend: options.backend || 'ensemble',
        enableOcr: options.enableOcr ?? true,
        enableQualityAssessment: options.enableQualityAssessment ?? true,
        enableCaching: options.enableCaching ?? true
      });

      setBatchJobId(batchResult.jobId);
      setBatchStatus(batchResult);

      return batchResult;
    } catch (error) {
      console.error('Batch analysis submission failed:', error);
      throw error;
    }
  }, []);

  const getBatchJobStatus = useCallback(async (jobId: string) => {
    try {
      const status = await enhancedApiClient.getBatchJobStatus(jobId);
      setBatchStatus(status);
      return status;
    } catch (error) {
      console.error('Failed to get batch job status:', error);
      throw error;
    }
  }, []);

  // System monitoring
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [systemStats, setSystemStats] = useState<any>(null);

  const checkSystemHealth = useCallback(async () => {
    try {
      const health = await enhancedApiClient.healthCheck();
      setSystemHealth(health);
      return health;
    } catch (error) {
      console.error('System health check failed:', error);
      throw error;
    }
  }, []);

  const getSystemStatistics = useCallback(async () => {
    try {
      const stats = await enhancedApiClient.getSystemStatistics();
      setSystemStats(stats);
      return stats;
    } catch (error) {
      console.error('Failed to get system statistics:', error);
      throw error;
    }
  }, []);

  // Cache management
  const [cacheStats, setCacheStats] = useState<any>(null);

  const getCacheStatistics = useCallback(async () => {
    try {
      const stats = await enhancedApiClient.getCacheStats();
      setCacheStats(stats);
      return stats;
    } catch (error) {
      console.error('Failed to get cache statistics:', error);
      throw error;
    }
  }, []);

  const clearCache = useCallback(async (pattern?: string) => {
    try {
      const result = await enhancedApiClient.clearCache(pattern);
      // Refresh cache stats after clearing
      await getCacheStatistics();
      return result;
    } catch (error) {
      console.error('Failed to clear cache:', error);
      throw error;
    }
  }, [getCacheStatistics]);

  // Queue monitoring
  const [queueStats, setQueueStats] = useState<any>(null);

  const getQueueStatistics = useCallback(async () => {
    try {
      const stats = await enhancedApiClient.getQueueStats();
      setQueueStats(stats);
      return stats;
    } catch (error) {
      console.error('Failed to get queue statistics:', error);
      throw error;
    }
  }, []);

  // WebSocket monitoring
  const [webSocketStats, setWebSocketStats] = useState<any>(null);

  const getWebSocketStatistics = useCallback(async () => {
    try {
      const stats = await enhancedApiClient.getWebSocketStats();
      setWebSocketStats(stats);
      return stats;
    } catch (error) {
      console.error('Failed to get WebSocket statistics:', error);
      throw error;
    }
  }, []);

  // Analysis control functions
  const pauseAnalysis = useCallback(() => {
    setIsPaused(true);
  }, []);

  const resumeAnalysis = useCallback(() => {
    setIsPaused(false);
  }, []);

  const cancelAnalysis = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setIsAnalyzing(false);
    setProgress(null);
    setError(null);
    setWebSocketConnected(false);
  }, []);

  const resetAnalysis = useCallback(() => {
    cancelAnalysis();
    setResult(null);
    setError(null);
    setProgress(null);
    setIsPaused(false);
    setAnalysisId(null);
    setBatchJobId(null);
    setBatchStatus(null);
  }, [cancelAnalysis]);

  // Auto-refresh system stats
  useEffect(() => {
    const refreshStats = async () => {
      try {
        await Promise.all([
          getSystemStatistics(),
          getCacheStatistics(),
          getQueueStatistics(),
          getWebSocketStatistics()
        ]);
      } catch (error) {
        console.error('Failed to refresh system stats:', error);
      }
    };

    // Initial load
    refreshStats();

    // Refresh every 30 seconds
    const interval = setInterval(refreshStats, 30000);

    return () => clearInterval(interval);
  }, [getSystemStatistics, getCacheStatistics, getQueueStatistics, getWebSocketStatistics]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return {
    // Analysis state
    isAnalyzing,
    progress,
    result,
    error,
    isPaused,
    webSocketConnected,
    analysisId,

    // Analysis functions
    analyzeImage,
    pauseAnalysis,
    resumeAnalysis,
    cancelAnalysis,
    resetAnalysis,

    // Batch analysis
    batchJobId,
    batchStatus,
    submitBatchAnalysis,
    getBatchJobStatus,

    // System monitoring
    systemHealth,
    systemStats,
    checkSystemHealth,
    getSystemStatistics,

    // Cache management
    cacheStats,
    getCacheStatistics,
    clearCache,

    // Queue monitoring
    queueStats,
    getQueueStatistics,

    // WebSocket monitoring
    webSocketStats,
    getWebSocketStatistics,

    // Utility
    enhancedApiClient
  };
}
