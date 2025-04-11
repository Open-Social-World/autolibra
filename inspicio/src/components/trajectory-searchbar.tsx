"use client";

import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { motion, AnimatePresence } from "motion/react";
import {
  Search,
  Send,
  FileText,
  MessageSquare,
  User,
  Users,
  Tag,
  Clock,
} from "lucide-react";
import useDebounce from "@/hooks/use-debounce";

interface Trajectory {
  id: string;
  title: string;
  description?: string;
  participants?: string[];
  tags?: string[];
  timestamp?: string;
  icon?: React.ReactNode;
}

interface SearchResult {
  trajectories: Trajectory[];
}

// Sample trajectories for demonstration
const sampleTrajectories: Trajectory[] = [
  {
    id: "traj-1",
    title: "Customer Support Conversation",
    description: "A user asking about product features",
    participants: ["User A", "Agent B"],
    tags: ["support", "product inquiry"],
    timestamp: "2023-10-15",
    icon: <MessageSquare className="h-4 w-4 text-blue-500" />,
  },
  {
    id: "traj-2",
    title: "Sales Negotiation",
    description: "Enterprise client discussing pricing options",
    participants: ["Sales Rep", "Client"],
    tags: ["sales", "negotiation", "enterprise"],
    timestamp: "2023-10-12",
    icon: <Users className="h-4 w-4 text-green-500" />,
  },
  {
    id: "traj-3",
    title: "Technical Troubleshooting",
    description: "Resolving a complex API integration issue",
    participants: ["Developer", "Support Engineer"],
    tags: ["technical", "API", "troubleshooting"],
    timestamp: "2023-10-10",
    icon: <FileText className="h-4 w-4 text-purple-500" />,
  },
  {
    id: "traj-4",
    title: "Onboarding Session",
    description: "New user orientation and setup",
    participants: ["New User", "Onboarding Specialist"],
    tags: ["onboarding", "training"],
    timestamp: "2023-10-08",
    icon: <User className="h-4 w-4 text-orange-500" />,
  },
  {
    id: "traj-5",
    title: "Feature Request Discussion",
    description: "Customer suggesting new product capabilities",
    participants: ["Customer", "Product Manager"],
    tags: ["feedback", "feature request"],
    timestamp: "2023-10-05",
    icon: <Tag className="h-4 w-4 text-red-500" />,
  },
];

function TrajectorySearchBar({
  trajectories = sampleTrajectories,
  defaultOpen = false,
  onSelectTrajectory = () => {},
}: {
  trajectories?: Trajectory[];
  defaultOpen?: boolean;
  onSelectTrajectory?: (trajectory: Trajectory) => void;
}) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [isFocused, setIsFocused] = useState(defaultOpen);
  const [isTyping, setIsTyping] = useState(false);
  const [selectedTrajectory, setSelectedTrajectory] = useState<Trajectory | null>(null);
  const debouncedQuery = useDebounce(query, 200);

  useEffect(() => {
    if (!isFocused) {
      setResult(null);
      return;
    }

    if (!debouncedQuery) {
      setResult({ trajectories: trajectories });
      return;
    }

    const normalizedQuery = debouncedQuery.toLowerCase().trim();
    const filteredTrajectories = trajectories.filter((trajectory) => {
      const searchableText = [
        trajectory.title,
        trajectory.description,
        ...(trajectory.participants || []),
        ...(trajectory.tags || []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      
      return searchableText.includes(normalizedQuery);
    });

    setResult({ trajectories: filteredTrajectories });
  }, [debouncedQuery, isFocused, trajectories]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
    setIsTyping(true);
  };

  const handleSelectTrajectory = (trajectory: Trajectory) => {
    setSelectedTrajectory(trajectory);
    onSelectTrajectory(trajectory);
    setIsFocused(false);
  };

  const container = {
    hidden: { opacity: 0, height: 0 },
    show: {
      opacity: 1,
      height: "auto",
      transition: {
        height: {
          duration: 0.4,
        },
        staggerChildren: 0.1,
      },
    },
    exit: {
      opacity: 0,
      height: 0,
      transition: {
        height: {
          duration: 0.3,
        },
        opacity: {
          duration: 0.2,
        },
      },
    },
  };

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.3,
      },
    },
    exit: {
      opacity: 0,
      y: -10,
      transition: {
        duration: 0.2,
      },
    },
  };

  const handleFocus = () => {
    setSelectedTrajectory(null);
    setIsFocused(true);
  };

  return (
    <div className="w-full">
      <div className="relative flex flex-col justify-start items-center min-h-[40px]">
        <div className="w-full sticky top-0 bg-background z-10 pb-0">
          <div className="relative">
            <Input
              type="text"
              placeholder="Search trajectories..."
              value={query}
              onChange={handleInputChange}
              onFocus={handleFocus}
              onBlur={() => setTimeout(() => setIsFocused(false), 200)}
              className="pl-3 pr-9 py-1 h-8 text-sm rounded-lg focus-visible:ring-offset-0"
            />
            <div className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4">
              <AnimatePresence mode="popLayout">
                {query.length > 0 ? (
                  <motion.div
                    key="send"
                    initial={{ y: -20, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    exit={{ y: 20, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <Send className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                  </motion.div>
                ) : (
                  <motion.div
                    key="search"
                    initial={{ y: -20, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    exit={{ y: 20, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <Search className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>

        <div className="w-full">
          <AnimatePresence>
            {isFocused && result && (
              <motion.div
                className="w-full border rounded-md shadow-xs overflow-hidden dark:border-gray-800 bg-white dark:bg-black mt-1"
                variants={container}
                initial="hidden"
                animate="show"
                exit="exit"
              >
                <motion.ul>
                  {result.trajectories.length > 0 ? (
                    result.trajectories.map((trajectory) => (
                      <motion.li
                        key={trajectory.id}
                        className="px-3 py-2 flex items-center justify-between hover:bg-gray-200 dark:hover:bg-zinc-900 cursor-pointer rounded-md"
                        variants={item}
                        layout
                        onClick={() => handleSelectTrajectory(trajectory)}
                      >
                        <div className="flex items-center gap-2 justify-between w-full">
                          <div className="flex items-center gap-2">
                            <span className="text-gray-500">
                              {trajectory.icon || <FileText className="h-4 w-4 text-gray-500" />}
                            </span>
                            <div className="flex flex-col">
                              <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                                {trajectory.title}
                              </span>
                              {trajectory.description && (
                                <span className="text-xs text-gray-400">
                                  {trajectory.description}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {trajectory.timestamp && (
                              <span className="text-xs text-gray-400 flex items-center">
                                <Clock className="h-3 w-3 mr-1" />
                                {trajectory.timestamp}
                              </span>
                            )}
                          </div>
                        </div>
                      </motion.li>
                    ))
                  ) : (
                    <motion.li
                      className="px-3 py-4 text-center text-sm text-gray-500"
                      variants={item}
                    >
                      No trajectories found
                    </motion.li>
                  )}
                </motion.ul>
                <div className="mt-2 px-3 py-2 border-t border-gray-100 dark:border-gray-800">
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>Press ⌘K to open search</span>
                    <span>ESC to cancel</span>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

export default TrajectorySearchBar;
