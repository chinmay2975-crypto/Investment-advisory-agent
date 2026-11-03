import {
  Activity,
  BookOpen,
  Briefcase,
  GitCompare,
  Globe,
  LayoutDashboard,
  LogOut,
  type LucideIcon,
  MessageSquareText,
  Receipt,
  RefreshCcw,
  Target,
  UserRound,
} from "lucide-react";
import { Suspense } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useProfile } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import { GENERAL_NOTICE } from "@/components/Disclaimer";
import { LoadingCards } from "@/components/StateViews";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV: { to: string; label: string; icon: LucideIcon }[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/portfolio", label: "Portfolio", icon: Briefcase },
  { to: "/advice", label: "Advice", icon: MessageSquareText },
  { to: "/recommendations", label: "Suggestions", icon: BookOpen },
  { to: "/goals", label: "Goals", icon: Target },
  { to: "/scenarios", label: "Scenarios", icon: GitCompare },
  { to: "/tax", label: "Tax notes", icon: Receipt },
  { to: "/market", label: "Market data", icon: Globe },
  { to: "/self-assessment", label: "Self-assessment", icon: RefreshCcw },
  { to: "/onboarding", label: "Profile & country", icon: UserRound },
];

export function Layout() {
  const { logout, investorId } = useAuth();
  const profile = useProfile();
  const country = profile.data?.country;

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r bg-card md:flex">
        <div className="flex items-center gap-2 px-5 py-5 text-lg font-semibold">
          <Activity className="size-5 text-primary" /> InvestAd
        </div>
        <nav className="flex-1 space-y-0.5 px-3">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                  isActive && "bg-primary/10 font-medium text-primary",
                )
              }
            >
              <Icon className="size-4" /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t p-3">
          <div className="mb-2 px-2 text-xs text-muted-foreground">Investor #{investorId}</div>
          <Button variant="ghost" size="sm" className="w-full justify-start" onClick={logout}>
            <LogOut /> Log out
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b bg-background/80 px-6 py-3 backdrop-blur">
          <nav className="flex gap-1 overflow-x-auto md:hidden">
            {NAV.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn("whitespace-nowrap rounded-md px-2 py-1 text-xs", isActive ? "bg-primary/10 text-primary" : "text-muted-foreground")
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2 text-sm">
            {country ? (
              <Badge variant="secondary">
                {country} · {profile.data?.base_currency ?? "auto currency"}
              </Badge>
            ) : (
              <Badge variant="outline">Country: auto-detect</Badge>
            )}
            <Button variant="ghost" size="icon" className="md:hidden" onClick={logout} aria-label="Log out">
              <LogOut />
            </Button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">
          <Suspense fallback={<LoadingCards />}>
            <Outlet />
          </Suspense>
        </main>
        <footer className="border-t px-6 py-4 text-center text-xs text-muted-foreground">{GENERAL_NOTICE}</footer>
      </div>
    </div>
  );
}
