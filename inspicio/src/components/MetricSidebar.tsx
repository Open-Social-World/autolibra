"use client"

import { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp } from "lucide-react";
import { PolarAngleAxis, PolarGrid, Radar, RadarChart } from "recharts";
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";

export interface MetricValue {
  value: number;
  maxValue?: number;
  [key: string]: any;
}

export interface MetricDetail {
  explanation?: string;
  good_behaviors?: string[];
  bad_behaviors?: string[];
  [key: string]: any;
}

export interface MetricSidebarProps {
  title?: string;
  metrics?: Record<string, Record<string, MetricValue>>;
  metricDetails?: Record<string, MetricDetail>;
  isLoading?: boolean;
  selectedId?: string | null;
  emptyMessage?: string;
  loadingSkeletonCount?: number;
  className?: string;
  renderCustomMetric?: (key: string, value: MetricValue, details?: MetricDetail) => ReactNode;
  showRadarChart?: boolean;
}

export function MetricSidebar({
  title = "Metrics",
  metrics,
  metricDetails,
  isLoading = false,
  selectedId = null,
  emptyMessage = "No metrics available",
  loadingSkeletonCount = 3,
  className = "",
  renderCustomMetric,
  showRadarChart = true,
}: MetricSidebarProps) {
  // Format a metric value with its max value
  const formatMetricValue = (value: number, maxValue: number = 10) => {
    return `${value.toFixed(1)}/${maxValue}`;
  };

  // Default metric renderer
  const defaultRenderMetric = (key: string, metricValue: MetricValue, details?: MetricDetail) => {
    const { value, maxValue = 10 } = metricValue;
    
    return (
      <div key={key} className="space-y-1">
        <div className="flex justify-between items-center">
          <span className="text-xs capitalize">{key.replace(/_/g, ' ')}</span>
          <span className="text-xs font-medium">{formatMetricValue(value, maxValue)}</span>
        </div>
        
        {details && (
          <details className="text-xs">
            <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
              Details
            </summary>
            <div className="mt-2 space-y-2 pl-2 border-l-2 border-muted">
              {details.explanation && (
                <p className="text-muted-foreground">{details.explanation}</p>
              )}
              
              {details.good_behaviors && details.good_behaviors.length > 0 && (
                <div>
                  <p className="font-medium text-green-600 dark:text-green-400">Good behaviors:</p>
                  <ul className="list-disc pl-4 text-muted-foreground">
                    {details.good_behaviors.map((behavior, i) => (
                      <li key={i}>{behavior}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {details.bad_behaviors && details.bad_behaviors.length > 0 && (
                <div>
                  <p className="font-medium text-red-600 dark:text-red-400">Bad behaviors:</p>
                  <ul className="list-disc pl-4 text-muted-foreground">
                    {details.bad_behaviors.map((behavior, i) => (
                      <li key={i}>{behavior}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </details>
        )}
      </div>
    );
  };

  // Prepare radar chart data if metrics are available
  const renderRadarChart = (categoryId: string, categoryMetrics: Record<string, any>) => {
    if (!showRadarChart) return null;
    
    // Filter out overall score
    const filteredMetrics = Object.entries(categoryMetrics).filter(
      ([key]) => !['overall_score', 'overall', 'score'].includes(key)
    );
    
    // Format data for radar chart
    const chartData = filteredMetrics.map(([key, value]) => {
      const metricValue = typeof value === 'number' ? value : value.value;
      return {
        metric: key.replace(/_/g, ' '),
        value: metricValue
      };
    });
    
    // Sage green colors
    const sageGreen = "#7C9D8E";
    const paleSageGreen = "#E1EAE5";
    
    return (
      <div className="mt-4">
        <ChartContainer
          config={{
            value: {
              label: categoryId,
              color: sageGreen,
            },
          }}
          className="mx-auto aspect-square max-h-[200px]"
        >
          <RadarChart data={chartData}>
            <ChartTooltip
              cursor={false}
              content={<ChartTooltipContent hideLabel />}
            />
            <PolarGrid stroke={paleSageGreen} />
            <PolarAngleAxis dataKey="metric" stroke="#6B7280" />
            <Radar
              dataKey="value"
              stroke={sageGreen}
              fill={sageGreen}
              fillOpacity={0.5}
            />
          </RadarChart>
        </ChartContainer>
      </div>
    );
  };

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[70vh]">
          {!selectedId ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-muted-foreground">Select an item to view metrics</p>
            </div>
          ) : isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: loadingSkeletonCount }).map((_, i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))}
            </div>
          ) : !metrics || Object.keys(metrics).length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-muted-foreground">{emptyMessage}</p>
            </div>
          ) : (
            <div className="space-y-6">
              {Object.entries(metrics).map(([categoryId, categoryMetrics]) => {
                // Get overall score if it exists
                const overallScore = categoryMetrics.overall_score || 
                                    categoryMetrics.overall || 
                                    categoryMetrics.score;
                
                // Filter out overall score from the metrics list
                const filteredMetrics = Object.entries(categoryMetrics).filter(
                  ([key]) => !['overall_score', 'overall', 'score'].includes(key)
                );
                
                return (
                  <div key={categoryId} className="space-y-3">
                    <h4 className="font-medium text-sm border-b pb-1">{categoryId}</h4>
                    
                    {/* Render radar chart if enabled */}
                    {renderRadarChart(categoryId, categoryMetrics)}
                    
                    {filteredMetrics.map(([key, value]) => {
                      const metricValue = typeof value === 'number' ? { value } : value;
                      const details = metricDetails?.[key];
                      
                      return renderCustomMetric 
                        ? renderCustomMetric(key, metricValue, details)
                        : defaultRenderMetric(key, metricValue, details);
                    })}
                    
                    {overallScore && (
                      <div className="pt-2 border-t">
                        <div className="flex justify-between">
                          <span className="font-medium text-xs">Overall Score:</span>
                          <span className="font-bold text-xs">
                            {typeof overallScore === 'number' 
                              ? formatMetricValue(overallScore) 
                              : formatMetricValue(overallScore.value, overallScore.maxValue || 10)}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
