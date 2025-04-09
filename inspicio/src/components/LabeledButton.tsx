import { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Users, Calendar } from 'lucide-react';

interface LabeledButtonProps {
  id: string;
  topic: string;
  agents?: string;
  date?: string;
  isSelected?: boolean;
  onClick: (id: string) => void;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  className?: string;
}

export function LabeledButton({
  id,
  topic,
  agents,
  date,
  isSelected = false,
  onClick,
  leftIcon,
  rightIcon,
  className = "",
}: LabeledButtonProps) {
  return (
    <Button
      variant={isSelected ? "default" : "outline"}
      className={`w-full justify-start text-left font-normal h-auto py-3 flex flex-col items-start ${className}`}
      onClick={() => onClick(id)}
    >
      <div className="flex w-full items-center gap-2">
        {leftIcon && <div className="flex-shrink-0">{leftIcon}</div>}
        <div className="flex-grow min-w-0">
          <div className="text-base font-medium mb-1 w-full truncate" title={topic}>
            {topic}
          </div>
          <div className="flex w-full text-xs text-muted-foreground gap-2">
            {agents && (
              <div className="flex items-center truncate" title={agents}>
                <Users className="mr-1 h-3 w-3" />
                <span>{agents}</span>
              </div>
            )}
            {date && (
              <div className="flex items-center truncate" title={date}>
                <Calendar className="mr-1 h-3 w-3" />
                <span>{date}</span>
              </div>
            )}
          </div>
        </div>
        {rightIcon && <div className="flex-shrink-0">{rightIcon}</div>}
      </div>
    </Button>
  );
} 