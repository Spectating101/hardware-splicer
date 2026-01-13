"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { 
  TrendingUp, 
  CircuitBoard, 
  Users, 
  Award, 
  Clock, 
  Eye,
  Download,
  Activity,
  BarChart3,
  PieChart,
  Calendar,
  ArrowUpRight,
  ArrowDownRight
} from "lucide-react";

export default function DashboardPage() {
  // Mock data - in production this would come from API
  const stats = {
    totalAnalyses: 24,
    componentsIdentified: 156,
    projectsCreated: 8,
    totalValue: 45.67,
    recentActivity: [
      { id: 1, type: "analysis", description: "PCB Analysis #24", time: "2 hours ago", value: "$2.92" },
      { id: 2, type: "project", description: "Weather Station Project", time: "1 day ago", value: "$15.00" },
      { id: 3, type: "analysis", description: "PCB Analysis #23", time: "2 days ago", value: "$1.25" },
      { id: 4, type: "export", description: "Exported Analysis #22", time: "3 days ago", value: "PDF" },
    ],
    componentBreakdown: [
      { type: "IC Chips", count: 12, value: 6.00 },
      { type: "Capacitors", count: 45, value: 11.25 },
      { type: "Resistors", count: 67, value: 0.67 },
      { type: "Connectors", count: 23, value: 2.30 },
      { type: "Transformers", count: 5, value: 10.00 },
      { type: "Diodes", count: 4, value: 0.20 },
    ],
    monthlyTrends: [
      { month: "Jan", analyses: 5, value: 12.50 },
      { month: "Feb", analyses: 8, value: 18.75 },
      { month: "Mar", analyses: 12, value: 28.90 },
      { month: "Apr", analyses: 15, value: 35.20 },
      { month: "May", analyses: 18, value: 42.10 },
      { month: "Jun", analyses: 24, value: 45.67 },
    ]
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold mb-2">Dashboard</h1>
          <p className="text-xl text-gray-600">
            Your Circuit.AI analytics and activity overview
          </p>
        </div>
        <Button variant="gradient">
          <Download className="w-4 h-4 mr-2" />
          Export Report
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="card-hover">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Analyses</CardTitle>
            <CircuitBoard className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalAnalyses}</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-green-600 flex items-center">
                <ArrowUpRight className="w-3 h-3 mr-1" />
                +20% from last month
              </span>
            </p>
          </CardContent>
        </Card>

        <Card className="card-hover">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Components Identified</CardTitle>
            <Eye className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.componentsIdentified}</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-green-600 flex items-center">
                <ArrowUpRight className="w-3 h-3 mr-1" />
                +15% from last month
              </span>
            </p>
          </CardContent>
        </Card>

        <Card className="card-hover">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Projects Created</CardTitle>
            <Award className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.projectsCreated}</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-green-600 flex items-center">
                <ArrowUpRight className="w-3 h-3 mr-1" />
                +33% from last month
              </span>
            </p>
          </CardContent>
        </Card>

        <Card className="card-hover">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Value Generated</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${stats.totalValue}</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-green-600 flex items-center">
                <ArrowUpRight className="w-3 h-3 mr-1" />
                +25% from last month
              </span>
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* Recent Activity */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="w-5 h-5" />
                Recent Activity
              </CardTitle>
              <CardDescription>
                Your latest analyses, projects, and exports
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {stats.recentActivity.map((activity) => (
                  <div key={activity.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                        {activity.type === "analysis" && <CircuitBoard className="w-5 h-5 text-white" />}
                        {activity.type === "project" && <Award className="w-5 h-5 text-white" />}
                        {activity.type === "export" && <Download className="w-5 h-5 text-white" />}
                      </div>
                      <div>
                        <div className="font-medium">{activity.description}</div>
                        <div className="text-sm text-gray-600">{activity.time}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-medium">{activity.value}</div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Component Breakdown */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PieChart className="w-5 h-5" />
                Component Breakdown
              </CardTitle>
              <CardDescription>
                Components identified by type
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {stats.componentBreakdown.map((component, index) => (
                  <div key={index} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-indigo-500"></div>
                      <span className="text-sm">{component.type}</span>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-medium">{component.count}</div>
                      <div className="text-xs text-gray-600">${component.value}</div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Monthly Trends */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
            Monthly Trends
          </CardTitle>
          <CardDescription>
            Analysis volume and value over time
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 gap-8">
            {/* Analysis Volume */}
            <div>
              <h4 className="font-semibold mb-4">Analysis Volume</h4>
              <div className="space-y-3">
                {stats.monthlyTrends.map((trend, index) => (
                  <div key={index} className="flex items-center justify-between">
                    <span className="text-sm">{trend.month}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-32 bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-gradient-to-r from-indigo-500 to-purple-600 h-2 rounded-full"
                          style={{ width: `${(trend.analyses / 24) * 100}%` }}
                        ></div>
                      </div>
                      <span className="text-sm font-medium w-8">{trend.analyses}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Value Generated */}
            <div>
              <h4 className="font-semibold mb-4">Value Generated</h4>
              <div className="space-y-3">
                {stats.monthlyTrends.map((trend, index) => (
                  <div key={index} className="flex items-center justify-between">
                    <span className="text-sm">{trend.month}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-32 bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-gradient-to-r from-green-500 to-emerald-600 h-2 rounded-full"
                          style={{ width: `${(trend.value / 50) * 100}%` }}
                        ></div>
                      </div>
                      <span className="text-sm font-medium w-12">${trend.value}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>
            Common tasks and shortcuts
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-3 gap-4">
            <Button variant="outline" className="h-20 flex flex-col gap-2">
              <CircuitBoard className="w-6 h-6" />
              <span>New Analysis</span>
            </Button>
            <Button variant="outline" className="h-20 flex flex-col gap-2">
              <Award className="w-6 h-6" />
              <span>Start Project</span>
            </Button>
            <Button variant="outline" className="h-20 flex flex-col gap-2">
              <Download className="w-6 h-6" />
              <span>Export Data</span>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
