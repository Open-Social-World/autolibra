import { useEffect, useState, useRef, createRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Header } from "@/components/Header";
import { MessageSquare, Users, Calendar, TrendingUp } from 'lucide-react';
import { LabeledButton } from "@/components/LabeledButton";
import MetricSidebar from "@/components/MetricSidebar";
import sotopiaLogo from "../assets/sotopia.png";
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

interface ConversationData {
  instance_id: string;
  conversation: ConversationEntry[];
  scenario?: string;
}

function SotopiaDashboard() {
  const [labels, setLabels] = useState<Label[]>([]);
  const [selectedInstance, setSelectedInstance] = useState<string | null>(null);
  const [conversation, setConversation] = useState<ConversationEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [scenario, setScenario] = useState<string>("");
  const navigate = useNavigate();

  const [searchResults, setSearchResults] = useState<Label[]>([]);
  const [trajectoryRefs, setTrajectoryRefs] = useState<{ [key: string]: React.RefObject<HTMLDivElement> }>({});
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

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

    try {
      const response = await fetch(`http://localhost:8000/trajectories/${instanceId}`);
      const data: ConversationData = await response.json();
      setConversation(data.conversation);

      if (data.scenario) {
        setScenario(data.scenario);
      }

      setConversationLoading(false);
    } catch (error) {
      console.error(`Error fetching conversation for ${instanceId}:`, error);
      setConversation([]);
      setScenario("");
      setConversationLoading(false);
    }
  }

  function formatTimestamp(timestamp: string): string {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  // Extract agent names from conversation
  const getAgentNames = () => {
    if (!conversation.length) return []; // Return array of names
    // Get unique agent names
    const agents = [...new Set(conversation.map(entry => entry.agent_id))];
    return agents;
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

  // Get unique agent IDs for rendering sidebars
  const agentIds = selectedInstance && conversation.length > 0
    ? [...new Set(conversation.map(entry => entry.agent_id))]
    : [];

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
                    onSelect={() => {
                      fetchConversation(item.instance_id);
                      setOpen(false);
                    }}
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
              <div className="mb-2">
                <TrajectorySearchBar 
                  trajectories={labels.map(label => ({
                    id: label.instance_id,
                    title: getTopicFromLabel(label.label),
                    description: label.label,
                    timestamp: label.label.split('|')[2]?.trim() || ""
                  }))}
                  onSelectTrajectory={(trajectory) => {
                    fetchConversation(trajectory.id);
                    setOpen(false);
                  }}
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
                    {(searchResults.length > 0 ? searchResults : labels).map((item) => {
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
                    subtitle1={getAgentNames().join(" & ")}
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
        <div className="md:col-span-3 space-y-4">
          {selectedInstance && agentIds.length > 0 ? (
            agentIds.map(agentId => (
              <MetricSidebar
                key={agentId}
                instanceId={selectedInstance}
                agentId={agentId}
              />
            ))
          ) : (
            <Card className="h-full">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" />
                  Agent Performance Metrics
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-muted-foreground text-center p-4 h-[calc(100vh-200px)] flex items-center justify-center">
                  {conversationLoading
                    ? "Loading..."
                    : "Select a trajectory to view agent metrics"}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

export default SotopiaDashboard;