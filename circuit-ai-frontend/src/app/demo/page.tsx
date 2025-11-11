"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { 
  Play, 
  Pause, 
  RotateCcw, 
  Eye, 
  Download,
  CheckCircle,
  AlertCircle,
  Loader2,
  CircuitBoard,
  Zap,
  Target,
  DollarSign
} from "lucide-react";

export default function DemoPage() {
  const [isRunning, setIsRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [progress, setProgress] = useState(0);

  const demoSteps = [
    {
      title: "Image Upload",
      description: "Uploading PCB image for analysis",
      icon: CircuitBoard,
      duration: 1000
    },
    {
      title: "Component Detection",
      description: "AI detecting electronic components",
      icon: Eye,
      duration: 2000
    },
    {
      title: "Capability Analysis",
      description: "Analyzing component capabilities",
      icon: Zap,
      duration: 1500
    },
    {
      title: "Value Assessment",
      description: "Calculating market value",
      icon: DollarSign,
      duration: 1000
    },
    {
      title: "Project Recommendations",
      description: "Generating educational projects",
      icon: Target,
      duration: 1500
    }
  ];

  const demoResults = {
    components: [
      { type: "IC Chip", count: 2, value: 1.00, confidence: 0.93 },
      { type: "Capacitor", count: 5, value: 1.25, confidence: 0.75 },
      { type: "Connector", count: 1, value: 0.10, confidence: 0.85 }
    ],
    totalValue: 2.35,
    projectPotential: "Good",
    capabilities: [
      "arduino_projects", "iot_devices", "power_filtering", 
      "audio_circuits", "signal_transmission", "voltage_regulation"
    ],
    recommendations: [
      {
        name: "Arduino Weather Station",
        score: 85,
        components: 6,
        time: "2-4 hours",
        value: 15.00
      },
      {
        name: "LED Pattern Controller",
        score: 72,
        components: 4,
        time: "1-2 hours",
        value: 8.00
      }
    ]
  };

  const startDemo = () => {
    setIsRunning(true);
    setCurrentStep(0);
    setProgress(0);
    
    let stepIndex = 0;
    const runStep = () => {
      if (stepIndex < demoSteps.length) {
        setCurrentStep(stepIndex);
        const step = demoSteps[stepIndex];
        
        // Animate progress for this step
        const stepProgress = 100 / demoSteps.length;
        const startProgress = stepIndex * stepProgress;
        const endProgress = (stepIndex + 1) * stepProgress;
        
        let currentProgress = startProgress;
        const progressInterval = setInterval(() => {
          currentProgress += 2;
          setProgress(currentProgress);
          
          if (currentProgress >= endProgress) {
            clearInterval(progressInterval);
            stepIndex++;
            setTimeout(runStep, 500);
          }
        }, step.duration / 50);
      } else {
        setIsRunning(false);
      }
    };
    
    runStep();
  };

  const resetDemo = () => {
    setIsRunning(false);
    setCurrentStep(0);
    setProgress(0);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">Circuit.AI Demo</h1>
        <p className="text-xl text-gray-600">
          See how our AI-powered PCB analysis works in action
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        {/* Demo Controls */}
        <Card>
          <CardHeader>
            <CardTitle>Demo Controls</CardTitle>
            <CardDescription>
              Run a demonstration of the analysis process
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Demo Image */}
            <div className="text-center">
              <div className="w-full h-64 bg-gradient-to-br from-gray-100 to-gray-200 rounded-lg flex items-center justify-center mb-4">
                <div className="text-center">
                  <CircuitBoard className="w-16 h-16 mx-auto text-gray-400 mb-2" />
                  <p className="text-gray-600">Demo PCB Image</p>
                </div>
              </div>
            </div>

            {/* Controls */}
            <div className="flex gap-4">
              <Button
                onClick={startDemo}
                disabled={isRunning}
                variant="gradient"
                className="flex-1"
              >
                {isRunning ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 mr-2" />
                    Start Demo
                  </>
                )}
              </Button>
              <Button
                onClick={resetDemo}
                variant="outline"
                disabled={isRunning}
              >
                <RotateCcw className="w-4 h-4 mr-2" />
                Reset
              </Button>
            </div>

            {/* Progress */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Analysis Progress</span>
                <span>{Math.round(progress)}%</span>
              </div>
              <Progress value={progress} />
            </div>

            {/* Current Step */}
            {isRunning && currentStep < demoSteps.length && (
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                    <demoSteps[currentStep].icon className="w-4 h-4 text-white" />
                  </div>
                  <div>
                    <div className="font-medium">{demoSteps[currentStep].title}</div>
                    <div className="text-sm text-gray-600">{demoSteps[currentStep].description}</div>
                  </div>
                </div>
              </div>
            )}

            {/* Completion */}
            {!isRunning && progress >= 100 && (
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center gap-3">
                  <CheckCircle className="w-6 h-6 text-green-600" />
                  <div>
                    <div className="font-medium text-green-800">Analysis Complete!</div>
                    <div className="text-sm text-green-600">View results below</div>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Results */}
        <div className="space-y-6">
          {progress >= 100 ? (
            <>
              {/* Summary */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    Analysis Results
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-center p-4 bg-blue-50 rounded-lg">
                      <div className="text-2xl font-bold text-blue-600">
                        {demoResults.components.reduce((sum, c) => sum + c.count, 0)}
                      </div>
                      <div className="text-sm text-gray-600">Components</div>
                    </div>
                    <div className="text-center p-4 bg-green-50 rounded-lg">
                      <div className="text-2xl font-bold text-green-600">
                        ${demoResults.totalValue}
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
                    {demoResults.components.map((component, index) => (
                      <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div>
                          <div className="font-medium">{component.type}</div>
                          <div className="text-sm text-gray-600">
                            Count: {component.count} | Confidence: {(component.confidence * 100).toFixed(0)}%
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-bold">${component.value}</div>
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
                    {demoResults.capabilities.map((capability, index) => (
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

              {/* Project Recommendations */}
              <Card>
                <CardHeader>
                  <CardTitle>Project Recommendations</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {demoResults.recommendations.map((project, index) => (
                      <div key={index} className="p-4 border border-gray-200 rounded-lg">
                        <div className="flex items-center justify-between mb-2">
                          <div className="font-medium">{project.name}</div>
                          <div className="text-sm font-bold text-green-600">${project.value}</div>
                        </div>
                        <div className="flex items-center justify-between text-sm text-gray-600">
                          <span>Score: {project.score}%</span>
                          <span>Components: {project.components}/8</span>
                          <span>Time: {project.time}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Analysis Results</CardTitle>
                <CardDescription>
                  Results will appear here after the demo completes
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-12 text-gray-500">
                  <CircuitBoard className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>Run the demo to see analysis results</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Features Highlight */}
      <Card>
        <CardHeader>
          <CardTitle>What You Just Saw</CardTitle>
          <CardDescription>
            Key features demonstrated in this demo
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-cyan-600 rounded-lg flex items-center justify-center mx-auto mb-4">
                <Eye className="w-6 h-6 text-white" />
              </div>
              <h3 className="font-semibold mb-2">Component Detection</h3>
              <p className="text-sm text-gray-600">
                AI-powered identification of electronic components with confidence scores
              </p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 bg-gradient-to-r from-green-500 to-emerald-600 rounded-lg flex items-center justify-center mx-auto mb-4">
                <DollarSign className="w-6 h-6 text-white" />
              </div>
              <h3 className="font-semibold mb-2">Value Assessment</h3>
              <p className="text-sm text-gray-600">
                Real-time calculation of component market value and educational potential
              </p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 bg-gradient-to-r from-purple-500 to-pink-600 rounded-lg flex items-center justify-center mx-auto mb-4">
                <Target className="w-6 h-6 text-white" />
              </div>
              <h3 className="font-semibold mb-2">Project Matching</h3>
              <p className="text-sm text-gray-600">
                Intelligent recommendations for educational projects based on available components
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
