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

// --- Adapt this interface for ACTUAL WebArena Metrics ---
// Replace the example keys below (task_completion_rate, etc.)
// with the exact keys found in your WebArena metrics JSON data.
// Ensure you include both the score key (e.g., 'some_metric')
// and the reasoning key (e.g., 'some_metric_reasoning') if it exists.
interface MetricResult {
  navigation_and_task_completion_accuracy_reasoning: string; 
  search_query_precision_reasoning: string;     
  element_interaction_accuracy_reasoning: string;          
  efficiency_in_action_sequencing_reasoning: string;    
  sorting_and_filtering_effectiveness_reasoning: string;
  feature_utilization_appropriateness_reasoning: string;
  repeated_action_avoidance_and_resource_management_reasoning: string;

  // Keep instance/agent IDs (these should match the API response structure)
  instance_id: string;
  agent_id: string; // Should be 'agent' based on server logic
}
// --- End Adaptation ---

interface MetricSidebarProps {
  instanceId?: string;
  agentId?: string;
}

// --- Optional: Adapt ChartConfig if using charts ---
const chartConfig: ChartConfig = {
  // Update keys here if using charts, matching the metric keys above
  completion: { color: "#22c55e" },
  efficiency: { color: "#3b82f6" },
  errors: { color: "#ef4444" },
  satisfaction: { color: "#eab308" },
};
// --- End Optional Adaptation ---

// --- Adapt Metric Labels for ACTUAL WebArena Metrics ---
// Update this dictionary to map your actual metric keys (the score keys,
// e.g., 'task_completion_rate') to the desired display labels in the UI.
const metricLabels: Record<string, string> = {
  navigation_and_task_completion_accuracy: "Navigation & Task Completion Accuracy",
  search_query_precision: "Search Query Precision",
  element_interaction_accuracy: "Element Interaction Accuracy",
  efficiency_in_action_sequencing: "Efficiency in Action Sequencing",
  sorting_and_filtering_effectiveness: "Sorting and Filtering Effectiveness",
  feature_utilization_appropriateness: "Feature Utilization Appropriateness",
  repeated_action_avoidance_and_resource_management: "Repeated Action Avoidance and Resource Management",
};
// --- End Adaptation ---

// Component structure remains the same
const MetricSidebar = ({ instanceId, agentId }: MetricSidebarProps) => {
  const [metrics, setMetrics] = useState<MetricResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Logic for handling missing IDs remains the same
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

        // --- Update API Endpoint for WebArena ---
        // Use the endpoint defined in server.py
        const response = await fetch(`http://localhost:8000/webarena/instances/${instanceId}/metrics/${agentId}`);
        // --- End Update ---

        // Response handling logic remains the same
        if (!response.ok) {
          if (response.status === 404) {
            // Adapt error message if needed
            throw new Error(`No metrics found for agent ${agentId} in instance ${instanceId}`);
          }
          throw new Error(`Failed to fetch metrics: ${response.status} ${response.statusText}`);
        }

        const data: MetricResult = await response.json();
        setMetrics(data);

      } catch (err) {
        // Error handling logic remains the same
        console.error("Error fetching metrics:", err);
        setError(err instanceof Error ? err.message : "Unknown error occurred");
        setMetrics(null);
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
  }, [instanceId, agentId]); // Dependencies remain the same

  // Rendering structure remains the same
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          {/* Title remains generic */}
          Metrics: {agentId || "Agent"}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* ScrollArea usage remains the same */}
        <ScrollArea>
          {/* Loading state rendering remains the same */}
          {loading ? (
            <div className="space-y-4 p-4">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          /* Error state rendering remains the same */
          ) : error ? (
            <div className="text-destructive p-4 text-center flex items-center justify-center h-full">
              {error}
            </div>
          /* Metrics display logic using Accordion remains the same */
          ) : metrics ? (
            <div className="p-2">
              <Accordion type="single" collapsible className="w-full space-y-2">
                {/* Iterate over the adapted metricLabels */}
                {Object.entries(metricLabels).map(([key, label]) => {
                  // Access score and reasoning using the actual keys from MetricResult
                  const score = metrics[key as keyof MetricResult];
                  const reasoning = metrics[`${key}_reasoning` as keyof MetricResult] as string;

                  // Determine symbol and color based on score
                  // (Keep or adapt the existing logic for score interpretation)
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
          /* Empty state rendering remains the same, text adapted slightly */
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
