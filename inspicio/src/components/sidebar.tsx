import {
    Sidebar,
    SidebarContent,
    SidebarGroup,
    SidebarGroupContent,
    SidebarGroupLabel,
    SidebarMenu,
    SidebarMenuButton,
    SidebarMenuItem,
    SidebarTrigger,
    SidebarHeader,
} from "@/components/ui/sidebar"
import { useNavigate } from "react-router-dom"
import { Brain, Globe, Bot, Cpu, Code, Users } from "lucide-react"

const agentDomains = [
    {
        title: "SOTOPIA",
        icon: Users,
        route: "/sotopia"
    },
    {
        title: "WEBARENA",
        icon: Globe,
        route: "/webarena"
    },
    {
        title: "WEBVOYAGER",
        icon: Bot,
        route: "/webvoyager"
    },
    {
        title: "BABA AI",
        icon: Brain,
        route: null
    },
    {
        title: "BALROG",
        icon: Cpu,
        route: null
    },
    {
        title: "COLLABORATIVE GYM",
        icon: Code,
        route: null
    },
]

export function AppSidebar() {
    const navigate = useNavigate()

    return (
        <Sidebar collapsible="icon">
            <SidebarHeader>
                <SidebarTrigger />
            </SidebarHeader>
            <SidebarContent>
                <SidebarGroup>
                    <SidebarGroupLabel>Agent Domains</SidebarGroupLabel>
                    <SidebarGroupContent>
                        <SidebarMenu>
                            {agentDomains.map((domain) => (
                                <SidebarMenuItem key={domain.title}>
                                    <SidebarMenuButton
                                        asChild={!!domain.route}
                                        onClick={!domain.route ? undefined : () => navigate(domain.route!)}
                                    >
                                        {domain.route ? (
                                            <a href={domain.route} className="flex items-center gap-2">
                                                <domain.icon className="h-4 w-4 shrink-0" />
                                                <span className="group-data-[collapsed=true]:hidden">{domain.title}</span>
                                            </a>
                                        ) : (
                                            <div className="flex items-center gap-2 opacity-50">
                                                <domain.icon className="h-4 w-4 shrink-0" />
                                                <span className="group-data-[collapsed=true]:hidden">{domain.title}</span>
                                            </div>
                                        )}
                                    </SidebarMenuButton>
                                </SidebarMenuItem>
                            ))}
                        </SidebarMenu>
                    </SidebarGroupContent>
                </SidebarGroup>
            </SidebarContent>
        </Sidebar>
    )
}