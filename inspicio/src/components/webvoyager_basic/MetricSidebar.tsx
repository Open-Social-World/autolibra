"use client" // Keep client directive if needed

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp } from "lucide-react"; 
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"; 
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card"; 
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"; 

interface MetricResult {
  navigation_and_task_completion_accuracy_reasoning: string; 
  search_query_precision_reasoning: string;     
  element_interaction_accuracy_reasoning: string;          
  efficiency_in_action_sequencing_reasoning: string;    
  sorting_and_filtering_effectiveness_reasoning: string;
  feature_utilization_appropriateness_reasoning: string;
  repeated_action_avoidance_and_resource_management_reasoning: string;

  instance_id: string;
  agent_id: string; 
}

interface MetricSidebarProps {
  instanceId?: string;
  agentId?: string;
}

const chartConfig: ChartConfig = {
  // Update keys here if using charts, matching the metric keys above
  completion: { color: "#22c55e" },
  efficiency: { color: "#3b82f6" },
  errors: { color: "#ef4444" },
  satisfaction: { color: "#eab308" },
};

const metricLabels: Record<string, string> = {
  navigation_and_task_completion_accuracy: "Navigation & Task Completion Accuracy",
  search_query_precision: "Search Query Precision",
  element_interaction_accuracy: "Element Interaction Accuracy",
  efficiency_in_action_sequencing: "Efficiency in Action Sequencing",
  sorting_and_filtering_effectiveness: "Sorting and Filtering Effectiveness",
  feature_utilization_appropriateness: "Feature Utilization Appropriateness",
  repeated_action_avoidance_and_resource_management: "Repeated Action Avoidance and Resource Management",
};

const MetricSidebar = ({ instanceId, agentId }: MetricSidebarProps) => {
  const [metrics, setMetrics] = useState<MetricResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!instanceId || !agentId) {
      setLoading(false);
      setMetrics(null);
      setError(null);
      return;
    }

    const fetchMetrics = async () => {
      try {
        setLoading(true);
        setError(null);
        setMetrics(null);

        const response = await fetch(`http://localhost:8000/webarena/instances/${instanceId}/metrics/${agentId}`);

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error(`No metrics found for agent ${agentId} in instance ${instanceId}`);
            throw new Error(`No metrics found for agent ${agentId} in instance ${instanceId}`);
          }
          throw new Error(`Failed to fetch metrics: ${response.status} ${response.statusText}`);
        }

        const data: MetricResult = await response.json();
        setMetrics(data);

      } catch (err) {
        console.error("Error fetching metrics:", err);
        setError(err instanceof Error ? err.message : "Unknown error occurred");
        setMetrics(null);
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
  }, [instanceId, agentId]); 

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          Metrics
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea>
          {loading ? (
            <div className="space-y-4 p-4">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          ) : error ? (
            <div className="text-destructive p-4 text-center flex items-center justify-center h-full">
              {error}
            </div>
          ) : metrics ? (
            <div className="p-2">
              <Accordion type="single" collapsible className="w-full space-y-2">
                {Object.entries(metricLabels).map(([key, label]) => {
                  const score = metrics[key as keyof MetricResult];
                  const reasoning = metrics[`${key}_reasoning` as keyof MetricResult] as string;

                  // Determine symbol and color based on score
                  let scoreSymbol = "?";
                  let scoreColor = "text-muted-foreground";
                  if (typeof score === 'number') {
                      // Example logic: Adjust thresholds as needed for WebArena metrics
                      if (score > 0.75) {
                          scoreSymbol = "✓"; // Good
                          scoreColor = "text-green-600";
                      } else if (score > 0.25) {
                          scoreSymbol = "−"; // Neutral/Okay
                          scoreColor = "text-yellow-600";
                      } else {
                          scoreSymbol = "✗"; // Bad
                          scoreColor = "text-red-600";
                      }
                  } else if (score !== undefined && score !== null) {
                      // Handle non-numeric scores if applicable
                      scoreSymbol = String(score); // Display the value directly
                  }

                  return (
                    <AccordionItem value={key} key={key} className="border rounded-md px-3">
                      <AccordionTrigger className="text-sm font-medium py-3 hover:no-underline">
                        <div className="flex justify-between items-center w-full pr-2">
                          <span>{label}</span> {/* Display the human-readable label */}
                          <span className={`font-bold ${scoreColor}`}>
                            {scoreSymbol} {/* Display the interpreted score */}
                          </span>
                        </div>
                      </AccordionTrigger>
                      <AccordionContent className="text-xs pt-1 pb-3">
                        {reasoning || "No reasoning provided."} {/* Display reasoning */}
                      </AccordionContent>
                    </AccordionItem>
                  );
                })}
              </Accordion>
            </div>
          ) : (
            <div className="text-muted-foreground text-center p-4 flex items-center justify-center h-full">
              {instanceId && agentId ? 'Loading metrics...' : 'Select an interaction and agent to view metrics'}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export default MetricSidebar;
