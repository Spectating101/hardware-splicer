import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  Zap, 
  Eye, 
  Brain, 
  BookOpen, 
  DollarSign, 
  TrendingUp, 
  Cpu, 
  CircuitBoard,
  Upload,
  Target,
  Users,
  Award
} from "lucide-react";

export default function Home() {
  return (
    <div className="space-y-20">
      {/* Hero Section */}
      <section className="text-center py-20">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-5xl md:text-6xl font-bold mb-6">
            Transform{" "}
            <span className="gradient-text">E-Waste</span> into{" "}
            <span className="gradient-text">Educational Opportunities</span>
          </h1>
          <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            AI-powered PCB analysis platform that detects components, analyzes capabilities, 
            and provides project recommendations for educational electronics.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/analyze">
              <Button variant="gradient" size="lg" className="text-lg px-8 py-3">
                <Upload className="w-5 h-5 mr-2" />
                Start Analysis
              </Button>
            </Link>
            <Link href="/demo">
              <Button variant="outline" size="lg" className="text-lg px-8 py-3">
                <Eye className="w-5 h-5 mr-2" />
                View Demo
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold mb-4">How Circuit.AI Works</h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Our AI-powered platform makes electronics education accessible and engaging
          </p>
        </div>
        
        <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          <Card className="card-hover">
            <CardHeader>
              <div className="w-12 h-12 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center mb-4">
                <CircuitBoard className="w-6 h-6 text-white" />
              </div>
              <CardTitle>1. Upload PCB Image</CardTitle>
              <CardDescription>
                Simply upload a photo of any printed circuit board
              </CardDescription>
            </CardHeader>
          </Card>

          <Card className="card-hover">
            <CardHeader>
              <div className="w-12 h-12 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center mb-4">
                <Brain className="w-6 h-6 text-white" />
              </div>
              <CardTitle>2. AI Analysis</CardTitle>
              <CardDescription>
                Our AI detects components and analyzes their capabilities
              </CardDescription>
            </CardHeader>
          </Card>

          <Card className="card-hover">
            <CardHeader>
              <div className="w-12 h-12 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center mb-4">
                <Target className="w-6 h-6 text-white" />
              </div>
              <CardTitle>3. Get Results</CardTitle>
              <CardDescription>
                Receive detailed analysis and project recommendations
              </CardDescription>
            </CardHeader>
          </Card>
        </div>
      </section>

      {/* Value Proposition */}
      <section className="py-20 bg-white/50 rounded-3xl">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4">Why Choose Circuit.AI?</h2>
            <p className="text-xl text-gray-600">
              Professional-grade analysis with educational focus
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-r from-green-500 to-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <Eye className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Component Detection</h3>
              <p className="text-gray-600">Identify IC chips, capacitors, resistors, and more</p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-r from-blue-500 to-cyan-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <DollarSign className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Value Assessment</h3>
              <p className="text-gray-600">Calculate market value of salvaged components</p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-r from-purple-500 to-pink-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <BookOpen className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Educational Insights</h3>
              <p className="text-gray-600">Learn about component capabilities and uses</p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-r from-orange-500 to-red-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <Cpu className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Project Ideas</h3>
              <p className="text-gray-600">Get recommendations for educational projects</p>
            </div>
          </div>
        </div>
      </section>

      {/* Statistics */}
      <section className="py-20">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4">Platform Statistics</h2>
            <p className="text-xl text-gray-600">
              Real-time metrics from our growing community
            </p>
          </div>

          <div className="grid md:grid-cols-4 gap-8">
            <Card className="text-center card-hover">
              <CardContent className="pt-6">
                <div className="w-12 h-12 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center mx-auto mb-4">
                  <CircuitBoard className="w-6 h-6 text-white" />
                </div>
                <div className="text-3xl font-bold text-indigo-600 mb-2">1,234</div>
                <p className="text-gray-600">Components Analyzed</p>
              </CardContent>
            </Card>

            <Card className="text-center card-hover">
              <CardContent className="pt-6">
                <div className="w-12 h-12 bg-gradient-to-r from-green-500 to-emerald-600 rounded-lg flex items-center justify-center mx-auto mb-4">
                  <Users className="w-6 h-6 text-white" />
                </div>
                <div className="text-3xl font-bold text-green-600 mb-2">567</div>
                <p className="text-gray-600">Active Users</p>
              </CardContent>
            </Card>

            <Card className="text-center card-hover">
              <CardContent className="pt-6">
                <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-cyan-600 rounded-lg flex items-center justify-center mx-auto mb-4">
                  <Award className="w-6 h-6 text-white" />
                </div>
                <div className="text-3xl font-bold text-blue-600 mb-2">89</div>
                <p className="text-gray-600">Projects Created</p>
              </CardContent>
            </Card>

            <Card className="text-center card-hover">
              <CardContent className="pt-6">
                <div className="w-12 h-12 bg-gradient-to-r from-purple-500 to-pink-600 rounded-lg flex items-center justify-center mx-auto mb-4">
                  <TrendingUp className="w-6 h-6 text-white" />
                </div>
                <div className="text-3xl font-bold text-purple-600 mb-2">$12,345</div>
                <p className="text-gray-600">Value Generated</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-gradient-to-r from-indigo-600 to-purple-700 rounded-3xl text-white">
        <div className="text-center max-w-4xl mx-auto">
          <h2 className="text-4xl font-bold mb-4">Ready to Transform E-Waste?</h2>
          <p className="text-xl mb-8 opacity-90">
            Join educators, students, and hobbyists in making electronics education more accessible
          </p>
          <Link href="/analyze">
            <Button variant="secondary" size="lg" className="text-lg px-8 py-3">
              <Zap className="w-5 h-5 mr-2" />
              Start Your First Analysis
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
