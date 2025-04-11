import { useEffect, useState, useRef, createRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Header } from "@/components/Header";
import { MessageSquare, Users, Calendar } from 'lucide-react';
import { LabeledButton } from "@/components/LabeledButton";
import { MetricSidebar } from "@/components/MetricSidebar";
import sotopiaLogo from "../assets/sotopia-logo.png";
import { useNavigate } from "react-router-dom";
import TrajectorySearchBar from "@/components/trajectory-searchbar";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command"
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"


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
  agent_backgrounds?: Record<string, string>;
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
  const navigate = useNavigate();

  // Add this new state and function for search functionality
  const [searchResults, setSearchResults] = useState<Label[]>([]);
  
  // Create a map of refs for each trajectory item
  const [trajectoryRefs, setTrajectoryRefs] = useState<{[key: string]: React.RefObject<HTMLDivElement>}>({});
  // Ref for the scroll area
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  
  // Add state for command dialog
  const [open, setOpen] = useState(false);
  
  // Add a new state for agent backgrounds
  const [agentBackgrounds, setAgentBackgrounds] = useState<Record<string, string>>({});
  
  // Update refs when labels change
  useEffect(() => {
    // Create a ref for each label
    const refs: {[key: string]: React.RefObject<HTMLDivElement>} = {};
    labels.forEach(label => {
      refs[label.instance_id] = createRef<HTMLDivElement>();
    });
    setTrajectoryRefs(refs);
  }, [labels]);
  
  // Function to handle keyboard shortcut
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };
    
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);
  
  // Function to handle command selection
  const handleCommandSelect = useCallback((trajectoryId: string) => {
    fetchConversation(trajectoryId);
    setOpen(false);
    
    // Schedule scrolling to the selected item after a short delay
    setTimeout(() => {
      scrollToTrajectory(trajectoryId);
    }, 100);
  }, []);
  
  // Function to handle trajectory selection from search
  const handleSelectTrajectory = (trajectory: any) => {
    // Fetch the conversation data
    fetchConversation(trajectory.id);
    
    // Schedule scrolling to the selected item after a short delay
    // to ensure the UI has updated
    setTimeout(() => {
      scrollToTrajectory(trajectory.id);
    }, 100);
  };
  
  // Function to scroll to a specific trajectory
  const scrollToTrajectory = (trajectoryId: string) => {
    const ref = trajectoryRefs[trajectoryId];
    if (ref?.current && scrollAreaRef.current) {
      // Get the scroll container
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        // Calculate position to scroll to
        const itemTop = ref.current.offsetTop;
        const containerHeight = scrollContainer.clientHeight;
        const itemHeight = ref.current.offsetHeight;
        
        // Scroll the item into view, centered if possible
        scrollContainer.scrollTop = itemTop - (containerHeight / 2) + (itemHeight / 2);
      }
    }
  };
  
  // Filter labels based on search results or show all if no search results
  const displayedLabels = searchResults.length > 0 ? searchResults : labels;

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
    setAgentBackgrounds({}); // Reset agent backgrounds
    
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
      
      if (data.agent_backgrounds) {
        setAgentBackgrounds(data.agent_backgrounds);
      }
      
      setConversationLoading(false);
    } catch (error) {
      console.error(`Error fetching conversation for ${instanceId}:`, error);
      setConversation([]);
      setScenario("");
      setMetrics(null);
      setMetricDetails(null);
      setAgentBackgrounds({});
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
    <div className="container px-4 mx-auto py-10">
      <Header 
        logo={sotopiaLogo}
        subtitle1={`${labels.length} trajectories`}
        subtitle1Icon={<MessageSquare className="mr-1.5 h-4 w-4 text-muted-foreground" />}
      />
      
      {/* Add Command Dialog */}
      <CommandDialog open={open} onOpenChange={setOpen}>
        <Command>
          <CommandInput placeholder="Search trajectories..." />
          <CommandList>
            <CommandEmpty>No trajectories found.</CommandEmpty>
            <CommandGroup heading="Trajectories">
              {labels.map((item) => {
                const topic = getTopicFromLabel(item.label);
                const labelParts = item.label.split('|');
                let agents = "";
                let date = "";
                
                if (labelParts.length >= 3) {
                  agents = labelParts[0].trim();
                  date = labelParts[2].trim();
                }
                
                return (
                  <CommandItem
                    key={item.instance_id}
                    onSelect={() => handleCommandSelect(item.instance_id)}
                    className="flex items-center justify-between"
                  >
                    <div className="flex flex-col">
                      <span>{topic}</span>
                      {agents && (
                        <span className="text-xs text-muted-foreground flex items-center">
                          <Users className="mr-1 h-3 w-3" />
                          {agents}
                        </span>
                      )}
                    </div>
                    {date && (
                      <span className="text-xs text-muted-foreground">
                        <Calendar className="mr-1 h-3 w-3 inline" />
                        {date}
                      </span>
                    )}
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </CommandDialog>
      
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* Left Sidebar - Trajectories */}
        <div className="md:col-span-3">
        <Card>
          <CardHeader>
              <CardTitle>Trajectories</CardTitle>
          </CardHeader>
          <CardContent>
              {/* Add the TrajectorySearchBar component here */}
              <div className="mb-2">
                <TrajectorySearchBar 
                  trajectories={labels.map(label => ({
                    id: label.instance_id,
                    title: getTopicFromLabel(label.label),
                    description: label.label,
                    timestamp: label.label.split('|')[2]?.trim() || ""
                  }))}
                  onSelectTrajectory={handleSelectTrajectory}
                />
              </div>
              
              <ScrollArea className="h-[60vh]" ref={scrollAreaRef}>
                {loading ? (
                  // Loading skeletons
                  <div className="space-y-2">
                    {Array.from({ length: 10 }).map((_, i) => (
                      <Skeleton key={i} className="h-10 w-full" />
                    ))}
                  </div>
                ) : (
                  <div className="space-y-2">
                    {displayedLabels.map((item) => {
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
                        <div ref={trajectoryRefs[item.instance_id]} key={item.instance_id}>
                          <LabeledButton
                            id={item.instance_id}
                            topic={topic}
                            agents={agents}
                            date={date}
                            isSelected={selectedInstance === item.instance_id}
                            onClick={(id) => {
                              fetchConversation(id);
                            }}
                          />
                        </div>
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
                <CardTitle className="p-6">Select a trajectory</CardTitle>
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
                    <p className="text-muted-foreground">Select a trajectory from the left panel</p>
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
            agentBackgrounds={agentBackgrounds}
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