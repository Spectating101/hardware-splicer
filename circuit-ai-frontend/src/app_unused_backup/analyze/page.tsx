"use client";

import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { 
  Upload, 
  Image as ImageIcon, 
  Brain, 
  Target, 
  Download,
  Eye,
  Settings,
  Zap,
  CheckCircle,
  AlertCircle,
  Loader2
} from "lucide-react";
import { useDropzone } from "react-dropzone";

interface AnalysisResult {
  success: boolean;
  analysis_id: number;
  results: {
    detections: Array<{
      class_name: string;
      confidence: number;
      bbox: number[];
    }>;
    functionality_data: {
      components: Array<{
        type: string;
        capabilities: string[];
        reuse_value: string;
        market_value: number;
        educational_value: string;
      }>;
      capabilities: string[];
      total_market_value: number;
      project_potential: string;
    };
  };
  summary: {
    total_components: number;
    total_market_value: number;
    project_potential: string;
    educational_potential: string;
    capabilities: string[];
  };
}

export default function AnalyzePage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [backend, setBackend] = useState("classical");
  const [enableOcr, setEnableOcr] = useState(true);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (file) {
      setFile(file);
      setError(null);
      setResult(null);
      
      // Create preview
      const reader = new FileReader();
      reader.onload = () => {
        setPreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.gif', '.bmp']
    },
    multiple: false
  });

  const analyzeImage = async () => {
    if (!file) return;

    setIsAnalyzing(true);
    setProgress(0);
    setError(null);

    // Simulate progress
    const progressInterval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 90) {
          clearInterval(progressInterval);
          return 90;
        }
        return prev + 10;
      });
    }, 200);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('backend', backend);
      formData.append('enable_ocr', enableOcr.toString());

      // For demo purposes, we'll simulate the API call
      // In production, this would be: const response = await fetch('http://localhost:8000/analyze', { method: 'POST', body: formData });
      
      await new Promise(resolve => setTimeout(resolve, 2000)); // Simulate API delay
      
      // Demo result
      const demoResult: AnalysisResult = {
        success: true,
        analysis_id: Math.floor(Math.random() * 1000) + 1,
        results: {
          detections: [
            { class_name: "ic_chip", confidence: 0.93, bbox: [248, 148, 303, 203] },
            { class_name: "capacitor", confidence: 0.75, bbox: [348, 148, 383, 183] },
            { class_name: "capacitor", confidence: 0.73, bbox: [148, 148, 183, 203] },
            { class_name: "connector", confidence: 0.85, bbox: [98, 148, 133, 203] },
          ],
          functionality_data: {
            components: [
              {
                type: "ic_chip",
                capabilities: ["arduino_projects", "iot_devices", "educational_electronics"],
                reuse_value: "high",
                market_value: 0.50,
                educational_value: "high"
              },
              {
                type: "capacitor",
                capabilities: ["power_filtering", "audio_circuits", "voltage_regulation"],
                reuse_value: "medium",
                market_value: 0.25,
                educational_value: "medium"
              }
            ],
            capabilities: ["arduino_projects", "iot_devices", "power_filtering", "audio_circuits"],
            total_market_value: 2.92,
            project_potential: "good"
          }
        },
        summary: {
          total_components: 4,
          total_market_value: 2.92,
          project_potential: "good",
          educational_potential: "high",
          capabilities: ["arduino_projects", "iot_devices", "power_filtering", "audio_circuits"]
        }
      };

      setResult(demoResult);
      setProgress(100);
    } catch (err) {
      setError("Analysis failed. Please try again.");
    } finally {
      setIsAnalyzing(false);
      clearInterval(progressInterval);
    }
  };

  const resetAnalysis = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    setProgress(0);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">PCB Analysis</h1>
        <p className="text-xl text-gray-600">
          Upload a PCB image and get instant AI-powered component analysis
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        {/* Upload Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="w-5 h-5" />
              Upload PCB Image
            </CardTitle>
            <CardDescription>
              Drag and drop or click to upload a PCB image for analysis
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Drop Zone */}
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                isDragActive
                  ? "border-indigo-500 bg-indigo-50"
                  : "border-gray-300 hover:border-indigo-400"
              }`}
            >
              <input {...getInputProps()} />
              {preview ? (
                <div className="space-y-4">
                  <img
                    src={preview}
                    alt="Preview"
                    className="max-w-full h-64 object-contain mx-auto rounded-lg"
                  />
                  <p className="text-sm text-gray-600">{file?.name}</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <ImageIcon className="w-12 h-12 mx-auto text-gray-400" />
                  <div>
                    <p className="text-lg font-medium">
                      {isDragActive ? "Drop the image here" : "Drag & drop an image"}
                    </p>
                    <p className="text-sm text-gray-500">or click to browse</p>
                  </div>
                </div>
              )}
            </div>

            {/* Analysis Options */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">Analysis Backend</label>
                <select
                  value={backend}
                  onChange={(e) => setBackend(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded-md"
                >
                  <option value="classical">Classical CV</option>
                  <option value="yolo">YOLO</option>
                  <option value="remote">Remote API</option>
                </select>
              </div>
              
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="ocr"
                  checked={enableOcr}
                  onChange={(e) => setEnableOcr(e.target.checked)}
                  className="rounded"
                />
                <label htmlFor="ocr" className="text-sm">Enable OCR for text detection</label>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-4">
              <Button
                onClick={analyzeImage}
                disabled={!file || isAnalyzing}
                className="flex-1"
                variant="gradient"
              >
                {isAnalyzing ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Brain className="w-4 h-4 mr-2" />
                    Analyze PCB
                  </>
                )}
              </Button>
              
              {file && (
                <Button
                  onClick={resetAnalysis}
                  variant="outline"
                  disabled={isAnalyzing}
                >
                  Reset
                </Button>
              )}
            </div>

            {/* Progress */}
            {isAnalyzing && (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Analyzing components...</span>
                  <span>{progress}%</span>
                </div>
                <Progress value={progress} />
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-md">
                <AlertCircle className="w-4 h-4 text-red-600" />
                <span className="text-red-600">{error}</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Results Section */}
        <div className="space-y-6">
          {result ? (
            <>
              {/* Summary Card */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    Analysis Complete
                  </CardTitle>
                  <CardDescription>
                    Analysis ID: #{result.analysis_id}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-center p-4 bg-blue-50 rounded-lg">
                      <div className="text-2xl font-bold text-blue-600">
                        {result.summary.total_components}
                      </div>
                      <div className="text-sm text-gray-600">Components</div>
                    </div>
                    <div className="text-center p-4 bg-green-50 rounded-lg">
                      <div className="text-2xl font-bold text-green-600">
                        ${result.summary.total_market_value}
                      </div>
                      <div className="text-sm text-gray-600">Market Value</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Component Breakdown */}
              <Card>
                <CardHeader>
                  <CardTitle>Component Breakdown</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {result.results.functionality_data.components.map((component, index) => (
                      <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div>
                          <div className="font-medium capitalize">{component.type.replace('_', ' ')}</div>
                          <div className="text-sm text-gray-600">
                            Reuse: {component.reuse_value} | Education: {component.educational_value}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-bold">${component.market_value}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Capabilities */}
              <Card>
                <CardHeader>
                  <CardTitle>Identified Capabilities</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {result.summary.capabilities.map((capability, index) => (
                      <span
                        key={index}
                        className="px-3 py-1 bg-indigo-100 text-indigo-800 rounded-full text-sm"
                      >
                        {capability.replace('_', ' ')}
                      </span>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Project Potential */}
              <Card>
                <CardHeader>
                  <CardTitle>Project Potential</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2">
                    <Target className="w-5 h-5 text-green-600" />
                    <span className="capitalize font-medium">{result.summary.project_potential}</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-2">
                    This PCB has {result.summary.project_potential} potential for educational projects.
                  </p>
                </CardContent>
              </Card>

              {/* Export Options */}
              <Card>
                <CardHeader>
                  <CardTitle>Export Results</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-4">
                    <Button variant="outline" className="flex-1">
                      <Download className="w-4 h-4 mr-2" />
                      Export CSV
                    </Button>
                    <Button variant="outline" className="flex-1">
                      <Download className="w-4 h-4 mr-2" />
                      Export PDF
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Analysis Results</CardTitle>
                <CardDescription>
                  Upload an image to see detailed analysis results
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-12 text-gray-500">
                  <Brain className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>No analysis results yet</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
