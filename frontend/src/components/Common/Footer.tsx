export function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="border-t px-6 py-4">
      <div className="flex items-center justify-center text-sm text-muted-foreground sm:justify-between">
        <span>AetherFlow Enterprise Agent Platform - {currentYear}</span>
        <span className="hidden sm:inline">场景路由、Trace 回放、失败恢复、运行评估</span>
      </div>
    </footer>
  )
}
