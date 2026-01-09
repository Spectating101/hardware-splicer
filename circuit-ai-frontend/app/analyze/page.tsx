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
import { apiClient } from '@/lib/api';

export default function AnalyzePage() {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [analysisResults, setAnalysisResults] = useState<any>(null);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState<string>('Ready');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      const reader = new FileReader();
      reader.onload = (e) => {
        setUploadedImage(e.target?.result as string);
        setAnalysisResults(null); // Reset results on new upload
      };
      reader.readAsDataURL(file);
    }
  };

  const startAnalysis = async () => {
    if (!selectedFile) return;

    setIsAnalyzing(true);
    setProgress(0);
    setStatusMessage('Initializing analysis...');

    try {
      const result = await apiClient.analyzePCB(selectedFile, {
        backend: 'ensemble',
        enableOcr: true,
        onProgress: (p, step) => {
          setProgress(p);
          setStatusMessage(step);
        }
      });

      setAnalysisResults(result);
      setStatusMessage('Analysis complete!');
    } catch (error) {
      console.error('Analysis failed:', error);
      setStatusMessage('Analysis failed. Please try again.');
    } finally {
      setIsAnalyzing(false);
      setProgress(100);
    }
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
                    <p className="text-white/40 text-sm">Supports JPG, PNG (Max 10MB)</p>
                  </div>
                ) : (
                  <div className="relative rounded-xl overflow-hidden border border-white/20">
                    <img src={uploadedImage} alt="PCB" className="w-full h-auto" />
                    <button 
                      onClick={() => {
                        setUploadedImage(null);
                        setSelectedFile(null);
                        setAnalysisResults(null);
                      }}
                      className="absolute top-4 right-4 bg-black/60 p-2 rounded-full hover:bg-black/80 transition-colors"
                    >
                      <RotateCcw className="w-5 h-5 text-white" />
                    </button>
                  </div>
                )}
                
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  className="hidden" 
                  accept="image/*"
                  onChange={handleFileUpload}
                />

                {/* Analysis Controls */}
                {uploadedImage && !analysisResults && (
                  <button
                    onClick={startAnalysis}
                    disabled={isAnalyzing}
                    className={`w-full mt-6 py-4 rounded-xl font-bold text-lg flex items-center justify-center transition-all ${
                      isAnalyzing 
                        ? 'bg-white/10 text-white/50 cursor-not-allowed'
                        : 'bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-400 hover:to-blue-400 text-white shadow-lg hover:shadow-purple-500/25'
                    }`}
                  >
                    {isAnalyzing ? (
                      <>
                        <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-3" />
                        {statusMessage}... {progress}%
                      </>
                    ) : (
                      <>
                        <Zap className="w-5 h-5 mr-2" />
                        Start Analysis
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>

            {/* Results Section */}
            <div className="space-y-6">
              {analysisResults ? (
                <div className="bg-white/5 backdrop-blur-md rounded-2xl border border-white/10 p-8 h-full">
                  <div className="flex justify-between items-start mb-8">
                    <div>
                      <h2 className="text-2xl font-bold text-white mb-2">Analysis Results</h2>
                      <div className="flex items-center space-x-4 text-sm text-white/60">
                        <span className="flex items-center"><Clock className="w-4 h-4 mr-1" /> {analysisResults.processing_time || '2.3s'}</span>
                        <span className="flex items-center"><Target className="w-4 h-4 mr-1" /> {Math.round((analysisResults.confidence || 0.9) * 100)}% Confidence</span>
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <button className="p-2 hover:bg-white/10 rounded-lg transition-colors" title="Download Report">
                        <Download className="w-5 h-5 text-white/80" />
                      </button>
                      <button className="p-2 hover:bg-white/10 rounded-lg transition-colors" title="Share Analysis">
                        <Share2 className="w-5 h-5 text-white/80" />
                      </button>
                    </div>
                  </div>

                  {/* Component List */}
                  <div className="space-y-4">
                    {analysisResults.detections?.map((comp: any, i: number) => (
                      <div key={i} className="bg-white/5 rounded-xl p-4 border border-white/5 hover:border-white/20 transition-colors">
                        <div className="flex justify-between items-start">
                          <div className="flex items-start">
                            <div className="p-2 bg-purple-500/20 rounded-lg mr-4">
                              <Brain className="w-5 h-5 text-purple-400" />
                            </div>
                            <div>
                              <h3 className="font-semibold text-white">{comp.class_name || comp.type}</h3>
                              <p className="text-sm text-white/60">{comp.ocr_text || 'Electronic Component'}</p>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-emerald-400 font-mono">{comp.part_number || 'N/A'}</div>
                            <div className="text-xs text-white/40">{Math.round((comp.confidence || 0) * 100)}% Match</div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                  
                  {/* JSON Dump (for debugging) */}
                  <div className="mt-8 pt-8 border-t border-white/10">
                    <h3 className="text-white/60 text-sm font-semibold mb-2">Raw Data</h3>
                    <pre className="bg-black/30 p-4 rounded-lg text-xs text-white/40 overflow-x-auto">
                      {JSON.stringify(analysisResults, null, 2)}
                    </pre>
                  </div>

                </div>
              ) : (
                <div className="h-full flex items-center justify-center p-12 border-2 border-dashed border-white/5 rounded-2xl text-center">
                  <div className="max-w-sm">
                    <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-6">
                      <Brain className="w-8 h-8 text-white/20" />
                    </div>
                    <h3 className="text-xl font-semibold text-white mb-2">Ready to Analyze</h3>
                    <p className="text-white/40">Upload an image to see the AI breakdown of components, faults, and value.</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
