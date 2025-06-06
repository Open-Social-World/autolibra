import React from 'react';
import { Button } from "../../components/ui/button";
import { Users, Calendar } from 'lucide-react';
import { cn } from '../../lib/utils';

interface LabeledButtonProps {
  id: string;
  topic: string; 
  agents?: string; 
  date?: string;  
  selected?: boolean;
  onClick: (id: string) => void;
}

export function LabeledButton({ id, topic, agents, date, selected, onClick }: LabeledButtonProps) {
  return (
    <div className="w-full">
      <Button
        variant={selected ? "default" : "outline"}
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
