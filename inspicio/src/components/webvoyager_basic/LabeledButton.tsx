import React from 'react';
import { Button } from "../ui/button";
import { Users, Calendar } from 'lucide-react'; // Keep icons
import { cn } from '../../lib/utils'; // Keep utility

interface LabeledButtonProps {
  id: string;
  topic: string; 
  agents?: string; 
  date?: string;  
  isSelected?: boolean;
  onClick: (id: string) => void;
}

export function LabeledButton({ id, topic, agents, date, isSelected, onClick }: LabeledButtonProps) {
  return (
    <div className="w-full">
      <Button
        variant={isSelected ? "default" : "outline"}
        className={cn(
          "w-full justify-start text-left font-normal h-auto py-3 px-4",
          "hover:bg-accent hover:text-accent-foreground", 
        )}
        onClick={() => onClick(id)}
      >
        <div className="flex flex-col gap-1 w-full overflow-hidden">
          {/* Display topic */}
          <div className="text-base font-medium truncate">{topic}</div>

          {/* Conditionally display agents/roles if provided */}
          {agents && (
            <div className="flex items-center text-sm text-muted-foreground">
              <Users className="mr-1 h-3 w-3" />
              <span className="truncate">{agents}</span>
            </div>
          )}

          {/* Conditionally display date if provided */}
          {date && (
            <div className="flex items-center text-sm text-muted-foreground">
              <Calendar className="mr-1 h-3 w-3" />
              <span>{date}</span>
            </div>
          )}
        </div>
      </Button>
    </div>
  );
}
