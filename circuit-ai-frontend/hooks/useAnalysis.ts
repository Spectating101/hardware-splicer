import { useState, useCallback, useRef, useEffect } from 'react';
import { CircuitAnalyzer, AnalysisProgress, Detection } from '@/types/analysis';
import { apiClient } from '@/lib/api';

interface UseAnalysisOptions {
  onProgress?: (progress: AnalysisProgress) => void;
  onComplete?: (result: CircuitAnalyzer) => void;
  onError?: (error: Error) => void;
}

export function useAnalysis(options: UseAnalysisOptions = {}) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progress, setProgress] = useState<AnalysisProgress | null>(null);
  const [result, setResult] = useState<CircuitAnalyzer | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isPaused, setIsPaused] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const analysisSteps = [
    { step: 'uploading', message: 'Uploading image...', duration: 1000 },
    { step: 'preprocessing', message: 'Preprocessing image...', duration: 1500 },
    { step: 'detecting', message: 'Detecting components...', duration: 2000 },
    { step: 'analyzing', message: 'Analyzing capabilities...', duration: 1800 },
    { step: 'mapping', message: 'Mapping functionality...', duration: 1200 },
    { step: 'recommending', message: 'Generating recommendations...', duration: 1000 },
    { step: 'finalizing', message: 'Finalizing results...', duration: 800 }
  ];

  const analyzeImage = useCallback(async (file: File, backend: string = 'classical', enableOcr: boolean = true) => {
    setIsAnalyzing(true);
    setError(null);
    setResult(null);
    setIsPaused(false);

    // Create abort controller for cancellation
    abortControllerRef.current = new AbortController();

    try {
      // Simulate real-time progress updates
      for (let i = 0; i < analysisSteps.length; i++) {
        if (abortControllerRef.current.signal.aborted || isPaused) {
          break;
        }

        const step = analysisSteps[i];
        const progressData: AnalysisProgress = {
          step: step.step,
          progress: (i / (analysisSteps.length - 1)) * 90,
          message: step.message,
          timestamp: new Date().toISOString()
        };

        setProgress(progressData);
        options.onProgress?.(progressData);

        // Wait for step duration
        await new Promise(resolve => setTimeout(resolve, step.duration));
      }

      if (!abortControllerRef.current.signal.aborted && !isPaused) {
        // Generate sophisticated demo result
        const demoResult: CircuitAnalyzer = {
          success: true,
          analysis_id: Math.floor(Math.random() * 10000) + 1,
          results: {
            detections: [
              { 
                class_name: "ic_chip", 
                confidence: 0.93, 
                bbox: [248, 148, 303, 203],
                center: { x: 275.5, y: 175.5 },
                area: 2695
              },
              { 
                class_name: "capacitor", 
                confidence: 0.75, 
                bbox: [348, 148, 383, 183],
                center: { x: 365.5, y: 165.5 },
                area: 1225
              },
              { 
                class_name: "capacitor", 
                confidence: 0.73, 
                bbox: [148, 148, 183, 203],
                center: { x: 165.5, y: 175.5 },
                area: 1225
              },
              { 
                class_name: "connector", 
                confidence: 0.85, 
                bbox: [98, 148, 133, 203],
                center: { x: 115.5, y: 175.5 },
                area: 1225
              },
              { 
                class_name: "resistor", 
                confidence: 0.68, 
                bbox: [48, 148, 83, 203],
                center: { x: 65.5, y: 175.5 },
                area: 1225
              }
            ],
            functionality_data: {
              components: [
                {
                  id: "ic_chip_1",
                  type: "ic_chip",
                  capabilities: ["arduino_projects", "iot_devices", "educational_electronics", "signal_processing"],
                  reuse_value: "high",
                  market_value: 0.50,
                  educational_value: "high",
                  datasheet_url: "https://example.com/datasheet/ic_chip_1",
                  manufacturer: "Texas Instruments",
                  part_number: "LM358",
                  description: "Dual operational amplifier",
                  pin_count: 8,
                  package_type: "DIP-8"
                },
                {
                  id: "capacitor_1",
                  type: "capacitor",
                  capabilities: ["power_filtering", "audio_circuits", "voltage_regulation", "timing_circuits"],
                  reuse_value: "medium",
                  market_value: 0.25,
                  educational_value: "medium",
                  datasheet_url: "https://example.com/datasheet/capacitor_1",
                  manufacturer: "Murata",
                  part_number: "GRM188R71C104K",
                  description: "100nF ceramic capacitor",
                  package_type: "0603"
                },
                {
                  id: "connector_1",
                  type: "connector",
                  capabilities: ["signal_transmission", "data_communication", "modular_design"],
                  reuse_value: "high",
                  market_value: 0.10,
                  educational_value: "medium",
                  datasheet_url: "https://example.com/datasheet/connector_1",
                  manufacturer: "Molex",
                  part_number: "22-01-2027",
                  description: "2-pin header connector",
                  pin_count: 2,
                  package_type: "THT"
                }
              ],
              capabilities: ["arduino_projects", "iot_devices", "power_filtering", "audio_circuits", "signal_transmission"],
              total_market_value: 2.92,
              project_potential: "good",
              complexity_score: 0.7,
              educational_score: 0.8,
              reusability_score: 0.75
            }
          },
          summary: {
            total_components: 5,
            total_market_value: 2.92,
            project_potential: "good",
            educational_potential: "high",
            capabilities: ["arduino_projects", "iot_devices", "power_filtering", "audio_circuits", "signal_transmission"],
            processing_time: 8.3,
            confidence_score: 0.79,
            image_quality: "high"
          },
          analysis_metadata: {
            backend: backend,
            ocr: enableOcr,
            detection_quality: "high",
            project_potential: "good",
            timestamp: new Date().toISOString(),
            version: "2.1.0"
          },
          recommendations: [
            {
              id: "proj_1",
              name: "Arduino Audio Amplifier",
              description: "Build a simple audio amplifier using the detected IC chip and capacitors",
              difficulty: "beginner",
              components_needed: ["ic_chip", "capacitor"],
              estimated_cost: 5.50,
              time_required: "2-3 hours",
              skills_developed: ["soldering", "circuit_design", "audio_electronics"],
              tutorial_url: "https://example.com/tutorials/audio-amplifier",
              score: 0.85
            },
            {
              id: "proj_2",
              name: "IoT Sensor Hub",
              description: "Create an IoT sensor hub using the microcontroller and connectors",
              difficulty: "intermediate",
              components_needed: ["ic_chip", "connector"],
              estimated_cost: 12.00,
              time_required: "4-6 hours",
              skills_developed: ["programming", "iot", "sensor_integration"],
              tutorial_url: "https://example.com/tutorials/iot-hub",
              score: 0.78
            }
          ],
          educational_content: [
            {
              component_type: "ic_chip",
              title: "Understanding Operational Amplifiers",
              content: "Learn about op-amps and their applications in electronic circuits",
              difficulty: "intermediate",
              video_url: "https://example.com/videos/op-amps",
              interactive_demo: "https://example.com/demos/op-amp-simulator",
              quiz_questions: [
                {
                  id: "q1",
                  question: "What is the primary function of an operational amplifier?",
                  options: ["Voltage amplification", "Current amplification", "Power amplification", "Frequency amplification"],
                  correct_answer: 0,
                  explanation: "Operational amplifiers are primarily used for voltage amplification in electronic circuits."
                }
              ]
            }
          ]
        };

        setResult(demoResult);
        setProgress({
          step: 'complete',
          progress: 100,
          message: 'Analysis complete!',
          timestamp: new Date().toISOString()
        });

        options.onComplete?.(demoResult);
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Analysis failed');
      setError(error);
      options.onError?.(error);
    } finally {
      setIsAnalyzing(false);
      abortControllerRef.current = null;
    }
  }, [analysisSteps, isPaused, options]);

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
  }, []);

  const resetAnalysis = useCallback(() => {
    cancelAnalysis();
    setResult(null);
    setError(null);
    setProgress(null);
    setIsPaused(false);
  }, [cancelAnalysis]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return {
    isAnalyzing,
    progress,
    result,
    error,
    isPaused,
    analyzeImage,
    pauseAnalysis,
    resumeAnalysis,
    cancelAnalysis,
    resetAnalysis
  };
}
