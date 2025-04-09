import { ReactNode } from 'react';
import { Button } from "@/components/ui/button";
import {
    Briefcase as BriefcaseIcon,
    Calendar as CalendarIcon,
    Check as CheckIcon,
    ChevronDown as ChevronDownIcon,
    DollarSign as CurrencyDollarIcon,
    Link as LinkIcon,
    MapPin as MapPinIcon,
    Pencil as PencilIcon,
    User as UserIcon,
    LucideIcon
  } from 'lucide-react'
  import { Menu, MenuButton, MenuItem, MenuItems } from '@headlessui/react'
  
  interface HeaderProps {
    title?: string;
    subtitle1?: string;
    subtitle2?: string;
    subtitle1Icon?: ReactNode;
    subtitle2Icon?: ReactNode;
    actionLabel?: string;
    onAction?: () => void;
    children?: ReactNode;
    showIcons?: boolean;
    className?: string;
    logo?: string;
  }
  
  export function Header({
    title,
    subtitle1,
    subtitle2,
    subtitle1Icon,
    subtitle2Icon,
    actionLabel,
    onAction,
    children,
    showIcons = true,
    className = "mb-4",
    logo
  }: HeaderProps) {
    return (
      <div className={`flex flex-col md:flex-row md:items-center md:justify-between ${className}`}>
        <div className="min-w-0 flex-1">
          <div className="flex items-center">
            {logo ? (
              <img src={logo} alt={title || "Logo"} className="h-10" />
            ) : (
              <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                {title}
              </h1>
            )}
          </div>
          {(subtitle1 || subtitle2) && (
            <div className="mt-2 flex flex-col sm:flex-row sm:flex-wrap sm:space-x-6">
              {subtitle1 && (
                <div className="mt-1 flex items-center text-sm text-muted-foreground">
                  {showIcons && (subtitle1Icon || <UserIcon className="mr-1.5 h-4 w-4 text-muted-foreground" />)}
                  {subtitle1}
                </div>
              )}
              {subtitle2 && (
                <div className="mt-1 flex items-center text-sm text-muted-foreground">
                  {showIcons && (subtitle2Icon || <CalendarIcon className="mr-1.5 h-4 w-4 text-muted-foreground" />)}
                  {subtitle2}
                </div>
              )}
            </div>
          )}
        </div>
        
        {(actionLabel || children) && (
          <div className="mt-4 flex md:mt-0 md:ml-4">
            {children}
            
            {actionLabel && onAction && (
              <Button onClick={onAction}>
                {actionLabel}
              </Button>
            )}
          </div>
        )}
      </div>
    );
  }
  