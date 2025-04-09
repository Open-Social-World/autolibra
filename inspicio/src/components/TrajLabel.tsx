import { InteractiveHoverButton } from "@/registry/magicui/interactive-hover-button";
import { ReactNode } from "react";

interface TrajLabelProps {
  title: string;
  subtitle1?: string;
  subtitle2?: string;
  children?: ReactNode;
  onClick?: () => void;
  maxWidth?: string;
}

export function TrajLabel({ 
  title, 
  subtitle1, 
  subtitle2, 
  children, 
  onClick,
  maxWidth = "100%" 
}: TrajLabelProps) {
  return (
    <InteractiveHoverButton onClick={onClick} className="flex flex-col items-center p-4 w-full">
      <div className="w-full text-center" style={{ maxWidth }}>
        <h2 className="text-xl font-bold mb-1 truncate" title={title}>{title}</h2>
        {subtitle1 && <p className="text-sm mb-0.5 truncate" title={subtitle1}>{subtitle1}</p>}
        {subtitle2 && <p className="text-sm truncate" title={subtitle2}>{subtitle2}</p>}
        {children}
      </div>
    </InteractiveHoverButton>
  );
}

// Example usage (can be removed if not needed)
export function TrajLabelDemo() {
  return (
    <TrajLabel 
      title="Main Title" 
      subtitle1="First subtitle text" 
      subtitle2="Second subtitle text"
      maxWidth="300px"
    >
      Additional content can go here
    </TrajLabel>
  );
}

