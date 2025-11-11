"use client";

import { useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RotateCcw, ZoomIn, ZoomOut, Eye, EyeOff } from 'lucide-react';

interface Component3DViewerProps {
  component: {
    type: string;
    package_type?: string;
    pin_count?: number;
    manufacturer?: string;
    part_number?: string;
  };
  className?: string;
}

export function Component3DViewer({ component, className }: Component3DViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [viewMode, setViewMode] = useState<'3d' | '2d'>('3d');
  const [showPins, setShowPins] = useState(true);

  useEffect(() => {
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    canvas.width = 400;
    canvas.height = 300;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw component based on type
    drawComponent(ctx, component, viewMode, showPins);
    setIsLoaded(true);
  }, [component, viewMode, showPins]);

  const drawComponent = (
    ctx: CanvasRenderingContext2D,
    component: any,
    mode: '3d' | '2d',
    pins: boolean
  ) => {
    const centerX = 200;
    const centerY = 150;
    const width = 120;
    const height = 80;

    if (mode === '3d') {
      // 3D effect with perspective
      ctx.save();
      
      // Create 3D effect
      ctx.transform(1, 0, 0.3, 1, 0, 0);
      
      // Draw main body
      ctx.fillStyle = '#374151';
      ctx.fillRect(centerX - width/2, centerY - height/2, width, height);
      
      // Draw top face (lighter)
      ctx.fillStyle = '#6B7280';
      ctx.fillRect(centerX - width/2, centerY - height/2 - 10, width, 10);
      
      // Draw side face
      ctx.fillStyle = '#4B5563';
      ctx.fillRect(centerX + width/2, centerY - height/2, 10, height);
      
      ctx.restore();

      // Draw pins if enabled
      if (pins && component.pin_count) {
        drawPins3D(ctx, centerX, centerY, width, height, component.pin_count);
      }

      // Add component label
      ctx.fillStyle = '#FFFFFF';
      ctx.font = '12px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(component.part_number || component.type, centerX, centerY + 5);
    } else {
      // 2D top view
      ctx.fillStyle = '#374151';
      ctx.fillRect(centerX - width/2, centerY - height/2, width, height);
      
      // Draw pin indicators
      if (pins && component.pin_count) {
        drawPins2D(ctx, centerX, centerY, width, height, component.pin_count);
      }
      
      // Add component details
      ctx.fillStyle = '#FFFFFF';
      ctx.font = '10px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(component.part_number || component.type, centerX, centerY - 10);
      ctx.fillText(component.manufacturer || '', centerX, centerY + 5);
    }
  };

  const drawPins3D = (
    ctx: CanvasRenderingContext2D,
    centerX: number,
    centerY: number,
    width: number,
    height: number,
    pinCount: number
  ) => {
    const pinsPerSide = Math.ceil(pinCount / 2);
    const pinSpacing = width / (pinsPerSide + 1);
    
    ctx.fillStyle = '#F59E0B';
    
    // Bottom pins
    for (let i = 0; i < pinsPerSide; i++) {
      const x = centerX - width/2 + pinSpacing * (i + 1);
      const y = centerY + height/2;
      ctx.fillRect(x - 2, y, 4, 15);
    }
    
    // Top pins
    for (let i = 0; i < pinsPerSide; i++) {
      const x = centerX - width/2 + pinSpacing * (i + 1);
      const y = centerY - height/2 - 15;
      ctx.fillRect(x - 2, y, 4, 15);
    }
  };

  const drawPins2D = (
    ctx: CanvasRenderingContext2D,
    centerX: number,
    centerY: number,
    width: number,
    height: number,
    pinCount: number
  ) => {
    const pinsPerSide = Math.ceil(pinCount / 2);
    const pinSpacing = width / (pinsPerSide + 1);
    
    ctx.fillStyle = '#F59E0B';
    
    // Bottom pins
    for (let i = 0; i < pinsPerSide; i++) {
      const x = centerX - width/2 + pinSpacing * (i + 1);
      const y = centerY + height/2;
      ctx.fillRect(x - 1, y, 2, 8);
    }
    
    // Top pins
    for (let i = 0; i < pinsPerSide; i++) {
      const x = centerX - width/2 + pinSpacing * (i + 1);
      const y = centerY - height/2 - 8;
      ctx.fillRect(x - 1, y, 2, 8);
    }
  };

  const resetView = () => {
    setViewMode('3d');
    setShowPins(true);
  };

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>3D Component Viewer</span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setViewMode(viewMode === '3d' ? '2d' : '3d')}
            >
              {viewMode === '3d' ? '2D' : '3D'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowPins(!showPins)}
            >
              {showPins ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={resetView}
            >
              <RotateCcw className="w-4 h-4" />
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative">
          <canvas
            ref={canvasRef}
            className="w-full h-64 border border-gray-200 rounded-lg bg-gradient-to-br from-gray-50 to-gray-100"
          />
          {!isLoaded && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-gray-500">Loading component...</div>
            </div>
          )}
        </div>
        
        <div className="mt-4 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Package:</span>
            <span className="font-medium">{component.package_type || 'Standard'}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Pins:</span>
            <span className="font-medium">{component.pin_count || 'N/A'}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Manufacturer:</span>
            <span className="font-medium">{component.manufacturer || 'Unknown'}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
