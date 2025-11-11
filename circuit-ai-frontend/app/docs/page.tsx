'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { motion } from 'framer-motion';
import { Copy, Check, ExternalLink, Key, Zap, Database, Cpu, Globe } from 'lucide-react';

export default function DocsPage() {
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const copyToClipboard = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(id);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const endpoints = [
    {
      method: 'POST',
      path: '/v1/analyze',
      description: 'Analyze a PCB image for component detection and value assessment',
      example: `curl -X POST "https://api.circuit-ai.com/v1/analyze" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: multipart/form-data" \\
  -F "image=@pcb_image.jpg"`
    },
    {
      method: 'GET',
      path: '/v1/components',
      description: 'Get information about specific electronic components',
      example: `curl -X GET "https://api.circuit-ai.com/v1/components?search=arduino" \\
  -H "Authorization: Bearer YOUR_API_KEY"`
    },
    {
      method: 'GET',
      path: '/v1/projects',
      description: 'Get educational project recommendations based on components',
      example: `curl -X GET "https://api.circuit-ai.com/v1/projects?components=arduino,led,resistor" \\
  -H "Authorization: Bearer YOUR_API_KEY"`
    },
    {
      method: 'GET',
      path: '/v1/educational/{component_id}',
      description: 'Get educational content and tutorials for a specific component',
      example: `curl -X GET "https://api.circuit-ai.com/v1/educational/arduino-uno" \\
  -H "Authorization: Bearer YOUR_API_KEY"`
    }
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="border-b border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-900">API Documentation</h1>
              <p className="text-slate-600 mt-1">Complete reference for Circuit.AI API endpoints</p>
            </div>
            <div className="flex items-center space-x-4">
              <Button variant="outline">
                <Key className="w-4 h-4 mr-2" />
                Get API Key
              </Button>
              <Button>
                <ExternalLink className="w-4 h-4 mr-2" />
                Try Playground
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Sidebar */}
          <div className="lg:col-span-1">
            <div className="sticky top-8">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Quick Start</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <a href="#authentication" className="block text-blue-600 hover:text-blue-800">Authentication</a>
                  <a href="#endpoints" className="block text-blue-600 hover:text-blue-800">Endpoints</a>
                  <a href="#sdks" className="block text-blue-600 hover:text-blue-800">SDKs</a>
                  <a href="#rate-limits" className="block text-blue-600 hover:text-blue-800">Rate Limits</a>
                  <a href="#errors" className="block text-blue-600 hover:text-blue-800">Error Handling</a>
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Main Content */}
          <div className="lg:col-span-3 space-y-8">
            {/* Authentication */}
            <Card id="authentication">
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Key className="w-5 h-5 mr-2" />
                  Authentication
                </CardTitle>
                <CardDescription>
                  All API requests require authentication using your API key
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-slate-600">
                  Include your API key in the Authorization header of all requests:
                </p>
                <div className="relative">
                  <pre className="bg-slate-900 text-green-400 font-mono text-sm p-4 rounded-lg overflow-x-auto">
                    <code>Authorization: Bearer YOUR_API_KEY</code>
                  </pre>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="absolute top-2 right-2"
                    onClick={() => copyToClipboard('Authorization: Bearer YOUR_API_KEY', 'auth')}
                  >
                    {copiedCode === 'auth' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  </Button>
                </div>
                <div className="bg-blue-50 p-4 rounded-lg">
                  <p className="text-blue-800 text-sm">
                    <strong>Note:</strong> Keep your API key secure and never expose it in client-side code.
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Endpoints */}
            <Card id="endpoints">
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Globe className="w-5 h-5 mr-2" />
                  API Endpoints
                </CardTitle>
                <CardDescription>
                  Complete list of available API endpoints
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {endpoints.map((endpoint, index) => (
                  <div key={index} className="border border-slate-200 rounded-lg p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center space-x-3">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          endpoint.method === 'POST' 
                            ? 'bg-green-100 text-green-800' 
                            : 'bg-blue-100 text-blue-800'
                        }`}>
                          {endpoint.method}
                        </span>
                        <code className="text-slate-900 font-mono">{endpoint.path}</code>
                      </div>
                    </div>
                    <p className="text-slate-600 mb-4">{endpoint.description}</p>
                    <div className="relative">
                      <pre className="bg-slate-900 text-green-400 font-mono text-sm p-4 rounded-lg overflow-x-auto">
                        <code>{endpoint.example}</code>
                      </pre>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="absolute top-2 right-2"
                        onClick={() => copyToClipboard(endpoint.example, `endpoint-${index}`)}
                      >
                        {copiedCode === `endpoint-${index}` ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                      </Button>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* SDKs */}
            <Card id="sdks">
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Cpu className="w-5 h-5 mr-2" />
                  SDKs & Libraries
                </CardTitle>
                <CardDescription>
                  Official SDKs for popular programming languages
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="border border-slate-200 rounded-lg p-6">
                    <h3 className="font-semibold text-slate-900 mb-2">Python SDK</h3>
                    <p className="text-slate-600 mb-4">Official Python client for Circuit.AI API</p>
                    <div className="space-y-2">
                      <code className="block bg-slate-100 p-2 rounded text-sm">pip install circuit-ai</code>
                      <Button size="sm" variant="outline">
                        <ExternalLink className="w-4 h-4 mr-2" />
                        View on PyPI
                      </Button>
                    </div>
                  </div>
                  
                  <div className="border border-slate-200 rounded-lg p-6">
                    <h3 className="font-semibold text-slate-900 mb-2">JavaScript SDK</h3>
                    <p className="text-slate-600 mb-4">Official JavaScript/Node.js client</p>
                    <div className="space-y-2">
                      <code className="block bg-slate-100 p-2 rounded text-sm">npm install circuit-ai-sdk</code>
                      <Button size="sm" variant="outline">
                        <ExternalLink className="w-4 h-4 mr-2" />
                        View on NPM
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Rate Limits */}
            <Card id="rate-limits">
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Zap className="w-5 h-5 mr-2" />
                  Rate Limits
                </CardTitle>
                <CardDescription>
                  API usage limits and pricing tiers
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="border border-slate-200 rounded-lg p-6 text-center">
                    <h3 className="font-semibold text-slate-900 mb-2">Free Tier</h3>
                    <p className="text-3xl font-bold text-blue-600 mb-2">50</p>
                    <p className="text-slate-600 text-sm">requests/month</p>
                    <p className="text-slate-500 text-xs mt-2">No SLA</p>
                  </div>
                  
                  <div className="border border-blue-200 rounded-lg p-6 text-center bg-blue-50">
                    <h3 className="font-semibold text-slate-900 mb-2">Pro Tier</h3>
                    <p className="text-3xl font-bold text-blue-600 mb-2">$0.10</p>
                    <p className="text-slate-600 text-sm">per request</p>
                    <p className="text-slate-500 text-xs mt-2">99.9% SLA</p>
                  </div>
                  
                  <div className="border border-slate-200 rounded-lg p-6 text-center">
                    <h3 className="font-semibold text-slate-900 mb-2">Enterprise</h3>
                    <p className="text-3xl font-bold text-blue-600 mb-2">Custom</p>
                    <p className="text-slate-600 text-sm">volume pricing</p>
                    <p className="text-slate-500 text-xs mt-2">Dedicated support</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Error Handling */}
            <Card id="errors">
              <CardHeader>
                <CardTitle>Error Handling</CardTitle>
                <CardDescription>
                  Standard HTTP status codes and error response format
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  <div className="flex items-center space-x-3">
                    <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs font-medium">400</span>
                    <span className="text-slate-900">Bad Request - Invalid parameters</span>
                  </div>
                  <div className="flex items-center space-x-3">
                    <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs font-medium">401</span>
                    <span className="text-slate-900">Unauthorized - Invalid API key</span>
                  </div>
                  <div className="flex items-center space-x-3">
                    <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs font-medium">429</span>
                    <span className="text-slate-900">Too Many Requests - Rate limit exceeded</span>
                  </div>
                  <div className="flex items-center space-x-3">
                    <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs font-medium">500</span>
                    <span className="text-slate-900">Internal Server Error</span>
                  </div>
                </div>
                
                <div className="bg-slate-50 p-4 rounded-lg">
                  <h4 className="font-medium text-slate-900 mb-2">Error Response Format</h4>
                  <pre className="bg-slate-900 text-red-400 font-mono text-sm p-4 rounded-lg overflow-x-auto">
                    <code>{`{
  "error": {
    "code": "INVALID_API_KEY",
    "message": "The provided API key is invalid",
    "details": "Please check your API key and try again"
  }
}`}</code>
                  </pre>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
