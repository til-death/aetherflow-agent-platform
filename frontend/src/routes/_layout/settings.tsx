import { createFileRoute } from "@tanstack/react-router"

import ChangePassword from "@/components/UserSettings/ChangePassword"
import DeleteAccount from "@/components/UserSettings/DeleteAccount"
import UserInformation from "@/components/UserSettings/UserInformation"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"

const tabsConfig = [
  { value: "my-profile", title: "My profile", component: UserInformation },
  { value: "password", title: "Password", component: ChangePassword },
  { value: "danger-zone", title: "Danger zone", component: DeleteAccount },
]

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
  head: () => ({
    meta: [
      {
        title: "Settings - AetherFlow",
      },
    ],
  }),
})

function UserSettings() {
  const { user: currentUser } = useAuth()

  if (!currentUser) {
    return null
  }

  const finalTabs = tabsConfig

  return (
    <div className="page-shell">
      <div>
        <div className="page-kicker">Account</div>
        <h1 className="page-title text-3xl md:text-4xl">User settings</h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
          Manage your AetherFlow account settings and preferences
        </p>
      </div>

      <Tabs defaultValue="my-profile">
        <TabsList>
          {finalTabs.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.title}
            </TabsTrigger>
          ))}
        </TabsList>

        {finalTabs.map((tab) => {
          const TabComponent = tab.component

          return (
            <TabsContent key={tab.value} value={tab.value}>
              <TabComponent />
            </TabsContent>
          )
        })}
      </Tabs>
    </div>
  )
}