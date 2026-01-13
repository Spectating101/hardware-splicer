"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  Search, 
  Filter, 
  Clock, 
  DollarSign, 
  BookOpen, 
  Star,
  Eye,
  Download,
  Target,
  Users,
  Award,
  Zap,
  Cpu,
  Lightbulb
} from "lucide-react";

interface Project {
  id: string;
  name: string;
  description: string;
  difficulty: string;
  time_estimate: string;
  components_needed: string[];
  educational_value: string;
  market_value: number;
  skills_learned: string[];
  image?: string;
  color: string;
}

const projects: Project[] = [
  {
    id: "weather_station",
    name: "Arduino Weather Station",
    description: "Monitor temperature, humidity, and pressure with real-time data logging",
    difficulty: "beginner",
    time_estimate: "2-4 hours",
    components_needed: ["microcontroller", "sensor", "display"],
    educational_value: "high",
    market_value: 15.00,
    skills_learned: ["Arduino programming", "sensor interfacing", "data logging"],
    color: "from-blue-500 to-cyan-600"
  },
  {
    id: "audio_amplifier",
    name: "Simple Audio Amplifier",
    description: "Build a basic audio amplifier for speakers or headphones",
    difficulty: "intermediate",
    time_estimate: "4-6 hours",
    components_needed: ["op_amp", "capacitor", "speaker"],
    educational_value: "high",
    market_value: 25.00,
    skills_learned: ["analog electronics", "audio circuits", "signal processing"],
    color: "from-green-500 to-emerald-600"
  },
  {
    id: "led_controller",
    name: "LED Pattern Controller",
    description: "Create programmable LED patterns and animations",
    difficulty: "beginner",
    time_estimate: "1-2 hours",
    components_needed: ["microcontroller", "led", "resistor"],
    educational_value: "medium",
    market_value: 8.00,
    skills_learned: ["digital output", "timing control", "pattern programming"],
    color: "from-purple-500 to-pink-600"
  },
  {
    id: "power_supply",
    name: "Variable Power Supply",
    description: "Build an adjustable voltage power supply for electronics projects",
    difficulty: "intermediate",
    time_estimate: "6-8 hours",
    components_needed: ["transformer", "regulator", "capacitor"],
    educational_value: "high",
    market_value: 35.00,
    skills_learned: ["power electronics", "voltage regulation", "safety practices"],
    color: "from-orange-500 to-red-600"
  },
  {
    id: "data_logger",
    name: "Environmental Data Logger",
    description: "Create a device to log environmental data over time",
    difficulty: "intermediate",
    time_estimate: "4-6 hours",
    components_needed: ["microcontroller", "sensor", "memory"],
    educational_value: "high",
    market_value: 20.00,
    skills_learned: ["data acquisition", "storage systems", "time-series analysis"],
    color: "from-indigo-500 to-purple-600"
  }
];

export default function ProjectsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [filterDifficulty, setFilterDifficulty] = useState("all");
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);

  const filteredProjects = projects.filter(project => {
    const matchesSearch = project.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         project.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesDifficulty = filterDifficulty === "all" || project.difficulty === filterDifficulty;
    
    return matchesSearch && matchesDifficulty;
  });

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case "beginner": return "text-green-600 bg-green-100";
      case "intermediate": return "text-yellow-600 bg-yellow-100";
      case "advanced": return "text-red-600 bg-red-100";
      default: return "text-gray-600 bg-gray-100";
    }
  };

  const getDifficultyIcon = (difficulty: string) => {
    switch (difficulty) {
      case "beginner": return <Star className="w-4 h-4" />;
      case "intermediate": return <Target className="w-4 h-4" />;
      case "advanced": return <Award className="w-4 h-4" />;
      default: return <Star className="w-4 h-4" />;
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">Project Templates</h1>
        <p className="text-xl text-gray-600">
          Educational electronics projects using salvaged components
        </p>
      </div>

      {/* Search and Filter */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <input
            type="text"
            placeholder="Search projects..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <select
          value={filterDifficulty}
          onChange={(e) => setFilterDifficulty(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-md"
        >
          <option value="all">All Difficulties</option>
          <option value="beginner">Beginner</option>
          <option value="intermediate">Intermediate</option>
          <option value="advanced">Advanced</option>
        </select>
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* Project Grid */}
        <div className="lg:col-span-2">
          <div className="grid md:grid-cols-2 gap-6">
            {filteredProjects.map((project) => (
              <Card 
                key={project.id} 
                className="card-hover cursor-pointer"
                onClick={() => setSelectedProject(project)}
              >
                <CardHeader>
                  <div className="flex items-center justify-between mb-4">
                    <div className={`w-12 h-12 bg-gradient-to-r ${project.color} rounded-lg flex items-center justify-center`}>
                      <Cpu className="w-6 h-6 text-white" />
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-green-600">
                        ${project.market_value}
                      </div>
                      <div className="text-sm text-gray-600">Market Value</div>
                    </div>
                  </div>
                  <CardTitle>{project.name}</CardTitle>
                  <CardDescription>{project.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Difficulty:</span>
                      <span className={`px-2 py-1 rounded-full text-xs flex items-center gap-1 ${getDifficultyColor(project.difficulty)}`}>
                        {getDifficultyIcon(project.difficulty)}
                        {project.difficulty}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Time Estimate:</span>
                      <span className="text-sm font-medium">{project.time_estimate}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Educational Value:</span>
                      <span className={`px-2 py-1 rounded-full text-xs ${getDifficultyColor(project.educational_value)}`}>
                        {project.educational_value}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-3">
                      {project.components_needed.slice(0, 3).map((component, index) => (
                        <span
                          key={index}
                          className="px-2 py-1 bg-indigo-100 text-indigo-800 rounded-full text-xs"
                        >
                          {component.replace('_', ' ')}
                        </span>
                      ))}
                      {project.components_needed.length > 3 && (
                        <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded-full text-xs">
                          +{project.components_needed.length - 3} more
                        </span>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Project Details Sidebar */}
        <div className="lg:col-span-1">
          {selectedProject ? (
            <Card className="sticky top-8">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className={`w-12 h-12 bg-gradient-to-r ${selectedProject.color} rounded-lg flex items-center justify-center`}>
                    <Cpu className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <CardTitle>{selectedProject.name}</CardTitle>
                    <CardDescription>Project Details</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <h4 className="font-semibold mb-2">Description</h4>
                  <p className="text-sm text-gray-600">{selectedProject.description}</p>
                </div>

                <div>
                  <h4 className="font-semibold mb-2">Project Info</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm">Difficulty:</span>
                      <span className={`px-2 py-1 rounded-full text-xs flex items-center gap-1 ${getDifficultyColor(selectedProject.difficulty)}`}>
                        {getDifficultyIcon(selectedProject.difficulty)}
                        {selectedProject.difficulty}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Time Estimate:</span>
                      <span className="text-sm font-medium">{selectedProject.time_estimate}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Market Value:</span>
                      <span className="text-sm font-bold text-green-600">${selectedProject.market_value}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Educational Value:</span>
                      <span className={`px-2 py-1 rounded-full text-xs ${getDifficultyColor(selectedProject.educational_value)}`}>
                        {selectedProject.educational_value}
                      </span>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold mb-2">Required Components</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedProject.components_needed.map((component, index) => (
                      <span
                        key={index}
                        className="px-3 py-1 bg-indigo-100 text-indigo-800 rounded-full text-sm"
                      >
                        {component.replace('_', ' ')}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold mb-2">Skills You'll Learn</h4>
                  <div className="space-y-2">
                    {selectedProject.skills_learned.map((skill, index) => (
                      <div key={index} className="flex items-center gap-2 text-sm text-gray-600">
                        <Lightbulb className="w-4 h-4 text-yellow-500" />
                        <span>{skill}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex gap-2">
                  <Button variant="gradient" className="flex-1">
                    <Eye className="w-4 h-4 mr-2" />
                    Start Project
                  </Button>
                  <Button variant="outline" className="flex-1">
                    <Download className="w-4 h-4 mr-2" />
                    Download Guide
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Project Details</CardTitle>
                <CardDescription>Select a project to view details</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-12 text-gray-500">
                  <Target className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>Click on a project to see detailed information</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Statistics */}
      <Card>
        <CardHeader>
          <CardTitle>Project Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-4 gap-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-indigo-600">{projects.length}</div>
              <div className="text-sm text-gray-600">Total Projects</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-green-600">
                ${projects.reduce((sum, p) => sum + p.market_value, 0).toFixed(0)}
              </div>
              <div className="text-sm text-gray-600">Total Value</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-blue-600">
                {projects.filter(p => p.difficulty === "beginner").length}
              </div>
              <div className="text-sm text-gray-600">Beginner Projects</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-purple-600">
                {projects.filter(p => p.educational_value === "high").length}
              </div>
              <div className="text-sm text-gray-600">High Educational Value</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
