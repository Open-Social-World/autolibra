import { useEffect, useState, useRef, useCallback } from "react";
import { Button } from "../components/ui/button"; 
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { ScrollArea } from "../components/ui/scroll-area";   
import { Separator } from "../components/ui/separator"; 
import { Skeleton } from "../components/ui/skeleton";
import { Header } from "../components/Header"; 
import { MessageSquare, Users, Calendar, TrendingUp, Search, ExternalLink } from 'lucide-react';
import { LabeledButton } from "../components/webvoyager_ui/LabeledButton";
import MetricSidebar from "../components/webvoyager_ui/MetricSidebar"; 
import webvoyagerLogo from "../assets/WebVoyagerLogo.png"; 
import { useNavigate } from "react-router-dom";
import TrajectorySearchBar from "../components/webvoyager_ui/trajectory-searchbar";
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
} from "../components/ui/command"; 
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "../components/ui/hover-card"; 
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
  type CarouselApi,
} from "../components/ui/carousel";
import CommentSystem from "../components/webvoyager_ui/comment-system";
import { SidebarProvider } from "../components/ui/sidebar";
import { AppSidebar } from "../components/sidebar";


// Interface for mock instances from the database
interface MockInstance {
  instance_id: string;
  label: string;
  folder_path: string;
}

// Interface for file data from the database
interface FileData {
  id: number;
  filename: string;
  filepath: string;
  filetype: string;
  filesize: number;
  created_at: string;
  description?: string;
  metadata?: any;
}

// Interface for instance details
interface InstanceDetails {
  instance_id: string;
  folder_path: string;
  description: string;
  files: FileData[];
  log_content: string | null;
  screenshot_log_pairs: ScreenshotLogPair[];
}

// Add a new interface for screenshot-log pairs
interface ScreenshotLogPair {
  screenshot_id: number;
  log_segment: string;
}

// Update LabeledButton props interface to match component
interface LabeledButtonProps {
  id: string;
  topic: string;
  selected?: boolean;
  onClick: (id: string) => void;
}

// Add missing TrajectorySummary interface
interface TrajectorySummary {
  id: string;
  title: string;
  description?: string;
  timestamp?: string;
}

// Interface for conversation entries from /trajectories/{instanceId}
interface ConversationEntry {
  agent_id: string;
  timestamp: string;
  content: string;
}

// Add timestamp formatting function
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

// Format conversation to string function
const formatConversationToString = (conv: ConversationEntry[]): string => {
  if (!conv || conv.length === 0) return "";
  return conv.map(entry => {
    const cleanContent = entry.content.replace(/^said:\s*/, '');
    return `[${formatTimestamp(entry.timestamp)}] ${entry.agent_id}:\n${cleanContent}`;
  }).join("\n\n---\n\n");
};

function WebVoyagerDashboard() {
  const [instances, setInstances] = useState<MockInstance[]>([]);
  const [selectedInstance, setSelectedInstance] = useState<string | null>(null);
  const [instanceDetails, setInstanceDetails] = useState<InstanceDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const navigate = useNavigate();

  const [open, setOpen] = useState(false);
  const [screenshots, setScreenshots] = useState<string[]>([]);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const carouselRef = useRef<HTMLDivElement>(null);
  const [currentLogSegment, setCurrentLogSegment] = useState<string>("");

  // Add state for carousel API
  const [carouselApi, setCarouselApi] = useState<CarouselApi | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);

  // Add missing trajectoryRefs state
  const [trajectoryRefs] = useState<{ [key: string]: React.RefObject<HTMLDivElement> }>({});

  useEffect(() => {
    async function fetchInstances() {
      try {
        const response = await fetch("http://localhost:8000/webvoyager/instances");
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data: MockInstance[] = await response.json();
        setInstances(data);
        setLoading(false);
      } catch (error) {
        console.error("Error fetching WebVoyager instances:", error);
        setLoading(false);
      }
    }

    fetchInstances();
  }, []);

  // Add effect to handle carousel changes
  useEffect(() => {
    if (!carouselApi) return;
    
    const handleSelect = () => {
      const selectedIndex = carouselApi.selectedScrollSnap();
      setCurrentIndex(selectedIndex);
      
      if (instanceDetails?.screenshot_log_pairs && 
          instanceDetails.screenshot_log_pairs[selectedIndex]) {
        setCurrentLogSegment(instanceDetails.screenshot_log_pairs[selectedIndex].log_segment);
      } else {
        setCurrentLogSegment("");
      }
    };
    
    carouselApi.on("select", handleSelect);
    
    // Call once to set initial state
    handleSelect();
    
    return () => {
      carouselApi.off("select", handleSelect);
    };
  }, [carouselApi, instanceDetails]);

  async function fetchInstanceDetails(instanceId: string) {
    setDetailsLoading(true);
    setSelectedInstance(instanceId);
    setInstanceDetails(null);
    setScreenshots([]);
    setCurrentLogSegment("");

    try {
      const response = await fetch(`http://localhost:8000/webvoyager/instances/${instanceId}`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data: InstanceDetails = await response.json();
      setInstanceDetails(data);
      
      // Extract screenshots from files
      const screenshotFiles = data.files.filter(file => 
        file.filetype === 'image/png' || 
        file.filetype === 'image/jpeg'
      );
      
      // Create URLs for screenshots
      const screenshotUrls = screenshotFiles.map(file => 
        `http://localhost:8000/webvoyager/files/${file.id}`
      );
      
      setScreenshots(screenshotUrls);
      
      // Set the initial log segment if available
      if (data.screenshot_log_pairs && data.screenshot_log_pairs.length > 0) {
        setCurrentLogSegment(data.screenshot_log_pairs[0].log_segment);
      }
      
      setDetailsLoading(false);
    } catch (error) {
      console.error(`Error fetching instance details for ${instanceId}:`, error);
      setInstanceDetails(null);
      setScreenshots([]);
      setDetailsLoading(false);
    }
  }

  // Function to handle instance selection
  const handleInstanceClick = (instanceId: string) => {
    fetchInstanceDetails(instanceId);
  };

  // Function to format file size
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
  };

  return (
    <SidebarProvider>
      <AppSidebar />
      <div className="container mx-auto p-4 md:p-6 lg:p-8">
        <Header
          logo={webvoyagerLogo}
          title="WebVoyager Interaction Inspector"
          subtitle1="Browse and analyze user interactions"
          subtitle2={`${instances.length} experiments loaded`}
          subtitle1Icon={<MessageSquare className="mr-1.5 h-4 w-4 text-muted-foreground" />}
          subtitle2Icon={<Calendar className="mr-1.5 h-4 w-4 text-muted-foreground" />}
        />

        <CommandDialog open={open} onOpenChange={setOpen}>
          <CommandInput placeholder="Search experiments by description..." />
          <CommandList>
            <CommandEmpty>No results found.</CommandEmpty>
            <CommandGroup heading="Experiments">
              {instances.map((instance) => (
                <CommandItem
                  key={instance.instance_id}
                  value={`${instance.instance_id} ${instance.label}`}
                  onSelect={() => {
                    fetchInstanceDetails(instance.instance_id);
                    setOpen(false);
                  }}
                >
                  {instance.label || instance.instance_id}
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
                      trajectories={instances.map(instance => ({
                          id: instance.instance_id,
                          title: instance.label,
                          description: "",
                          timestamp: ""
                      }))}
                      onSelectTrajectory={(trajectory: TrajectorySummary) => {
                          fetchInstanceDetails(trajectory.id);
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
                      {instances.map((instance) => (
                        <div ref={trajectoryRefs[instance.instance_id]} key={instance.instance_id}>
                          <LabeledButton
                            id={instance.instance_id}
                            topic={instance.label}
                            selected={selectedInstance === instance.instance_id}
                            onClick={(id: string) => {
                              fetchInstanceDetails(id);
                            }}
                          />
                        </div>
                      ))}
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
                          ? instances.find(i => i.instance_id === selectedInstance)?.label || ""
                          : "Interaction Details"
                      }
                      subtitle1={`Experiment ID: ${selectedInstance}`}
                      subtitle2={`${screenshots.length} screenshots`}
                      subtitle1Icon={<Users className="mr-1.5 h-4 w-4 text-muted-foreground" />}
                      subtitle2Icon={<Calendar className="mr-1.5 h-4 w-4 text-muted-foreground" />}
                      className="mb-0"
                    />
                  </div>
                ) : (
                  <CardTitle>Select an interaction</CardTitle>
                )}
              </CardHeader>
              <CardContent className="flex-grow p-4 flex flex-col gap-4">
                {/* Screenshots - Full width */}
                {screenshots.length > 0 ? (
                  <div className="w-full">
                    <Carousel setApi={setCarouselApi}>
                      <CarouselContent>
                        {screenshots.map((screenshot, index) => (
                          <CarouselItem key={index}>
                            <Card>
                              <CardContent className="flex aspect-video items-center justify-center p-2 relative">
                                <img 
                                  src={screenshot} 
                                  alt={`Screenshot ${index + 1} of ${screenshots.length}`} 
                                  className="max-h-full max-w-full object-contain"
                                />
                                <div className="absolute bottom-3 right-3 bg-black/70 text-white px-2 py-1 rounded text-sm">
                                  {index + 1} / {screenshots.length}
                                </div>
                              </CardContent>
                            </Card>
                          </CarouselItem>
                        ))}
                      </CarouselContent>
                      <CarouselPrevious />
                      <CarouselNext />
                    </Carousel>
                  </div>
                ) : (
                  <div className="text-center text-muted-foreground w-full">
                    No screenshots available.
                  </div>
                )}

                {/* Information and Comments - Side by side */}
                <div className="flex gap-4 flex-grow">
                  {/* Left side: Log/Information */}
                  <div className="flex-1 overflow-y-auto">
                    {currentLogSegment && (
                      <div className="p-4 bg-muted/50 rounded-lg text-sm whitespace-pre-wrap font-mono">
                        {currentLogSegment}
                      </div>
                    )}
                  </div>

                  {/* Right side: Comment System */}
                  <div className="w-[45%] border-l">
                    <div className="pl-4">
                      <h3 className="text-sm font-semibold mb-2">Agent Annotations</h3>
                      {detailsLoading ? (
                        <div className="text-center text-muted-foreground">Loading Interaction...</div>
                      ) : selectedInstance && instanceDetails?.log_content ? (
                        <CommentSystem
                          initialText={instanceDetails.log_content}
                          isLoading={false}
                          instanceId={selectedInstance}
                          agentId="agent"
                        />
                      ) : (
                        <div className="text-center text-muted-foreground">
                          {selectedInstance ? "No interaction data found." : "Select an interaction to view details."}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="md:col-span-3 space-y-4">
            {selectedInstance && (
              <Card className="h-full">
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <TrendingUp className="h-5 w-5" />
                    Experiment Details
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div>
                      <h3 className="text-sm font-medium">Description</h3>
                      <p className="text-sm text-muted-foreground">
                        {instanceDetails?.description || "No description available"}
                      </p>
                    </div>
                    
                    <div>
                      <h3 className="text-sm font-medium">Screenshots</h3>
                      <p className="text-sm text-muted-foreground">
                        {screenshots.length} available
                      </p>
                    </div>
                    
                    <Separator className="my-4" />
                    
                    <div>
                      <h3 className="text-sm font-medium mb-2">Files</h3>
                      <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2">
                        {instanceDetails?.files.map(file => (
                          <div key={file.id} className="text-xs p-2 bg-muted rounded-md">
                            <div className="font-medium">{file.filename}</div>
                            <div className="text-muted-foreground flex justify-between">
                              <span>{file.filetype.split('/')[1]}</span>
                              <span>{formatFileSize(file.filesize)}</span>
                            </div>
                            <div className="mt-1 flex justify-end">
                              <a 
                                href={`http://localhost:8000/webvoyager/files/${file.id}`} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className="text-xs flex items-center gap-1 text-blue-500 hover:text-blue-700"
                              >
                                View <ExternalLink className="h-3 w-3" />
                              </a>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
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

export default WebVoyagerDashboard;
