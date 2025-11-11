"use client";

import { useState, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { 
  Target, 
  Clock, 
  DollarSign, 
  Star, 
  Filter, 
  ExternalLink,
  BookOpen,
  Zap,
  Users,
  TrendingUp
} from 'lucide-react';
import { ProjectRecommendation } from '@/types/analysis';

interface ProjectRecommendationsProps {
  recommendations: ProjectRecommendation[];
  className?: string;
}

export function ProjectRecommendations({ recommendations, className }: ProjectRecommendationsProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [difficultyFilter, setDifficultyFilter] = useState<string>('all');
  const [costFilter, setCostFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'score' | 'cost' | 'time'>('score');

  const filteredAndSortedRecommendations = useMemo(() => {
    let filtered = recommendations.filter(project => {
      const matchesSearch = project.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           project.description.toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesDifficulty = difficultyFilter === 'all' || project.difficulty === difficultyFilter;
      
      const matchesCost = costFilter === 'all' || 
                         (costFilter === 'low' && project.estimated_cost <= 10) ||
                         (costFilter === 'medium' && project.estimated_cost > 10 && project.estimated_cost <= 25) ||
                         (costFilter === 'high' && project.estimated_cost > 25);
      
      return matchesSearch && matchesDifficulty && matchesCost;
    });

    // Sort recommendations
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'score':
          return b.score - a.score;
        case 'cost':
          return a.estimated_cost - b.estimated_cost;
        case 'time':
          return parseInt(a.time_required) - parseInt(b.time_required);
        default:
          return 0;
      }
    });

    return filtered;
  }, [recommendations, searchTerm, difficultyFilter, costFilter, sortBy]);

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'beginner': return 'text-green-600 bg-green-100';
      case 'intermediate': return 'text-yellow-600 bg-yellow-100';
      case 'advanced': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getCostCategory = (cost: number) => {
    if (cost <= 10) return 'Low';
    if (cost <= 25) return 'Medium';
    return 'High';
  };

  const getCostColor = (cost: number) => {
    if (cost <= 10) return 'text-green-600';
    if (cost <= 25) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-r from-green-500 to-emerald-600 rounded-lg flex items-center justify-center">
            <Target className="w-5 h-5 text-white" />
          </div>
          <div>
            <CardTitle>Project Recommendations</CardTitle>
            <CardDescription>
              {filteredAndSortedRecommendations.length} projects found based on your components
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Filters */}
        <div className="space-y-4">
          <div className="flex gap-4">
            <div className="flex-1">
              <Input
                placeholder="Search projects..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full"
              />
            </div>
            <select
              value={difficultyFilter}
              onChange={(e) => setDifficultyFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="all">All Difficulties</option>
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
            <select
              value={costFilter}
              onChange={(e) => setCostFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="all">All Costs</option>
              <option value="low">Low ($0-10)</option>
              <option value="medium">Medium ($11-25)</option>
              <option value="high">High ($25+)</option>
            </select>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as 'score' | 'cost' | 'time')}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="score">Sort by Score</option>
              <option value="cost">Sort by Cost</option>
              <option value="time">Sort by Time</option>
            </select>
          </div>
        </div>

        {/* Project Grid */}
        <div className="grid gap-6">
          {filteredAndSortedRecommendations.map((project) => (
            <Card key={project.id} className="hover:shadow-lg transition-shadow">
              <CardContent className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-xl font-semibold">{project.name}</h3>
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getDifficultyColor(project.difficulty)}`}>
                        {project.difficulty}
                      </span>
                      <div className="flex items-center gap-1">
                        <Star className="w-4 h-4 text-yellow-500 fill-current" />
                        <span className={`text-sm font-medium ${getScoreColor(project.score)}`}>
                          {project.score}%
                        </span>
                      </div>
                    </div>
                    <p className="text-gray-600 mb-4">{project.description}</p>
                  </div>
                </div>

                {/* Project Stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                  <div className="text-center p-3 bg-blue-50 rounded-lg">
                    <div className="flex items-center justify-center mb-1">
                      <DollarSign className="w-4 h-4 text-blue-600" />
                    </div>
                    <div className={`text-lg font-bold ${getCostColor(project.estimated_cost)}`}>
                      ${project.estimated_cost}
                    </div>
                    <div className="text-xs text-gray-600">
                      {getCostCategory(project.estimated_cost)} Cost
                    </div>
                  </div>
                  
                  <div className="text-center p-3 bg-green-50 rounded-lg">
                    <div className="flex items-center justify-center mb-1">
                      <Clock className="w-4 h-4 text-green-600" />
                    </div>
                    <div className="text-lg font-bold text-green-600">
                      {project.time_required}
                    </div>
                    <div className="text-xs text-gray-600">Time Required</div>
                  </div>
                  
                  <div className="text-center p-3 bg-purple-50 rounded-lg">
                    <div className="flex items-center justify-center mb-1">
                      <BookOpen className="w-4 h-4 text-purple-600" />
                    </div>
                    <div className="text-lg font-bold text-purple-600">
                      {project.components_needed.length}
                    </div>
                    <div className="text-xs text-gray-600">Components</div>
                  </div>
                  
                  <div className="text-center p-3 bg-orange-50 rounded-lg">
                    <div className="flex items-center justify-center mb-1">
                      <TrendingUp className="w-4 h-4 text-orange-600" />
                    </div>
                    <div className="text-lg font-bold text-orange-600">
                      {project.skills_developed.length}
                    </div>
                    <div className="text-xs text-gray-600">Skills</div>
                  </div>
                </div>

                {/* Skills and Components */}
                <div className="space-y-3 mb-4">
                  <div>
                    <h4 className="font-medium text-sm text-gray-700 mb-2">Components Needed:</h4>
                    <div className="flex flex-wrap gap-2">
                      {project.components_needed.map((component, index) => (
                        <span
                          key={index}
                          className="px-2 py-1 bg-indigo-100 text-indigo-800 rounded-full text-xs"
                        >
                          {component.replace('_', ' ')}
                        </span>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="font-medium text-sm text-gray-700 mb-2">Skills You'll Develop:</h4>
                    <div className="flex flex-wrap gap-2">
                      {project.skills_developed.map((skill, index) => (
                        <span
                          key={index}
                          className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs"
                        >
                          {skill.replace('_', ' ')}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-3">
                  <Button variant="gradient" className="flex-1">
                    <BookOpen className="w-4 h-4 mr-2" />
                    Start Project
                  </Button>
                  {project.tutorial_url && (
                    <Button variant="outline">
                      <ExternalLink className="w-4 h-4 mr-2" />
                      Tutorial
                    </Button>
                  )}
                  <Button variant="outline">
                    <Star className="w-4 h-4 mr-2" />
                    Save
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {filteredAndSortedRecommendations.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <Target className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium mb-2">No projects found</p>
            <p className="text-sm">Try adjusting your filters or search terms</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
