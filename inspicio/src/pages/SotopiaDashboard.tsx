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
import CommentSystem from "@/components/comment-system";
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/sidebar";


interface Label {
  instance_id: string;
  label: string;
}

// Add a type for Trajectory based on usage
interface TrajectorySummary {
  id: string;
  title: string;
  description: string;
  timestamp: string;
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
        const response = await fetch("http://localhost:8000/sotopia/instances");
        const data = await response.json();
        // Transform the data to match the expected Label interface
        const transformedData = data.map((instance: any) => ({
          instance_id: instance.instance_id,
          label: instance.label
        }));
        setLabels(transformedData);
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
    setConversation([]); // Clear previous conversation

    try {
      const response = await fetch(`http://localhost:8000/sotopia/instances/${instanceId}/conversation`);
      const data: ConversationData = await response.json();
      setConversation(data.conversation || []); // Ensure conversation is set

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

  // Get unique agent IDs for rendering sidebars AND comment systems
  const agentIds = selectedInstance && conversation.length > 0
    ? [...new Set(conversation.map(entry => entry.agent_id))]
    : [];

  // Function to format conversation array into a single string for CommentSystem
  const formatConversationToString = (conv: ConversationEntry[]): string => {
    if (!conv || conv.length === 0) return "";
    return conv.map(entry => {
      // Remove "said: " prefix if present
      const cleanContent = entry.content.replace(/^said:\s*/, '');
      return `[${formatTimestamp(entry.timestamp)}] ${entry.agent_id}:\n${cleanContent}`;
    }).join("\n\n---\n\n"); // Separate messages clearly
  };

  return (
    <SidebarProvider>
      <AppSidebar />
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
                    onSelectTrajectory={(trajectory: TrajectorySummary) => {
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
                              onClick={(id: string) => {
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
          
          {/* Middle Panel - Conversation with potentially MULTIPLE CommentSystems */}
          <div className="md:col-span-6">
            <Card className="flex flex-col h-full">
              <CardHeader className="flex-shrink-0">
                {selectedInstance ? (
                  <div>
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
                  <CardTitle>Select a trajectory</CardTitle>
                )}
                {scenario && (
                  <div className="mt-4 p-3 bg-muted/50 rounded-lg text-sm">
                    <h3 className="font-medium mb-1">Scenario:</h3>
                    <p className="text-muted-foreground whitespace-pre-wrap">{scenario}</p>
                  </div>
                )}
              </CardHeader>
              <CardContent className="flex-grow p-0 overflow-y-auto">
                {conversationLoading ? (
                   <div className="p-4 text-center text-muted-foreground">Loading Conversation...</div>
                ) : selectedInstance && agentIds.length > 0 ? (
                   // Map over agentIds to render a CommentSystem for each agent
                   agentIds.map((agentId, index) => (
                     <div key={agentId} className={index > 0 ? "mt-4 border-t pt-4" : ""}>
                       <h3 className="text-md font-semibold mb-2 px-4">Annotating: {agentId}</h3>
                       <CommentSystem
                         // Pass the formatted conversation string
                         initialText={formatConversationToString(conversation)}
                         isLoading={false} // Loading is handled outside now
                         instanceId={selectedInstance}
                         // Pass the specific agentId for this instance
                         agentId={agentId}
                         dataset="sotopia"
                       />
                     </div>
                   ))
                ) : (
                   <div className="p-4 text-center text-muted-foreground h-full flex items-center justify-center">
                     {selectedInstance ? "No conversation data found." : "Select a trajectory to view conversation and annotations."}
                   </div>
                )}
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
    </SidebarProvider>
  );
}

export default SotopiaDashboard;