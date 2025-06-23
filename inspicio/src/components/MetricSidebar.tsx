"use client"

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
} from "@/components/ui/accordion"

interface MetricResult {
  goal_achievement_and_outcome_effectiveness: number;
  conversational_naturalness_and_efficiency: number;
  personality_consistency_and_alignment: number;
  negotiation_tactics_and_strategic_adaptability: number;
  contextual_integration_of_identity_and_personal_background: number;
  clarity_and_precision_in_communication: number;
  responsiveness_and_conversational_termination: number;
  adaptability_and_flexibility_in_dialogue: number;
  goal_achievement_and_outcome_effectiveness_reasoning: string;
  conversational_naturalness_and_efficiency_reasoning: string;
  personality_consistency_and_alignment_reasoning: string;
  negotiation_tactics_and_strategic_adaptability_reasoning: string;
  contextual_integration_of_identity_and_personal_background_reasoning: string;
  clarity_and_precision_in_communication_reasoning: string;
  responsiveness_and_conversational_termination_reasoning: string;
  adaptability_and_flexibility_in_dialogue_reasoning: string;
  instance_id: string;
  agent_id: string;
}

interface MetricSidebarProps {
  instanceId?: string;
  agentId?: string;
}

const chartConfig: ChartConfig = {
  goal: { color: "#FF5733" },
  conversation: { color: "#33FF57" },
  personality: { color: "#3357FF" },
  negotiation: { color: "#FF33F6" },
  context: { color: "#F6FF33" },
  clarity: { color: "#33FFF6" },
  responsiveness: { color: "#F633FF" },
  adaptability: { color: "#FF8C33" },
};

const metricLabels: Record<string, string> = {
  goal_achievement_and_outcome_effectiveness: "Goal Achievement",
  conversational_naturalness_and_efficiency: "Conversation Flow",
  personality_consistency_and_alignment: "Personality Consistency",
  negotiation_tactics_and_strategic_adaptability: "Negotiation Tactics",
  contextual_integration_of_identity_and_personal_background: "Context Integration",
  clarity_and_precision_in_communication: "Clarity & Precision",
  responsiveness_and_conversational_termination: "Responsiveness",
  adaptability_and_flexibility_in_dialogue: "Adaptability",
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

        const response = await fetch(`http://localhost:8000/sotopia/instances/${instanceId}/metrics/${agentId}`);

        if (!response.ok) {
          if (response.status === 404) {
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
          Metrics: {agentId || "Agent"}
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
                  const scoreSymbol = score === 1 ? "✓" : score === 0 ? "−" : "✗";

                  return (
                    <AccordionItem value={key} key={key} className="border rounded-md px-3">
                      <AccordionTrigger className="text-sm font-medium py-3 hover:no-underline">
                        <div className="flex justify-between items-center w-full pr-2">
                          <span>{label}</span>
                          <span className={`font-bold ${score === 1 ? 'text-green-600' : score === 0 ? 'text-yellow-600' : 'text-red-600'}`}>
                            {scoreSymbol}
                          </span>
                        </div>
                      </AccordionTrigger>
                      <AccordionContent className="text-xs pt-1 pb-3">
                        {reasoning || "No reasoning provided."}
                      </AccordionContent>
                    </AccordionItem>
                  );
                })}
              </Accordion>
            </div>
          ) : (
            <div className="text-muted-foreground text-center p-4 flex items-center justify-center h-full">
              {instanceId && agentId ? 'Loading metrics...' : 'Select an instance and agent to view metrics'}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export default MetricSidebar;
