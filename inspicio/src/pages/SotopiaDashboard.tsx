import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Header } from "@/components/Header";
import { MessageSquare, Users, Calendar } from 'lucide-react';
import { LabeledButton } from "@/components/LabeledButton";
import { MetricSidebar } from "@/components/MetricSidebar";
import sotopiaLogo from "../assets/sotopia-logo.png";

interface Label {
  instance_id: string;
  label: string;
}

interface ConversationEntry {
  agent_id: string;
  timestamp: string;
  content: string;
}

interface MetricData {
  believability: number;
  relationship: number;
  knowledge: number;
  secret: number;
  social_rules: number;
  financial_and_material_benefits: number;
  goal: number;
  overall_score: number;
  [key: string]: number;
}

interface MetricDetails {
  explanation: string;
  good_behaviors: string[];
  bad_behaviors: string[];
}

interface ConversationData {
  instance_id: string;
  conversation: ConversationEntry[];
  scenario?: string;
  metrics?: Record<string, MetricData>;
  metric_details?: Record<string, MetricDetails>;
}

function SotopiaDashboard() {
  const [labels, setLabels] = useState<Label[]>([]);
  const [selectedInstance, setSelectedInstance] = useState<string | null>(null);
  const [conversation, setConversation] = useState<ConversationEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [scenario, setScenario] = useState<string>("");
  const [metrics, setMetrics] = useState<Record<string, MetricData> | null>(null);
  const [metricDetails, setMetricDetails] = useState<Record<string, MetricDetails> | null>(null);

  useEffect(() => {
    // Fetch labels when component mounts
    async function fetchLabels() {
      try {
        const response = await fetch("http://localhost:8000/trajectories");
        const data = await response.json();
        setLabels(data);
        setLoading(false);
      } catch (error) {
        console.error("Error fetching labels:", error);
        setLoading(false);
      }
    }

    fetchLabels();
  }, []);

  async function fetchConversation(instanceId: string) {
    setConversationLoading(true);
    setSelectedInstance(instanceId);
    setScenario("");
    setMetrics(null);
    setMetricDetails(null);
    
    try {
      const response = await fetch(`http://localhost:8000/trajectories/${instanceId}`);
      const data: ConversationData = await response.json();
      setConversation(data.conversation);
      
      if (data.scenario) {
        setScenario(data.scenario);
      }
      
      if (data.metrics) {
        setMetrics(data.metrics);
      }
      
      if (data.metric_details) {
        setMetricDetails(data.metric_details);
      }
      
      setConversationLoading(false);
    } catch (error) {
      console.error(`Error fetching conversation for ${instanceId}:`, error);
      setConversation([]);
      setScenario("");
      setMetrics(null);
      setMetricDetails(null);
      setConversationLoading(false);
    }
  }

  function formatTimestamp(timestamp: string): string {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  // Extract agent names from conversation
  const getAgentNames = () => {
    if (!conversation.length) return "";
    
    // Get unique agent names
    const agents = [...new Set(conversation.map(entry => entry.agent_id))];
    return agents.join(" & ");
  };
  
  // Extract date from conversation
  const getConversationDate = () => {
    if (!conversation.length) return "";
    
    // Get the date from the first message
    const firstMessage = conversation[0];
    const date = new Date(firstMessage.timestamp);
    return date.toLocaleDateString();
  };

  // Add this function to extract just the topic from the label
  const getTopicFromLabel = (label: string): string => {
    if (!label) return "Conversation";
    
    // Try to extract the middle part between pipes
    const parts = label.split('|');
    if (parts.length >= 2) {
      return parts[1].trim();
    }
    
    // If no pipes found, return the whole label
    return label;
  };

  // Add a function to render metrics
  const renderMetrics = () => {
    if (!metrics) return null;
    
    return (
      <div className="mt-6 space-y-4">
        <h3 className="text-lg font-medium">Performance Metrics</h3>
        {Object.entries(metrics).map(([agentId, agentMetrics]) => (
          <Card key={agentId} className="p-4">
            <h4 className="font-medium mb-2">{agentId}</h4>
            <div className="grid grid-cols-1 gap-4">
              {Object.entries(agentMetrics)
                .filter(([key]) => key !== "overall_score") // Display overall_score separately
                .map(([key, value]) => {
                  const details = metricDetails?.[key];
                  
                  return (
                    <div key={key} className="border rounded-md p-3">
                      <div className="flex justify-between mb-2">
                        <span className="font-medium capitalize">{key.replace(/_/g, ' ')}:</span>
                        <span className="font-medium">{value.toFixed(1)}/10</span>
                      </div>
                      
                      {details && (
                        <div className="text-sm space-y-2">
                          <p className="text-muted-foreground">{details.explanation}</p>
                          
                          {details.good_behaviors.length > 0 && (
                            <div>
                              <p className="font-medium text-green-600 dark:text-green-400">Good behaviors:</p>
                              <ul className="list-disc pl-5 text-muted-foreground">
                                {details.good_behaviors.map((behavior, i) => (
                                  <li key={i}>{behavior}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          
                          {details.bad_behaviors.length > 0 && (
                            <div>
                              <p className="font-medium text-red-600 dark:text-red-400">Bad behaviors:</p>
                              <ul className="list-disc pl-5 text-muted-foreground">
                                {details.bad_behaviors.map((behavior, i) => (
                                  <li key={i}>{behavior}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
            
            <div className="mt-4 pt-3 border-t">
              <div className="flex justify-between">
                <span className="font-medium">Overall Score:</span>
                <span className="font-bold">{agentMetrics.overall_score.toFixed(2)}/10</span>
              </div>
            </div>
          </Card>
        ))}
      </div>
    );
  };

  return (
    <div className="container p-4 mx-auto py-10">
      <Header 
        logo={sotopiaLogo}
        subtitle1={`${labels.length} trajectories`}
        subtitle1Icon={<MessageSquare className="mr-1.5 h-4 w-4 text-muted-foreground" />}
      />
      
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* Left Sidebar - Trajectories */}
        <div className="md:col-span-3">
          <Card>
            <CardHeader>
              <CardTitle>Trajectories</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[70vh]">
                {loading ? (
                  // Loading skeletons
                  <div className="space-y-2">
                    {Array.from({ length: 10 }).map((_, i) => (
                      <Skeleton key={i} className="h-10 w-full" />
                    ))}
                  </div>
                ) : (
                  <div className="space-y-2">
                    {labels.map((item) => {
                      // Extract topic, agents, and date from the label
                      const topic = getTopicFromLabel(item.label);
                      
                      // Extract agents and date if available in the label
                      const labelParts = item.label.split('|');
                      let agents = "";
                      let date = "";
                      
                      if (labelParts.length >= 3) {
                        agents = labelParts[0].trim();
                        date = labelParts[2].trim();
                      }
                      
                      return (
                        <LabeledButton
                          key={item.instance_id}
                          id={item.instance_id}
                          topic={topic}
                          agents={agents}
                          date={date}
                          isSelected={selectedInstance === item.instance_id}
                          onClick={fetchConversation}
                        />
                      );
                    })}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* Middle Panel - Conversation */}
        <div className="md:col-span-6">
          <Card>
            <CardHeader className="p-0">
              {selectedInstance ? (
                <div className="p-6">
                  <Header
                    title={
                      selectedInstance 
                        ? getTopicFromLabel(labels.find(l => l.instance_id === selectedInstance)?.label || "Conversation")
                        : "Conversation"
                    }
                    subtitle1={getAgentNames()}
                    subtitle2={getConversationDate()}
                    subtitle1Icon={<Users className="mr-1.5 h-4 w-4 text-muted-foreground" />}
                    subtitle2Icon={<Calendar className="mr-1.5 h-4 w-4 text-muted-foreground" />}
                    className="mb-0"
                  />
                </div>
              ) : (
                <CardTitle className="p-6">Select a conversation</CardTitle>
              )}
            </CardHeader>
            <CardContent>
              {scenario && (
                <div className="mb-6 p-4 bg-muted/50 rounded-lg">
                  <h3 className="text-sm font-medium mb-2">Scenario:</h3>
                  <p className="text-sm text-muted-foreground">{scenario}</p>
                </div>
              )}
              
              <ScrollArea className="h-[70vh] pr-4">
                {!selectedInstance ? (
                  <div className="flex items-center justify-center h-full">
                    <p className="text-muted-foreground">Select a conversation from the left panel</p>
                  </div>
                ) : conversationLoading ? (
                  <div className="space-y-4">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <div key={i} className="space-y-2">
                        <Skeleton className="h-4 w-[100px]" />
                        <Skeleton className="h-20 w-full" />
                      </div>
                    ))}
                  </div>
                ) : conversation.length === 0 ? (
                  <div className="flex items-center justify-center h-full">
                    <p className="text-muted-foreground">No conversation data available</p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {conversation.map((entry, index) => (
                      <div key={index} className="space-y-2">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{entry.agent_id}</span>
                        </div>
                        <div className="pl-4 border-l-2 border-muted-foreground/20">
                          <p className="whitespace-pre-wrap">
                            {entry.content.replace(/^said:\s*/, '')}
                          </p>
                        </div>
                        {index < conversation.length - 1 && <Separator className="my-4" />}
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>
        
        {/* Right Sidebar - Metrics */}
        <div className="md:col-span-3">
          <MetricSidebar
            title="Metrics"
            metrics={metrics}
            metricDetails={metricDetails}
            isLoading={conversationLoading}
            selectedId={selectedInstance}
            emptyMessage="No metrics available for this conversation"
          />
        </div>
      </div>
    </div>
  );
}

export default SotopiaDashboard;