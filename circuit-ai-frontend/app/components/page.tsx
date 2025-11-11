"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { 
  Search, 
  Filter, 
  Cpu, 
  Zap, 
  BookOpen, 
  DollarSign, 
  Star,
  Eye,
  Download,
  Info
} from "lucide-react";

interface Component {
  type: string;
  description: string;
  capabilities: string[];
  reuse_value: string;
  market_value: number;
  educational_value: string;
  icon: string;
  color: string;
}

const components: Component[] = [
  {
    type: "ic_chip",
    description: "Integrated Circuit chips for digital and analog processing",
    capabilities: ["arduino_projects", "iot_devices", "educational_electronics", "signal_processing"],
    reuse_value: "high",
    market_value: 0.50,
    educational_value: "high",
    icon: "Cpu",
    color: "from-blue-500 to-cyan-600"
  },
  {
    type: "capacitor",
    description: "Capacitive components for energy storage and filtering",
    capabilities: ["power_filtering", "audio_circuits", "voltage_regulation", "timing_circuits"],
    reuse_value: "medium",
    market_value: 0.25,
    educational_value: "medium",
    icon: "Zap",
    color: "from-green-500 to-emerald-600"
  },
  {
    type: "resistor",
    description: "Resistive components for current limiting and voltage division",
    capabilities: ["current_limiting", "voltage_division", "biasing", "load_simulation"],
    reuse_value: "low",
    market_value: 0.01,
    educational_value: "high",
    icon: "Zap",
    color: "from-orange-500 to-red-600"
  },
  {
    type: "connector",
    description: "Interface connectors for signal and power transmission",
    capabilities: ["signal_transmission", "power_distribution", "modular_design", "data_communication"],
    reuse_value: "high",
    market_value: 0.10,
    educational_value: "medium",
    icon: "Zap",
    color: "from-purple-500 to-pink-600"
  },
  {
    type: "transformer",
    description: "Power conversion components for voltage transformation",
    capabilities: ["voltage_conversion", "isolation", "power_distribution", "signal_coupling"],
    reuse_value: "high",
    market_value: 2.00,
    educational_value: "high",
    icon: "Zap",
    color: "from-indigo-500 to-purple-600"
  },
  {
    type: "diode",
    description: "Semiconductor components for rectification and protection",
    capabilities: ["rectification", "voltage_regulation", "signal_detection", "protection"],
    reuse_value: "medium",
    market_value: 0.05,
    educational_value: "medium",
    icon: "Zap",
    color: "from-yellow-500 to-orange-600"
  }
];

export default function ComponentsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [filterValue, setFilterValue] = useState("all");
  const [selectedComponent, setSelectedComponent] = useState<Component | null>(null);

  const filteredComponents = components.filter(component => {
    const matchesSearch = component.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         component.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filterValue === "all" || 
                         (filterValue === "high_value" && component.market_value > 1) ||
                         (filterValue === "high_education" && component.educational_value === "high") ||
                         (filterValue === "high_reuse" && component.reuse_value === "high");
    
    return matchesSearch && matchesFilter;
  });

  const getValueColor = (value: string) => {
    switch (value) {
      case "high": return "text-green-600 bg-green-100";
      case "medium": return "text-yellow-600 bg-yellow-100";
      case "low": return "text-red-600 bg-red-100";
      default: return "text-gray-600 bg-gray-100";
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">Component Library</h1>
        <p className="text-xl text-gray-600">
          Explore electronic components and their educational potential
        </p>
      </div>

      {/* Search and Filter */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <Input
            placeholder="Search components..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        <select
          value={filterValue}
          onChange={(e) => setFilterValue(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-md"
        >
          <option value="all">All Components</option>
          <option value="high_value">High Value ($1+)</option>
          <option value="high_education">High Educational Value</option>
          <option value="high_reuse">High Reuse Potential</option>
        </select>
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* Component Grid */}
        <div className="lg:col-span-2">
          <div className="grid md:grid-cols-2 gap-6">
            {filteredComponents.map((component) => (
              <Card 
                key={component.type} 
                className="card-hover cursor-pointer"
                onClick={() => setSelectedComponent(component)}
              >
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className={`w-12 h-12 bg-gradient-to-r ${component.color} rounded-lg flex items-center justify-center`}>
                      <Cpu className="w-6 h-6 text-white" />
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-green-600">
                        ${component.market_value}
                      </div>
                      <div className="text-sm text-gray-600">Market Value</div>
                    </div>
                  </div>
                  <CardTitle className="capitalize">{component.type.replace('_', ' ')}</CardTitle>
                  <CardDescription>{component.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <span>Reuse Value:</span>
                      <span className={`px-2 py-1 rounded-full text-xs ${getValueColor(component.reuse_value)}`}>
                        {component.reuse_value}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span>Educational Value:</span>
                      <span className={`px-2 py-1 rounded-full text-xs ${getValueColor(component.educational_value)}`}>
                        {component.educational_value}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-3">
                      {component.capabilities.slice(0, 3).map((capability, index) => (
                        <span
                          key={index}
                          className="px-2 py-1 bg-indigo-100 text-indigo-800 rounded-full text-xs"
                        >
                          {capability.replace('_', ' ')}
                        </span>
                      ))}
                      {component.capabilities.length > 3 && (
                        <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded-full text-xs">
                          +{component.capabilities.length - 3} more
                        </span>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Component Details Sidebar */}
        <div className="lg:col-span-1">
          {selectedComponent ? (
            <Card className="sticky top-8">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className={`w-12 h-12 bg-gradient-to-r ${selectedComponent.color} rounded-lg flex items-center justify-center`}>
                    <Cpu className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <CardTitle className="capitalize">{selectedComponent.type.replace('_', ' ')}</CardTitle>
                    <CardDescription>Component Details</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <h4 className="font-semibold mb-2">Description</h4>
                  <p className="text-sm text-gray-600">{selectedComponent.description}</p>
                </div>

                <div>
                  <h4 className="font-semibold mb-2">Market Value</h4>
                  <div className="text-2xl font-bold text-green-600">${selectedComponent.market_value}</div>
                </div>

                <div>
                  <h4 className="font-semibold mb-2">Value Assessment</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm">Reuse Value:</span>
                      <span className={`px-2 py-1 rounded-full text-xs ${getValueColor(selectedComponent.reuse_value)}`}>
                        {selectedComponent.reuse_value}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Educational Value:</span>
                      <span className={`px-2 py-1 rounded-full text-xs ${getValueColor(selectedComponent.educational_value)}`}>
                        {selectedComponent.educational_value}
                      </span>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold mb-2">Capabilities</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedComponent.capabilities.map((capability, index) => (
                      <span
                        key={index}
                        className="px-3 py-1 bg-indigo-100 text-indigo-800 rounded-full text-sm"
                      >
                        {capability.replace('_', ' ')}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold mb-2">Educational Applications</h4>
                  <div className="space-y-2 text-sm text-gray-600">
                    <div className="flex items-center gap-2">
                      <BookOpen className="w-4 h-4" />
                      <span>Basic electronics principles</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Zap className="w-4 h-4" />
                      <span>Circuit design and analysis</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <DollarSign className="w-4 h-4" />
                      <span>Component value assessment</span>
                    </div>
                  </div>
                </div>

                <div className="flex gap-2">
                  <Button variant="outline" className="flex-1">
                    <Eye className="w-4 h-4 mr-2" />
                    View Projects
                  </Button>
                  <Button variant="outline" className="flex-1">
                    <Download className="w-4 h-4 mr-2" />
                    Export Info
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Component Details</CardTitle>
                <CardDescription>Select a component to view details</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-12 text-gray-500">
                  <Info className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>Click on a component to see detailed information</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Statistics */}
      <Card>
        <CardHeader>
          <CardTitle>Component Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-4 gap-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-indigo-600">{components.length}</div>
              <div className="text-sm text-gray-600">Total Components</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-green-600">
                ${components.reduce((sum, c) => sum + c.market_value, 0).toFixed(2)}
              </div>
              <div className="text-sm text-gray-600">Total Value</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-blue-600">
                {components.filter(c => c.educational_value === "high").length}
              </div>
              <div className="text-sm text-gray-600">High Educational Value</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-purple-600">
                {components.filter(c => c.reuse_value === "high").length}
              </div>
              <div className="text-sm text-gray-600">High Reuse Potential</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
