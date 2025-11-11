'use client';

import React, { useState, useRef } from 'react';
import { 
  Upload, 
  Zap, 
  Eye, 
  Download, 
  Share2, 
  Settings, 
  Play,
  Pause,
  RotateCcw,
  CheckCircle,
  AlertCircle,
  Info,
  Brain,
  Target,
  Clock,
  TrendingUp
} from 'lucide-react';

export default function AnalyzePage() {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [analysisResults, setAnalysisResults] = useState<any>(null);
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        setUploadedImage(e.target?.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const simulateAnalysis = () => {
    setIsAnalyzing(true);
    setProgress(0);
    
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setIsAnalyzing(false);
          setAnalysisResults({
            components: [
              { type: 'IC Chip', confidence: 0.95, value: '$2.50', description: 'Microcontroller unit' },
              { type: 'Capacitor', confidence: 0.88, value: '$0.15', description: 'Electrolytic capacitor' },
              { type: 'Resistor', confidence: 0.92, value: '$0.05', description: 'Carbon film resistor' },
              { type: 'LED', confidence: 0.85, value: '$0.25', description: 'Light emitting diode' }
            ],
            totalValue: '$2.95',
            processingTime: '2.3s',
            confidence: 0.90
          });
          return 100;
        }
        return prev + 10;
      });
    }, 200);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Animated Background */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-pulse"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-blue-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-pulse delay-1000"></div>
      </div>

      <div className="relative z-10 container mx-auto px-6 py-12">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="text-center mb-12">
            <h1 className="text-5xl font-bold mb-6 text-white">
              AI-Powered <span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">PCB Analysis</span>
            </h1>
            <p className="text-xl text-white/80 max-w-3xl mx-auto">
              Upload a PCB image and get instant component detection, value assessment, and educational insights
            </p>
          </div>

          <div className="grid lg:grid-cols-2 gap-12">
            {/* Upload Section */}
            <div className="space-y-8">
              <div className="bg-white/5 backdrop-blur-md rounded-2xl border border-white/10 p-8">
                <h2 className="text-2xl font-bold mb-6 text-white flex items-center">
                  <Upload className="w-6 h-6 mr-3 text-purple-400" />
                  Upload PCB Image
                </h2>
                
                {!uploadedImage ? (
                  <div 
                    className="border-2 border-dashed border-white/20 rounded-xl p-12 text-center hover:border-purple-400 transition-colors cursor-pointer"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Upload className="w-16 h-16 mx-auto mb-4 text-white/40" />
                    <p className="text-white/60 mb-2">Click to upload or drag and drop</p>
                    <p className="text-sm text-white/40">PNG, JPG, JPEG up to 10MB</p>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      onChange={handleFileUpload}
                      className="hidden"
                    />
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="relative">
                      <img 
                        src={uploadedImage} 
                        alt="Uploaded PCB" 
                        className="w-full h-64 object-cover rounded-xl"
                      />
                      <button 
                        onClick={() => setUploadedImage(null)}
                        className="absolute top-2 right-2 bg-red-500 text-white p-2 rounded-full hover:bg-red-600 transition-colors"
                      >
                        ×
                      </button>
                    </div>
                    
                    <div className="flex gap-3">
                      <button
                        onClick={simulateAnalysis}
                        disabled={isAnalyzing}
                        className="flex-1 bg-gradient-to-r from-purple-500 to-blue-500 text-white py-3 px-6 rounded-xl hover:from-purple-600 hover:to-blue-600 transition-all duration-300 transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                      >
                        {isAnalyzing ? (
                          <>
                            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-3"></div>
                            Analyzing...
                          </>
                        ) : (
                          <>
                            <Zap className="w-5 h-5 mr-3" />
                            Analyze PCB
                          </>
                        )}
                      </button>
                      
                      <button className="bg-white/10 text-white py-3 px-6 rounded-xl hover:bg-white/20 transition-colors">
                        <Settings className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Analysis Options */}
              <div className="bg-white/5 backdrop-blur-md rounded-2xl border border-white/10 p-8">
                <h3 className="text-xl font-bold mb-4 text-white">Analysis Options</h3>
                <div className="space-y-4">
                  <label className="flex items-center space-x-3">
                    <input type="checkbox" defaultChecked className="w-4 h-4 text-purple-500 rounded" />
                    <span className="text-white/80">Component Detection</span>
                  </label>
                  <label className="flex items-center space-x-3">
                    <input type="checkbox" defaultChecked className="w-4 h-4 text-purple-500 rounded" />
                    <span className="text-white/80">Value Assessment</span>
                  </label>
                  <label className="flex items-center space-x-3">
                    <input type="checkbox" defaultChecked className="w-4 h-4 text-purple-500 rounded" />
                    <span className="text-white/80">Educational Insights</span>
                  </label>
                  <label className="flex items-center space-x-3">
                    <input type="checkbox" defaultChecked className="w-4 h-4 text-purple-500 rounded" />
                    <span className="text-white/80">Project Recommendations</span>
                  </label>
                </div>
              </div>
            </div>

            {/* Results Section */}
            <div className="space-y-8">
              {/* Progress */}
              {isAnalyzing && (
                <div className="bg-white/5 backdrop-blur-md rounded-2xl border border-white/10 p-8">
                  <h3 className="text-xl font-bold mb-4 text-white flex items-center">
                    <Brain className="w-6 h-6 mr-3 text-purple-400" />
                    Analysis Progress
                  </h3>
                  <div className="space-y-4">
                    <div className="flex justify-between text-white/80">
                      <span>Processing image...</span>
                      <span>{progress}%</span>
                    </div>
                    <div className="w-full bg-white/10 rounded-full h-3">
                      <div 
                        className="bg-gradient-to-r from-purple-500 to-blue-500 h-3 rounded-full transition-all duration-300"
                        style={{ width: `${progress}%` }}
                      ></div>
                    </div>
                    <div className="text-sm text-white/60">
                      {progress < 30 && "Initializing AI models..."}
                      {progress >= 30 && progress < 60 && "Detecting components..."}
                      {progress >= 60 && progress < 90 && "Analyzing capabilities..."}
                      {progress >= 90 && "Generating recommendations..."}
                    </div>
                  </div>
                </div>
              )}

              {/* Results */}
              {analysisResults && (
                <div className="space-y-6">
                  {/* Summary */}
                  <div className="bg-white/5 backdrop-blur-md rounded-2xl border border-white/10 p-8">
                    <h3 className="text-xl font-bold mb-4 text-white flex items-center">
                      <CheckCircle className="w-6 h-6 mr-3 text-green-400" />
                      Analysis Complete
                    </h3>
                    <div className="grid grid-cols-3 gap-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-white">{analysisResults.components.length}</div>
                        <div className="text-sm text-white/60">Components</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-white">{analysisResults.totalValue}</div>
                        <div className="text-sm text-white/60">Total Value</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-white">{analysisResults.processingTime}</div>
                        <div className="text-sm text-white/60">Processing Time</div>
                      </div>
                    </div>
                  </div>

                  {/* Components */}
                  <div className="bg-white/5 backdrop-blur-md rounded-2xl border border-white/10 p-8">
                    <h3 className="text-xl font-bold mb-4 text-white flex items-center">
                      <Target className="w-6 h-6 mr-3 text-purple-400" />
                      Detected Components
                    </h3>
                    <div className="space-y-3">
                      {analysisResults.components.map((component: any, index: number) => (
                        <div key={index} className="flex items-center justify-between p-4 bg-white/5 rounded-xl">
                          <div className="flex items-center space-x-3">
                            <div className="w-10 h-10 bg-gradient-to-r from-purple-500 to-blue-500 rounded-lg flex items-center justify-center">
                              <span className="text-white font-bold">{index + 1}</span>
                            </div>
                            <div>
                              <div className="font-semibold text-white">{component.type}</div>
                              <div className="text-sm text-white/60">{component.description}</div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-semibold text-white">{component.value}</div>
                            <div className="text-sm text-white/60">{(component.confidence * 100).toFixed(0)}% confidence</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-3">
                    <button className="flex-1 bg-gradient-to-r from-green-500 to-emerald-500 text-white py-3 px-6 rounded-xl hover:from-green-600 hover:to-emerald-600 transition-all duration-300 transform hover:scale-105 flex items-center justify-center">
                      <Download className="w-5 h-5 mr-3" />
                      Export Results
                    </button>
                    <button className="bg-white/10 text-white py-3 px-6 rounded-xl hover:bg-white/20 transition-colors">
                      <Share2 className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              )}

              {/* Demo Mode */}
              {!uploadedImage && !analysisResults && (
                <div className="bg-white/5 backdrop-blur-md rounded-2xl border border-white/10 p-8">
                  <h3 className="text-xl font-bold mb-4 text-white flex items-center">
                    <Play className="w-6 h-6 mr-3 text-purple-400" />
                    Try Demo Mode
                  </h3>
                  <p className="text-white/60 mb-4">
                    Want to see how it works? Try our demo with a sample PCB image.
                  </p>
                  <button 
                    onClick={() => {
                      setUploadedImage('/api/placeholder/400/300');
                      setTimeout(simulateAnalysis, 1000);
                    }}
                    className="w-full bg-gradient-to-r from-purple-500 to-blue-500 text-white py-3 px-6 rounded-xl hover:from-purple-600 hover:to-blue-600 transition-all duration-300 transform hover:scale-105 flex items-center justify-center"
                  >
                    <Play className="w-5 h-5 mr-3" />
                    Run Demo Analysis
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}