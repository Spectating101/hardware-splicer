'use client';

import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  TrendingUp, 
  Users, 
  Activity, 
  Target,
  BarChart3,
  PieChart,
  LineChart
} from 'lucide-react';

interface AnalyticsDashboardProps {
  className?: string;
}

export function AnalyticsDashboard({ className }: AnalyticsDashboardProps) {
  const stats = [
    {
      title: "Total Analyses",
      value: "1,234",
      change: "+12%",
      icon: Activity,
      color: "text-blue-600"
    },
    {
      title: "Active Users",
      value: "567",
      change: "+8%",
      icon: Users,
      color: "text-green-600"
    },
    {
      title: "Components Detected",
      value: "8,901",
      change: "+15%",
      icon: Target,
      color: "text-purple-600"
    },
    {
      title: "Success Rate",
      value: "94.2%",
      change: "+2%",
      icon: TrendingUp,
      color: "text-orange-600"
    }
  ];

  const recentAnalyses = [
    { id: 1, type: "Arduino Board", components: 12, value: "$15.50", time: "2 min ago" },
    { id: 2, type: "Raspberry Pi", components: 8, value: "$45.00", time: "5 min ago" },
    { id: 3, type: "Sensor Module", components: 5, value: "$8.25", time: "8 min ago" },
    { id: 4, type: "Power Supply", components: 15, value: "$22.75", time: "12 min ago" }
  ];

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, index) => (
          <Card key={index} className="hover:shadow-lg transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                {stat.title}
              </CardTitle>
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              <p className="text-xs text-green-600 flex items-center">
                <TrendingUp className="h-3 w-3 mr-1" />
                {stat.change} from last month
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <BarChart3 className="h-5 w-5 mr-2" />
              Analysis Trends
            </CardTitle>
            <CardDescription>
              Daily analysis volume over the last 30 days
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64 flex items-center justify-center bg-gray-50 rounded-lg">
              <div className="text-center text-gray-500">
                <BarChart3 className="h-12 w-12 mx-auto mb-2 opacity-50" />
                <p>Chart visualization would go here</p>
                <p className="text-sm">Integration with charting library needed</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <PieChart className="h-5 w-5 mr-2" />
              Component Distribution
            </CardTitle>
            <CardDescription>
              Most commonly detected components
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64 flex items-center justify-center bg-gray-50 rounded-lg">
              <div className="text-center text-gray-500">
                <PieChart className="h-12 w-12 mx-auto mb-2 opacity-50" />
                <p>Pie chart visualization would go here</p>
                <p className="text-sm">Component type breakdown</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Analyses */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Activity className="h-5 w-5 mr-2" />
            Recent Analyses
          </CardTitle>
          <CardDescription>
            Latest PCB analyses performed by users
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {recentAnalyses.map((analysis) => (
              <div key={analysis.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center space-x-4">
                  <div className="w-10 h-10 bg-gradient-to-r from-blue-500 to-purple-500 rounded-lg flex items-center justify-center">
                    <Target className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <p className="font-medium">{analysis.type}</p>
                    <p className="text-sm text-gray-600">{analysis.components} components detected</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-bold text-green-600">{analysis.value}</p>
                  <p className="text-sm text-gray-500">{analysis.time}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}