"use client"

import { useEffect, useState } from "react";
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
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";

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

        const response = await fetch(`/api/instances/${instanceId}/metrics/${agentId}`);

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

  const radarData = metrics
    ? [
        {
          subject: "Goal",
          A: metrics.goal_achievement_and_outcome_effectiveness,
          fullMark: 1,
        },
        {
          subject: "Conversation",
          A: metrics.conversational_naturalness_and_efficiency,
          fullMark: 1,
        },
        {
          subject: "Personality",
          A: metrics.personality_consistency_and_alignment,
          fullMark: 1,
        },
        {
          subject: "Negotiation",
          A: metrics.negotiation_tactics_and_strategic_adaptability,
          fullMark: 1,
        },
        {
          subject: "Context",
          A: metrics.contextual_integration_of_identity_and_personal_background,
          fullMark: 1,
        },
        {
          subject: "Clarity",
          A: metrics.clarity_and_precision_in_communication,
          fullMark: 1,
        },
        {
          subject: "Responsiveness",
          A: metrics.responsiveness_and_conversational_termination,
          fullMark: 1,
        },
        {
          subject: "Adaptability",
          A: metrics.adaptability_and_flexibility_in_dialogue,
          fullMark: 1,
        },
      ]
    : [];

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
              <Skeleton className="h-[200px] w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          ) : error ? (
            <div className="text-destructive p-4 text-center flex items-center justify-center">
              {error}
            </div>
          ) : metrics ? (
            <div className="space-y-6 p-4">
              <div className="flex justify-center">
                <ChartContainer config={chartConfig}>
                  <RadarChart 
                    width={300} 
                    height={300} 
                    data={radarData}
                    margin={{ top: 10, right: 30, bottom: 10, left: 30 }}
                  >
                    <PolarGrid />
                    <PolarAngleAxis dataKey="subject" />
                    <Radar
                      name="Performance"
                      dataKey="A"
                      stroke="#8884d8"
                      fill="#8884d8"
                      fillOpacity={0.6}
                    />
                    <ChartTooltip
                      content={<ChartTooltipContent />}
                    />
                  </RadarChart>
                </ChartContainer>
              </div>

              <div className="space-y-4">
                {Object.entries(metricLabels).map(([key, label]) => (
                  <div key={key} className="space-y-1">
                    <HoverCard>
                      <HoverCardTrigger asChild>
                        <div className="flex justify-between items-center cursor-help">
                          <span className="text-sm font-medium">{label}</span>
                          <span className="text-sm font-bold">
                            {metrics[key as keyof MetricResult] === 1 ? "✓" : 
                             metrics[key as keyof MetricResult] === 0 ? "−" : "✗"}
                          </span>
                        </div>
                      </HoverCardTrigger>
                      <HoverCardContent className="w-80">
                        <div className="space-y-2">
                          <h4 className="text-sm font-semibold">{label}</h4>
                          <p className="text-xs">
                            {metrics[`${key}_reasoning` as keyof MetricResult] as string}
                          </p>
                        </div>
                      </HoverCardContent>
                    </HoverCard>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-muted-foreground text-center p-4 flex items-center justify-center">
              {instanceId && agentId ? 'Loading metrics...' : 'Select an instance and agent to view metrics'}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export default MetricSidebar;
