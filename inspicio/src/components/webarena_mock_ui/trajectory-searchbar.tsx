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
} from "lucide-react"; // Keep icons
import useDebounce from "@/hooks/use-debounce"; // Keep debounce hook

interface TrajectorySummary {
  id: string;
  title: string; // e.g., Task Goal
  description?: string; // e.g., Task Description
  participants?: string[]; // Or roles, actors
  tags?: string[]; // Relevant tags for WebArena tasks
  timestamp?: string; // Timestamp if available
  icon?: React.ReactNode; // Icon representation
}

interface SearchResult {
  trajectories: TrajectorySummary[]; 
}

const sampleInteractions: TrajectorySummary[] = [
  {
    id: "wa-1",
    title: "Book Flight",
    description: "Find and book a round-trip flight from SFO to LHR",
    tags: ["travel", "booking", "flight"],
    timestamp: "2024-03-10",
    icon: <MessageSquare className="h-4 w-4 text-blue-500" />, // Example icon
  },
  {
    id: "wa-2",
    title: "Online Shopping - Add to Cart",
    description: "Navigate e-commerce site, find specific item, add to cart",
    tags: ["shopping", "e-commerce", "navigation"],
    timestamp: "2024-03-08",
    icon: <Tag className="h-4 w-4 text-red-500" />, // Example icon
  },
  {
    id: "wa-3",
    title: "Configure Cloud Server",
    description: "Set up a new virtual machine with specific OS and resources",
    tags: ["cloud", "configuration", "technical"],
    timestamp: "2024-03-05",
    icon: <FileText className="h-4 w-4 text-purple-500" />, // Example icon
  },
];

function TrajectorySearchBar({
  trajectories = sampleInteractions, 
  defaultOpen = false,
  onSelectTrajectory = () => {},
}: {
  trajectories?: TrajectorySummary[];
  defaultOpen?: boolean;
  onSelectTrajectory?: (trajectory: TrajectorySummary) => void;
}) {
  // State management logic remains identical
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [isFocused, setIsFocused] = useState(defaultOpen);
  const [isTyping, setIsTyping] = useState(false);
  const [selectedTrajectory, setSelectedTrajectory] = useState<TrajectorySummary | null>(null);
  const debouncedQuery = useDebounce(query, 200);

  // useEffect logic for filtering remains identical
  useEffect(() => {
    if (!isFocused) {
      setResult(null);
      return;
    }

    // Show all initially or when query is cleared
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

  // Event handlers remain identical
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
    setIsTyping(true); 
  };

  const handleSelectTrajectory = (trajectory: TrajectorySummary) => {
    setSelectedTrajectory(trajectory);
    onSelectTrajectory(trajectory);
    setIsFocused(false); // Close dropdown on selection
  };

  // Animation variants remain identical
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
    setSelectedTrajectory(null); // Clear selection on focus
    setIsFocused(true);
  };

  // JSX structure remains identical, only text placeholders updated
  return (
    <div className="w-full">
      <div className="relative flex flex-col justify-start items-center min-h-[40px]">
        <div className="w-full sticky top-0 bg-background z-10 pb-0">
          <div className="relative">
            <Input
              type="text"
              placeholder="Search interactions..." // Updated placeholder
              value={query}
              onChange={handleInputChange}
              onFocus={handleFocus}
              // Close dropdown on blur after a short delay to allow click
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

        {/* Dropdown rendering logic remains identical */}
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
                        layout // Ensures smooth animation on filter changes
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
                      No interactions found {/* Updated text */}
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
