'use client';

import { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { motion } from 'framer-motion';
import { Upload, Play, Copy, Check, Download, Eye, Code, Terminal, Zap } from 'lucide-react';

export default function PlaygroundPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [apiKey, setApiKey] = useState('');
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setAnalysisResult(null);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedFile || !apiKey) return;

    setIsAnalyzing(true);
    try {
      const formData = new FormData();
      formData.append('image', selectedFile);

      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
        },
        body: formData,
      });

      const result = await response.json();
      setAnalysisResult(result);
    } catch (error) {
      console.error('Analysis failed:', error);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const copyToClipboard = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(id);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const generateCurlCommand = () => {
    if (!selectedFile) return '';
    return `curl -X POST "https://api.circuit-ai.com/v1/analyze" \\
  -H "Authorization: Bearer ${apiKey || 'YOUR_API_KEY'}" \\
  -H "Content-Type: multipart/form-data" \\
  -F "image=@${selectedFile.name}"`;
  };

  const generatePythonCode = () => {
    if (!selectedFile) return '';
    return `import circuitai

client = circuitai.Client(api_key="${apiKey || 'YOUR_API_KEY'}")

# Analyze a PCB image
result = client.analyze_pcb("${selectedFile.name}")

print(f"Found {len(result.components)} components")
for component in result.components:
    print(f"- {component.name}: {component.confidence:.2f}")
    print(f"  Value: ${component.value}")
    print(f"  Function: {component.function}")`;
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="border-b border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-900">API Playground</h1>
              <p className="text-slate-600 mt-1">Test Circuit.AI API endpoints with real PCB images</p>
            </div>
            <div className="flex items-center space-x-4">
              <Input
                type="password"
                placeholder="Enter API Key"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-64"
              />
              <Button variant="outline">
                <Terminal className="w-4 h-4 mr-2" />
                View Docs
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Upload Section */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Upload className="w-5 h-5 mr-2" />
                  Upload PCB Image
                </CardTitle>
                <CardDescription>
                  Upload a PCB image to test the analysis API
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div
                    className="border-2 border-dashed border-slate-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors cursor-pointer"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    {selectedFile ? (
                      <div className="space-y-2">
                        <Eye className="w-12 h-12 text-blue-500 mx-auto" />
                        <p className="text-slate-900 font-medium">{selectedFile.name}</p>
                        <p className="text-sm text-slate-500">
                          {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <Upload className="w-12 h-12 text-slate-400 mx-auto" />
                        <p className="text-slate-600">Click to upload or drag and drop</p>
                        <p className="text-sm text-slate-500">PNG, JPG, JPEG up to 10MB</p>
                      </div>
                    )}
                  </div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                  
                  <Button
                    onClick={handleAnalyze}
                    disabled={!selectedFile || !apiKey || isAnalyzing}
                    className="w-full"
                  >
                    {isAnalyzing ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                        Analyzing...
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4 mr-2" />
                        Analyze PCB
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* API Response */}
            {analysisResult && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center">
                    <Zap className="w-5 h-5 mr-2" />
                    Analysis Results
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-blue-50 p-4 rounded-lg">
                        <p className="text-sm text-blue-600 font-medium">Components Found</p>
                        <p className="text-2xl font-bold text-blue-900">
                          {analysisResult.components?.length || 0}
                        </p>
                      </div>
                      <div className="bg-green-50 p-4 rounded-lg">
                        <p className="text-sm text-green-600 font-medium">Total Value</p>
                        <p className="text-2xl font-bold text-green-900">
                          ${analysisResult.total_value || '0.00'}
                        </p>
                      </div>
                    </div>
                    
                    {analysisResult.components && (
                      <div className="space-y-2">
                        <h4 className="font-medium text-slate-900">Detected Components:</h4>
                        <div className="max-h-48 overflow-y-auto space-y-2">
                          {analysisResult.components.map((component: any, index: number) => (
                            <div key={index} className="bg-slate-50 p-3 rounded-lg">
                              <div className="flex justify-between items-start">
                                <div>
                                  <p className="font-medium text-slate-900">{component.name}</p>
                                  <p className="text-sm text-slate-600">{component.function}</p>
                                </div>
                                <div className="text-right">
                                  <p className="text-sm font-medium text-green-600">
                                    ${component.value}
                                  </p>
                                  <p className="text-xs text-slate-500">
                                    {Math.round(component.confidence * 100)}% confidence
                                  </p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Code Examples */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Code className="w-5 h-5 mr-2" />
                  cURL Command
                </CardTitle>
                <CardDescription>
                  Copy this command to test the API from your terminal
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="relative">
                  <pre className="bg-slate-900 text-green-400 font-mono text-sm p-4 rounded-lg overflow-x-auto">
                    <code>{generateCurlCommand()}</code>
                  </pre>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="absolute top-2 right-2"
                    onClick={() => copyToClipboard(generateCurlCommand(), 'curl')}
                  >
                    {copiedCode === 'curl' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Code className="w-5 h-5 mr-2" />
                  Python SDK
                </CardTitle>
                <CardDescription>
                  Example using the Circuit.AI Python SDK
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="relative">
                  <pre className="bg-slate-900 text-green-400 font-mono text-sm p-4 rounded-lg overflow-x-auto">
                    <code>{generatePythonCode()}</code>
                  </pre>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="absolute top-2 right-2"
                    onClick={() => copyToClipboard(generatePythonCode(), 'python')}
                  >
                    {copiedCode === 'python' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>API Response Format</CardTitle>
                <CardDescription>
                  Example JSON response from the analysis endpoint
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="bg-slate-900 text-green-400 font-mono text-sm p-4 rounded-lg overflow-x-auto">
                  <code>{`{
  "success": true,
  "analysis_id": "anal_123456789",
  "components": [
    {
      "name": "Arduino Uno R3",
      "type": "microcontroller",
      "confidence": 0.95,
      "value": 25.00,
      "function": "Main processing unit",
      "position": {"x": 100, "y": 150},
      "specifications": {
        "voltage": "5V",
        "current": "20mA",
        "pins": 14
      }
    }
  ],
  "total_value": 25.00,
  "analysis_time": 2.3,
  "timestamp": "2024-01-15T10:30:00Z"
}`}</code>
                </pre>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
