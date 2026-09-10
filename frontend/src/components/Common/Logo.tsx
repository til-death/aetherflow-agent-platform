import { Link } from "@tanstack/react-router"
import { Network } from "lucide-react"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({ variant = "full", className, asLink = true }: LogoProps) {
  const mark = (
    <div className={cn("flex items-center gap-3 text-foreground", variant === "icon" ? "justify-center" : "", className)}>
      <span className="flex size-10 items-center justify-center rounded-full border border-primary/25 bg-secondary text-primary shadow-[0_8px_20px_rgba(0,107,255,0.12)] group-data-[collapsible=icon]:size-9">
        <Network className="size-5" />
      </span>
      {variant !== "icon" ? <span className="text-xl font-bold tracking-tight text-primary group-data-[collapsible=icon]:hidden">AetherFlow</span> : null}
    </div>
  )

  if (!asLink) return mark
  return <Link to="/">{mark}</Link>
}