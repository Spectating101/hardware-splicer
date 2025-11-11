'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { motion } from 'framer-motion';
import { Zap, Code, Terminal, BookOpen, ArrowRight, Copy, Check, ExternalLink, Key, Database, Cpu, Users, Shield, Clock } from 'lucide-react';
import Link from 'next/link';

export default function MarketingPage() {
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const copyToClipboard = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(id);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const curlExample = `curl -X POST "https://api.circuit-ai.com/v1/analyze" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: multipart/form-data" \\
  -F "image=@pcb_image.jpg"`;

  const pythonExample = `import circuitai

client = circuitai.Client(api_key="YOUR_API_KEY")

# Analyze a PCB image
result = client.analyze_pcb("pcb_image.jpg")

print(f"Found {len(result.components)} components")
for component in result.components:
    print(f"- {component.name}: ${component.value}")`;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Navigation */}
      <nav className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-lg flex items-center justify-center">
                <Cpu className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold text-slate-900">Circuit.AI</span>
            </div>
            <div className="flex items-center space-x-4">
              <Link href="/docs" className="text-slate-600 hover:text-slate-900 transition-colors">
                Docs
              </Link>
              <Link href="/playground" className="text-slate-600 hover:text-slate-900 transition-colors">
                Playground
              </Link>
              <Link href="/pricing" className="text-slate-600 hover:text-slate-900 transition-colors">
                Pricing
              </Link>
              <Button className="bg-blue-600 hover:bg-blue-700 text-white">
                <Key className="w-4 h-4 mr-2" />
                Get API Key
              </Button>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="relative overflow-hidden bg-gradient-to-br from-slate-50 to-blue-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24">
          <div className="text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8 }}
            >
              <h1 className="text-5xl md:text-7xl font-bold text-slate-900 mb-6">
                PCB Analysis
                <span className="block bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                  API Platform
                </span>
              </h1>
              <p className="text-xl text-slate-600 mb-8 max-w-3xl mx-auto">
                Enterprise-grade AI for PCB component detection, analysis, and insights. 
                Built for developers, integrated by teams.
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-12"
            >
              <Button 
                size="lg" 
                className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 text-lg"
              >
                <Key className="w-5 h-5 mr-2" />
                Get API Key
              </Button>
              <Link href="/playground">
                <Button 
                  variant="outline" 
                  size="lg"
                  className="border-slate-300 text-slate-700 hover:bg-slate-50 px-8 py-4 text-lg"
                >
                  <Terminal className="w-5 h-5 mr-2" />
                  Try Playground
                </Button>
              </Link>
            </motion.div>

            {/* API Example */}
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.8, delay: 0.4 }}
              className="max-w-4xl mx-auto"
            >
              <Card className="bg-slate-900 border-slate-700">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Terminal className="w-5 h-5 text-green-400" />
                      <span className="text-green-400 font-mono text-sm">API Example</span>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => copyToClipboard(curlExample, 'curl')}
                      className="text-slate-400 hover:text-white"
                    >
                      {copiedCode === 'curl' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <pre className="text-green-400 font-mono text-sm overflow-x-auto">
                    <code>{curlExample}</code>
                  </pre>
                </CardContent>
              </Card>
            </motion.div>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-900 mb-4">
              Enterprise-Grade PCB Analysis
            </h2>
            <p className="text-xl text-slate-600 max-w-2xl mx-auto">
              Production-ready API with advanced computer vision and machine learning
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
            >
              <Card className="border-slate-200 hover:border-blue-300 transition-all duration-300">
                <CardHeader>
                  <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-indigo-500 rounded-lg flex items-center justify-center mb-4">
                    <Cpu className="w-6 h-6 text-white" />
                  </div>
                  <CardTitle className="text-slate-900">AI Detection</CardTitle>
                  <CardDescription className="text-slate-600">
                    YOLO + computer vision algorithms with 95%+ accuracy for component identification
                  </CardDescription>
                </CardHeader>
              </Card>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
            >
              <Card className="border-slate-200 hover:border-blue-300 transition-all duration-300">
                <CardHeader>
                  <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-indigo-500 rounded-lg flex items-center justify-center mb-4">
                    <Zap className="w-6 h-6 text-white" />
                  </div>
                  <CardTitle className="text-slate-900">Real-time Streaming</CardTitle>
                  <CardDescription className="text-slate-600">
                    WebSocket-powered live updates and streaming analysis results
                  </CardDescription>
                </CardHeader>
              </Card>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            >
              <Card className="border-slate-200 hover:border-blue-300 transition-all duration-300">
                <CardHeader>
                  <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-indigo-500 rounded-lg flex items-center justify-center mb-4">
                    <Database className="w-6 h-6 text-white" />
                  </div>
                  <CardTitle className="text-slate-900">Curated Dataset</CardTitle>
                  <CardDescription className="text-slate-600">
                    Professional component database with detailed specifications and documentation
                  </CardDescription>
                </CardHeader>
              </Card>
            </motion.div>
          </div>
        </div>
      </div>

      {/* SDK Examples */}
      <div className="py-24 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-900 mb-4">
              SDKs & Integrations
            </h2>
            <p className="text-xl text-slate-600 max-w-2xl mx-auto">
              Native SDKs for popular languages and frameworks
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Python SDK */}
            <Card className="border-slate-200">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Code className="w-5 h-5 text-blue-600" />
                    <span className="font-semibold text-slate-900">Python SDK</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(pythonExample, 'python')}
                  >
                    {copiedCode === 'python' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <pre className="bg-slate-900 text-green-400 font-mono text-sm p-4 rounded-lg overflow-x-auto">
                  <code>{pythonExample}</code>
                </pre>
              </CardContent>
            </Card>

            {/* JavaScript SDK */}
            <Card className="border-slate-200">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Code className="w-5 h-5 text-blue-600" />
                    <span className="font-semibold text-slate-900">JavaScript SDK</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard('npm install circuit-ai-sdk', 'js')}
                  >
                    {copiedCode === 'js' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <pre className="bg-slate-900 text-green-400 font-mono text-sm p-4 rounded-lg overflow-x-auto">
                  <code>{`npm install circuit-ai-sdk

import CircuitAI from 'circuit-ai-sdk';

const client = new CircuitAI({
  apiKey: 'YOUR_API_KEY'
});

const result = await client.analyzePCB('pcb_image.jpg');`}</code>
                </pre>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Use Cases */}
      <div className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-900 mb-4">
              Built for Every Use Case
            </h2>
            <p className="text-xl text-slate-600 max-w-2xl mx-auto">
              From educational platforms to enterprise manufacturing
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <Card className="border-slate-200">
              <CardHeader>
                <div className="w-12 h-12 bg-gradient-to-r from-green-500 to-emerald-500 rounded-lg flex items-center justify-center mb-4">
                  <BookOpen className="w-6 h-6 text-white" />
                </div>
                <CardTitle className="text-slate-900">Educational Technology</CardTitle>
                <CardDescription className="text-slate-600">
                  Integrate PCB analysis into electronics courses and maker spaces
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="border-slate-200">
              <CardHeader>
                <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-indigo-500 rounded-lg flex items-center justify-center mb-4">
                  <Users className="w-6 h-6 text-white" />
                </div>
                <CardTitle className="text-slate-900">Electronics Industry</CardTitle>
                <CardDescription className="text-slate-600">
                  Automated inventory management and quality control
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="border-slate-200">
              <CardHeader>
                <div className="w-12 h-12 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg flex items-center justify-center mb-4">
                  <Shield className="w-6 h-6 text-white" />
                </div>
                <CardTitle className="text-slate-900">E-waste Management</CardTitle>
                <CardDescription className="text-slate-600">
                  Automated component extraction and sustainability programs
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="py-24 bg-blue-600">
        <div className="max-w-4xl mx-auto text-center px-4 sm:px-6 lg:px-8">
          <h2 className="text-4xl font-bold text-white mb-6">
            Ready to Build with Circuit.AI?
          </h2>
          <p className="text-xl text-blue-100 mb-8">
            Join teams building the future of electronics analysis
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button 
              size="lg" 
              className="bg-white text-blue-600 hover:bg-blue-50 px-8 py-4 text-lg"
            >
              <Key className="w-5 h-5 mr-2" />
              Get API Key
            </Button>
            <Link href="/docs">
              <Button 
                variant="outline" 
                size="lg"
                className="border-white text-white hover:bg-white hover:text-blue-600 px-8 py-4 text-lg"
              >
                <BookOpen className="w-5 h-5 mr-2" />
                Read Documentation
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-slate-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-indigo-500 rounded-lg flex items-center justify-center">
                  <Cpu className="w-5 h-5 text-white" />
                </div>
                <span className="text-xl font-bold text-white">Circuit.AI</span>
              </div>
              <p className="text-slate-400">
                Enterprise PCB analysis API platform for developers and teams.
              </p>
            </div>
            <div>
              <h3 className="text-white font-semibold mb-4">API</h3>
              <ul className="space-y-2 text-slate-400">
                <li><Link href="/docs" className="hover:text-white transition-colors">Documentation</Link></li>
                <li><Link href="/playground" className="hover:text-white transition-colors">Playground</Link></li>
                <li><Link href="/pricing" className="hover:text-white transition-colors">Pricing</Link></li>
                <li><a href="#" className="hover:text-white transition-colors">Status</a></li>
              </ul>
            </div>
            <div>
              <h3 className="text-white font-semibold mb-4">SDKs</h3>
              <ul className="space-y-2 text-slate-400">
                <li><a href="#" className="hover:text-white transition-colors">Python</a></li>
                <li><a href="#" className="hover:text-white transition-colors">JavaScript</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Go</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Rust</a></li>
              </ul>
            </div>
            <div>
              <h3 className="text-white font-semibold mb-4">Support</h3>
              <ul className="space-y-2 text-slate-400">
                <li><a href="#" className="hover:text-white transition-colors">Help Center</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Contact</a></li>
                <li><a href="#" className="hover:text-white transition-colors">GitHub</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Discord</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-slate-800 mt-8 pt-8 text-center text-slate-400">
            <p>&copy; 2024 Circuit.AI. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
