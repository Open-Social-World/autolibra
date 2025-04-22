import { useEffect, useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button"; 
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";   
import { Separator } from "@/components/ui/separator"; 
import { Skeleton } from "@/components/ui/skeleton";
import { Header } from "@/components/Header"; 
import { MessageSquare, Users, Calendar, TrendingUp } from 'lucide-react';
import { LabeledButton } from "@/components/webarena_ui/LabeledButton"; // Updated path
import MetricSidebar from "@/components/webarena_ui/MetricSidebar"; // Updated path
import webarenaLogo from "../assets/WebArenaMascot.png"; // Assuming a webarena logo exists
import { useNavigate } from "react-router-dom";
import TrajectorySearchBar from "@/components/webarena_ui/trajectory-searchbar"; // Updated path
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
} from "@/components/ui/command"; 
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"; 


// Interface matches /webarena/trajectories output
interface Label {
  instance_id: string;
  label: string;
}

// Interface used internally and by TrajectorySearchBar
interface TrajectorySummary {
  id: string;
  title: string;
  description: string;
  timestamp: string;
}

// Interface matches conversation entries from /trajectories/{instanceId}
interface ConversationEntry {
  agent_id: string;
  timestamp: string;
  content: string;
}

// Interface matches overall structure from /trajectories/{instanceId}
interface ConversationData {
  instance_id: string;
  conversation: ConversationEntry[];
  scenario?: string; // Matches backend key
}

function WebArenaDashboard() {
  const [labels, setLabels] = useState<Label[]>([]);
  const [selectedInstance, setSelectedInstance] = useState<string | null>(null);
  const [conversation, setConversation] = useState<ConversationEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [scenario, setScenario] = useState<string>(""); // Holds the goal/task description
  const navigate = useNavigate();

  const [searchResults, setSearchResults] = useState<Label[]>([]);
  const [trajectoryRefs, setTrajectoryRefs] = useState<{ [key: string]: React.RefObject<HTMLDivElement> }>({});
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    async function fetchLabels() {
      try {
        // Use the dedicated WebArena endpoint
        const response = await fetch("http://localhost:8000/webarena/trajectories");
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data: Label[] = await response.json();
        setLabels(data);
        setLoading(false);
      } catch (error) {
        console.error("Error fetching WebArena labels:", error);
        setLoading(false);
      }
    }

    fetchLabels();
  }, []);

  async function fetchConversation(instanceId: string) {
    setConversationLoading(true);
    setSelectedInstance(instanceId);
    setScenario("");
    setConversation([]);

    try {
      // Use the WebArena-specific endpoint
      const response = await fetch(`http://localhost:8000/webarena/trajectories/${instanceId}`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data: ConversationData = await response.json();
      setConversation(data.conversation || []);

      // Use the 'scenario' key from backend data
      if (data.scenario) {
        setScenario(data.scenario);
      }

      setConversationLoading(false);
    } catch (error) {
      console.error(`Error fetching WebArena conversation for ${instanceId}:`, error);
      setConversation([]);
      setScenario("");
      setConversationLoading(false);
    }
  }

  // Timestamp formatting - assumes ISO format from backend is parseable
  function formatTimestamp(timestamp: string): string {
    try {
      const date = new Date(timestamp);
      if (isNaN(date.getTime())) return "Invalid Date";
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    } catch (e) {
      console.error("Error formatting timestamp:", timestamp, e);
      return timestamp;
    }
  }

  // Get unique agent IDs from conversation
  const getAgentIds = (): string[] => {
    if (!conversation.length) return [];
    // Use 'agent_id' key from ConversationEntry
    const ids = conversation.map(entry => entry.agent_id);
    return [...new Set(ids.filter(id => id != null))];
  };

  // Get conversation date from first entry
  const getConversationDate = (): string => {
    if (!conversation.length || !conversation[0].timestamp) return "N/A";
    try {
      // Assumes ISO format is parseable
      const date = new Date(conversation[0].timestamp);
      if (isNaN(date.getTime())) return "Invalid Date";
      return date.toLocaleDateString(); // Format as MM/DD/YYYY (locale-dependent)
    } catch (e) {
      console.error("Error parsing conversation date:", conversation[0].timestamp, e);
      return "Error Parsing Date";
    }
  };

  // Extract display title from label (assuming label is the title)
  const getTopicFromLabel = (label: string | undefined): string => {
    if (!label) return "Interaction";
    // Return label directly, assuming it's the task goal/title
    return label;
  };

  // Format conversation log string
  const formatConversationToString = (conv: ConversationEntry[]): string => {
    return conv
      .map(entry => {
        // Use keys from ConversationEntry
        const timestampStr = formatTimestamp(entry.timestamp);
        const agentId = entry.agent_id || 'Unknown';
        
        // Clean up the agent ID for display (capitalize first letter)
        const displayAgentId = agentId.charAt(0).toUpperCase() + agentId.slice(1);
        
        // Clean up the content
        let content = entry.content || '';
        
        // Extract description using regex pattern matching
        const descriptionMatch = content.match(/'description':\s*'((?:[^'\\]|\\.|'(?:\\.|[^'\\])*')*)'/) || 
                                content.match(/"description":\s*"((?:[^"\\]|\\.|"(?:\\.|[^"\\])*")*)"/) ||
                                content.match(/'description':\s*"((?:[^"\\]|\\.|"(?:\\.|[^"\\])*")*)"/) ||
                                content.match(/"description":\s*'((?:[^'\\]|\\.|'(?:\\.|[^'\\])*')*)'/) ;
        
        if (descriptionMatch && descriptionMatch[1]) {
          content = descriptionMatch[1];
        } else {
          // If no description, try to extract text field
          const textMatch = content.match(/'text':\s*'((?:[^'\\]|\\.|'(?:\\.|[^'\\])*')*)'/) || 
                           content.match(/"text":\s*"((?:[^"\\]|\\.|"(?:\\.|[^"\\])*")*)"/) ||
                           content.match(/'text':\s*"((?:[^"\\]|\\.|"(?:\\.|[^"\\])*")*)"/) ||
                           content.match(/"text":\s*'((?:[^'\\]|\\.|'(?:\\.|[^'\\])*')*)'/) ;
          
          if (textMatch && textMatch[1]) {
            content = textMatch[1];
          }
        }
        
        // Remove any remaining escaped quotes and clean up
        content = content.replace(/\\'/g, "'").replace(/\\"/g, '"');
        
        // Return the formatted entry
        return `[${timestampStr}] ${displayAgentId}: ${content}`;
      })
      .join('\n\n');
  };

  // Filter agent IDs for metrics sidebar (only 'agent')
  const agentIdsForMetrics = getAgentIds().filter(id => id === 'agent');

  return (
    <div className="container mx-auto p-4 md:p-6 lg:p-8">
      <Header
        logo={webarenaLogo}
        title="WebArena Interaction Inspector"
        subtitle1="Browse and analyze user interactions"
        subtitle2={`${labels.length} interactions loaded`}
        subtitle1Icon={<MessageSquare className="mr-1.5 h-4 w-4 text-muted-foreground" />}
        subtitle2Icon={<Calendar className="mr-1.5 h-4 w-4 text-muted-foreground" />}
      />

      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Search interactions by goal, ID, tag..." />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>
          <CommandGroup heading="Interactions">
            {labels.map((label) => (
              <CommandItem
                key={label.instance_id}
                value={`${label.instance_id} ${label.label}`}
                onSelect={() => {
                  fetchConversation(label.instance_id);
                  setOpen(false);
                }}
              >
                {getTopicFromLabel(label.label)}
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </CommandDialog>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        <div className="md:col-span-3">
          <Card className="h-full flex flex-col">
            <CardHeader>
              <CardTitle>Interactions</CardTitle>
              <div className="mt-4">
                 <TrajectorySearchBar
                    trajectories={labels.map(l => ({
                        id: l.instance_id,
                        title: getTopicFromLabel(l.label),
                        description: "",
                        timestamp: "",
                    }))}
                    onSelectTrajectory={(trajectory) => {
                        fetchConversation(trajectory.id);
                    }}
                 />
              </div>
            </CardHeader>
            <CardContent className="flex-grow overflow-hidden p-2">
              <ScrollArea className="h-[calc(100%-80px)]" ref={scrollAreaRef}>
                {loading ? (
                  <div className="space-y-2 p-2">
                    {Array.from({ length: 10 }).map((_, i) => (
                      <Skeleton key={i} className="h-16 w-full" />
                    ))}
                  </div>
                ) : (
                  <div className="space-y-2 p-1">
                    {(searchResults.length > 0 ? searchResults : labels).map((item) => {
                      const topic = getTopicFromLabel(item.label);

                      return (
                        <div ref={trajectoryRefs[item.instance_id]} key={item.instance_id}>
                          <LabeledButton
                            id={item.instance_id}
                            topic={topic}
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

        <div className="md:col-span-6">
          <Card className="flex flex-col h-full">
            <CardHeader className="flex-shrink-0 border-b">
              {selectedInstance ? (
                <div>
                  <Header
                    title={
                      selectedInstance
                        ? getTopicFromLabel(labels.find(l => l.instance_id === selectedInstance)?.label)
                        : "Interaction Details"
                    }
                    subtitle1={getAgentIds().length > 1 ? getAgentIds().join(" & ") : undefined}
                    subtitle2={getConversationDate()}
                    subtitle1Icon={getAgentIds().length > 1 ? <Users className="mr-1.5 h-4 w-4 text-muted-foreground" /> : undefined}
                    subtitle2Icon={<Calendar className="mr-1.5 h-4 w-4 text-muted-foreground" />}
                    className="mb-0 pb-4"
                  />
                </div>
              ) : (
                <CardTitle>Select an interaction</CardTitle>
              )}
              {scenario && (
                <div className="mt-2 p-3 bg-muted/50 rounded-lg text-sm">
                  <h3 className="font-semibold mb-1 text-foreground">Goal:</h3>
                  <p className="text-muted-foreground whitespace-pre-wrap">{scenario}</p>
                </div>
              )}
            </CardHeader>
            <CardContent className="flex-grow p-0 overflow-y-auto">
              {conversationLoading ? (
                 <div className="p-6 text-center text-muted-foreground">Loading Interaction...</div>
              ) : selectedInstance && conversation.length > 0 ? (
                 <ScrollArea className="h-full">
                   <pre className="text-sm whitespace-pre-wrap font-mono p-4 lg:p-6">
                     {formatConversationToString(conversation)}
                   </pre>
                 </ScrollArea>
              ) : (
                 <div className="p-6 text-center text-muted-foreground h-full flex items-center justify-center">
                   {selectedInstance ? "No interaction data found." : "Select an interaction to view details."}
                 </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="md:col-span-3 space-y-4">
          {selectedInstance && agentIdsForMetrics.length > 0 ? (
            agentIdsForMetrics.map(agentId => (
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
                    : selectedInstance
                      ? "Metrics only available for 'agent'."
                      : "Select an interaction to view agent metrics"}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

export default WebArenaDashboard;
