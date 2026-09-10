import { Activity, FlaskConical, Home, LayoutDashboard, Users, Workflow, Wrench } from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, Main } from "./Main"
import { User } from "./User"

const workspaceItems: Item[] = [
  { icon: Home, title: "工作台", path: "/" },
  { icon: Workflow, title: "任务列表", path: "/tasks" },
  { icon: Activity, title: "处理记录", path: "/runs" },
]

const engineeringItems: Item[] = [
  { icon: Wrench, title: "工具管理", path: "/tools" },
  { icon: FlaskConical, title: "可靠性评估", path: "/evaluation" },
]

export function AppSidebar() {
  const { user: currentUser } = useAuth()
  const isAdmin = Boolean(currentUser?.is_superuser)
  const operationsItems: Item[] = isAdmin ? [{ icon: LayoutDashboard, title: "运营总览", path: "/operations" }] : []
  const adminItems: Item[] = isAdmin ? [{ icon: Users, title: "成员管理", path: "/admin" }] : []
  const internalItems = isAdmin ? [...operationsItems, ...engineeringItems] : []
  const compactItems = [...workspaceItems, ...internalItems, ...adminItems]

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-6 py-7 group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-0">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent className="gap-6 px-3">
        <div className="group-data-[collapsible=icon]:hidden">
          <div className="mb-3 px-3 text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">我的工作</div>
          <Main items={workspaceItems} />
          {isAdmin ? <>
            <div className="mb-3 mt-7 px-3 text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">管理中心</div>
            <Main items={operationsItems} />
            <div className="mb-3 mt-7 px-3 text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">工程设置</div>
            <Main items={engineeringItems} />
            <div className="mb-3 mt-7 px-3 text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">系统管理</div>
            <Main items={adminItems} />
          </> : null}
        </div>
        <div className="hidden group-data-[collapsible=icon]:block">
          <Main items={compactItems} />
        </div>
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border/80 p-3">
        <SidebarAppearance />
        <div className="group-data-[collapsible=icon]:hidden">
          <div className="mb-2 px-3 text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">账户</div>
        </div>
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
