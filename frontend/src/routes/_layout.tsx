import { createFileRoute, Link, Outlet, redirect } from "@tanstack/react-router"
import { Plus } from "lucide-react"

import AppSidebar from "@/components/Sidebar/AppSidebar"
import { Button } from "@/components/ui/button"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({
        to: "/login",
      })
    }
  },
})

function Layout() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center justify-between gap-3 border-b bg-background/95 px-4 backdrop-blur md:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <SidebarTrigger className="-ml-1 text-muted-foreground" />
            <div className="hidden min-w-0 items-center gap-2 md:flex">
              <span className="size-2 rounded-full bg-emerald-500" />
              <span className="truncate text-sm font-bold text-foreground">AetherFlow 工作台</span>
              <span className="rounded-full border bg-card px-2.5 py-1 text-xs font-semibold text-muted-foreground">企业任务处理</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 text-xs text-muted-foreground lg:flex">
              <span className="size-1.5 rounded-full bg-emerald-500" />
              <span>处理服务在线</span>
            </div>
            <Button asChild size="sm">
              <Link to="/"><Plus className="size-4" />开始新任务</Link>
            </Button>
          </div>
        </header>
        <main className="flex-1 px-5 py-8 md:px-10 md:py-12">
          <div className="mx-auto max-w-[1380px]">
            <Outlet />
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}

export default Layout

