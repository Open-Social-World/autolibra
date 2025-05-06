import { useEffect, useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button"; 
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";   
import { Separator } from "@/components/ui/separator"; 
import { Skeleton } from "@/components/ui/skeleton";
import { Header } from "@/components/Header"; 
import { MessageSquare, Users, Calendar, TrendingUp, Search, ExternalLink } from 'lucide-react';
import { LabeledButton } from "@/components/webarena_mock_ui/LabeledButton"; // Updated path
import MetricSidebar from "@/components/webarena_mock_ui/MetricSidebar"; // Updated path
import webarenaLogo from "../assets/WebArenaMascot.png"; // Assuming a webarena logo exists
import { useNavigate } from "react-router-dom";
import TrajectorySearchBar from "@/components/webarena_mock_ui/trajectory-searchbar"; // Updated path
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
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel";


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
}

function WebArenaMock() {
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

  useEffect(() => {
    async function fetchInstances() {
      try {
        const response = await fetch("http://localhost:8000/webarena/mock/instances");
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data: MockInstance[] = await response.json();
        setInstances(data);
        setLoading(false);
      } catch (error) {
        console.error("Error fetching WebArena mock instances:", error);
        setLoading(false);
      }
    }

    fetchInstances();
  }, []);

  async function fetchInstanceDetails(instanceId: string) {
    setDetailsLoading(true);
    setSelectedInstance(instanceId);
    setInstanceDetails(null);
    setScreenshots([]);

    try {
      const response = await fetch(`http://localhost:8000/webarena/mock/instances/${instanceId}`);
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
        `http://localhost:8000/webarena/mock/files/${file.id}`
      );
      
      setScreenshots(screenshotUrls);
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
    <div className="container mx-auto p-4 md:p-6 lg:p-8">
      <Header
        logo={webarenaLogo}
        title="WebArena Interaction Inspector"
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
              <CardTitle>Experiments</CardTitle>
              <div className="mt-4">
                <Button 
                  variant="outline" 
                  className="w-full justify-start text-left font-normal"
                  onClick={() => setOpen(true)}
                >
                  <Search className="mr-2 h-4 w-4" />
                  <span>Search experiments...</span>
                </Button>
              </div>
            </CardHeader>
            <CardContent className="flex-grow overflow-hidden p-2">
              <ScrollArea className="h-[calc(100vh-250px)]" ref={scrollAreaRef}>
                {loading ? (
                  <div className="space-y-2 p-2">
                    {Array.from({ length: 10 }).map((_, i) => (
                      <Skeleton key={i} className="h-16 w-full" />
                    ))}
                  </div>
                ) : (
                  <div className="space-y-2 p-1">
                    {instances.map((instance) => (
                      <LabeledButton
                        key={instance.instance_id}
                        id={instance.instance_id}
                        topic={instance.label || instance.instance_id}
                        isSelected={selectedInstance === instance.instance_id}
                        onClick={handleInstanceClick}
                      />
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
              {instanceDetails ? (
                <div>
                  <Header
                    title={instanceDetails.description || instanceDetails.instance_id}
                    subtitle1={`Experiment ID: ${instanceDetails.instance_id}`}
                    subtitle1Icon={<Calendar className="mr-1.5 h-4 w-4 text-muted-foreground" />}
                    className="mb-0 pb-4"
                  />
                </div>
              ) : (
                <CardTitle>Experiment Screenshots</CardTitle>
              )}
            </CardHeader>
            <CardContent className="flex-grow p-4 overflow-y-auto">
              {screenshots.length > 0 ? (
                <div className="p-1 mb-4">
                  <Carousel>
                    <CarouselContent>
                      {screenshots.map((screenshot, index) => (
                        <CarouselItem key={index}>
                          <Card>
                            <CardContent className="flex aspect-video items-center justify-center p-2">
                              <img 
                                src={screenshot} 
                                alt={`Screenshot ${index + 1} of ${screenshots.length}`} 
                                className="max-h-full max-w-full object-contain"
                              />
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
                <div className="p-6 text-center text-muted-foreground mb-4">
                  No screenshots available.
                </div>
              )}
              
              {detailsLoading ? (
                <div className="p-6 text-center text-muted-foreground">Loading experiment log...</div>
              ) : instanceDetails?.log_content ? (
                <div className="p-4 bg-muted/50 rounded-lg text-sm whitespace-pre-wrap font-mono">
                  {instanceDetails.log_content}
                </div>
              ) : (
                <div className="p-6 text-center text-muted-foreground">
                  {selectedInstance ? "No log available for this experiment." : "Select an experiment to view details."}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="md:col-span-3 space-y-4">
          {instanceDetails ? (
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
                      {instanceDetails.description || "No description available"}
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
                      {instanceDetails.files.map(file => (
                        <div key={file.id} className="text-xs p-2 bg-muted rounded-md">
                          <div className="font-medium">{file.filename}</div>
                          <div className="text-muted-foreground flex justify-between">
                            <span>{file.filetype.split('/')[1]}</span>
                            <span>{formatFileSize(file.filesize)}</span>
                          </div>
                          <div className="mt-1 flex justify-end">
                            <a 
                              href={`http://localhost:8000/webarena/mock/files/${file.id}`} 
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
          ) : (
            <Card className="h-full">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" />
                  Experiment Details
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-muted-foreground text-center p-4 h-[calc(100vh-250px)] flex items-center justify-center">
                  Select an experiment to view details
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

export default WebArenaMock;
