'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { motion } from 'framer-motion';
import { Check, Zap, Star, Building, ArrowRight } from 'lucide-react';

export default function PricingPage() {
  const [isAnnual, setIsAnnual] = useState(false);

  const plans = [
    {
      name: 'Free',
      description: 'Perfect for getting started',
      price: { monthly: 0, annual: 0 },
      features: [
        '50 API requests/month',
        'Basic component detection',
        'Community support',
        'Standard response time',
        'Basic documentation'
      ],
      limitations: [
        'No SLA guarantee',
        'Limited to 5MB file size',
        'No real-time streaming'
      ],
      buttonText: 'Get Started Free',
      buttonVariant: 'outline' as const,
      popular: false
    },
    {
      name: 'Pro',
      description: 'For growing applications',
      price: { monthly: 99, annual: 990 },
      features: [
        'Unlimited API requests',
        'Advanced AI detection',
        'Real-time WebSocket streaming',
        'Priority support',
        '99.9% SLA guarantee',
        'Up to 50MB file size',
        'Advanced analytics',
        'Custom integrations'
      ],
      limitations: [],
      buttonText: 'Start Pro Trial',
      buttonVariant: 'default' as const,
      popular: true
    },
    {
      name: 'Enterprise',
      description: 'For large-scale deployments',
      price: { monthly: 'Custom', annual: 'Custom' },
      features: [
        'Everything in Pro',
        'Dedicated infrastructure',
        'Custom model training',
        'On-premise deployment',
        '24/7 dedicated support',
        'Custom SLA terms',
        'Volume discounts',
        'White-label options'
      ],
      limitations: [],
      buttonText: 'Contact Sales',
      buttonVariant: 'outline' as const,
      popular: false
    }
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="border-b border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="text-center">
            <h1 className="text-3xl font-bold text-slate-900">Simple, Transparent Pricing</h1>
            <p className="text-slate-600 mt-2">Choose the plan that fits your needs</p>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Billing Toggle */}
        <div className="flex justify-center mb-12">
          <div className="bg-slate-100 p-1 rounded-lg">
            <button
              onClick={() => setIsAnnual(false)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                !isAnnual
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setIsAnnual(true)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                isAnnual
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Annual
              <span className="ml-1 text-xs bg-green-100 text-green-800 px-1.5 py-0.5 rounded">
                Save 17%
              </span>
            </button>
          </div>
        </div>

        {/* Pricing Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {plans.map((plan, index) => (
            <motion.div
              key={plan.name}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: index * 0.1 }}
            >
              <Card className={`relative ${plan.popular ? 'border-blue-500 shadow-lg scale-105' : 'border-slate-200'}`}>
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                    <span className="bg-blue-500 text-white px-3 py-1 rounded-full text-sm font-medium flex items-center">
                      <Star className="w-4 h-4 mr-1" />
                      Most Popular
                    </span>
                  </div>
                )}
                
                <CardHeader className="text-center">
                  <CardTitle className="text-2xl">{plan.name}</CardTitle>
                  <CardDescription>{plan.description}</CardDescription>
                  <div className="mt-4">
                    {typeof plan.price.monthly === 'number' && typeof plan.price.annual === 'number' ? (
                      <div className="flex items-baseline justify-center">
                        <span className="text-4xl font-bold text-slate-900">
                          ${isAnnual ? plan.price.annual / 12 : plan.price.monthly}
                        </span>
                        <span className="text-slate-600 ml-1">
                          /{isAnnual ? 'month' : 'month'}
                        </span>
                      </div>
                    ) : (
                      <div className="text-4xl font-bold text-slate-900">
                        {plan.price.monthly}
                      </div>
                    )}
                    {isAnnual && typeof plan.price.monthly === 'number' && typeof plan.price.annual === 'number' && (
                      <p className="text-sm text-slate-500 mt-1">
                        Billed annually (${plan.price.annual}/year)
                      </p>
                    )}
                  </div>
                </CardHeader>
                
                <CardContent className="space-y-6">
                  <Button 
                    className={`w-full ${plan.popular ? 'bg-blue-600 hover:bg-blue-700' : ''}`}
                    variant={plan.buttonVariant}
                  >
                    {plan.buttonText}
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                  
                  <div className="space-y-3">
                    <h4 className="font-medium text-slate-900">Features included:</h4>
                    <ul className="space-y-2">
                      {plan.features.map((feature, featureIndex) => (
                        <li key={featureIndex} className="flex items-center text-sm text-slate-600">
                          <Check className="w-4 h-4 text-green-500 mr-2 flex-shrink-0" />
                          {feature}
                        </li>
                      ))}
                    </ul>
                  </div>
                  
                  {plan.limitations.length > 0 && (
                    <div className="space-y-3">
                      <h4 className="font-medium text-slate-900">Limitations:</h4>
                      <ul className="space-y-2">
                        {plan.limitations.map((limitation, limitationIndex) => (
                          <li key={limitationIndex} className="flex items-center text-sm text-slate-500">
                            <span className="w-4 h-4 mr-2 flex-shrink-0">•</span>
                            {limitation}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Additional Information */}
        <div className="mt-16 text-center">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">Frequently Asked Questions</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            <div className="text-left">
              <h3 className="font-semibold text-slate-900 mb-2">What counts as an API request?</h3>
              <p className="text-slate-600 text-sm">
                Each call to our analysis endpoints counts as one request. This includes component detection, 
                value assessment, and educational content retrieval.
              </p>
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-slate-900 mb-2">Can I change plans anytime?</h3>
              <p className="text-slate-600 text-sm">
                Yes, you can upgrade or downgrade your plan at any time. Changes take effect immediately, 
                and we'll prorate any billing differences.
              </p>
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-slate-900 mb-2">Do you offer custom pricing?</h3>
              <p className="text-slate-600 text-sm">
                Yes, we offer custom pricing for high-volume usage, enterprise deployments, 
                and specialized requirements. Contact our sales team for details.
              </p>
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-slate-900 mb-2">What payment methods do you accept?</h3>
              <p className="text-slate-600 text-sm">
                We accept all major credit cards, PayPal, and bank transfers for annual plans. 
                Enterprise customers can also pay via invoice.
              </p>
            </div>
          </div>
        </div>

        {/* CTA Section */}
        <div className="mt-16 bg-blue-600 rounded-2xl p-8 text-center text-white">
          <h2 className="text-3xl font-bold mb-4">Ready to Get Started?</h2>
          <p className="text-blue-100 mb-6 max-w-2xl mx-auto">
            Join thousands of developers and teams using Circuit.AI to build the future of electronics analysis.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="bg-white text-blue-600 hover:bg-blue-50">
              <Zap className="w-5 h-5 mr-2" />
              Start Free Trial
            </Button>
            <Button size="lg" variant="outline" className="border-white text-white hover:bg-white hover:text-blue-600">
              <Building className="w-5 h-5 mr-2" />
              Contact Sales
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
