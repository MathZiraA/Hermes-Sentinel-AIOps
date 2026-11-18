import { Link, useRouterState } from "@tanstack/react-router";
import { useState, type ComponentType, type ReactNode } from "react";
import {
  Activity,
  BarChart3,
  Brain,
  Building2,
  LayoutDashboard,
  Languages,
  LogOut,
  Menu,
  Moon,
  ScrollText,
  Server,
  ShieldAlert,
  Sun,
  UserCog,
  Users,
} from "lucide-react";
import { Logo } from "@/components/brand/Logo";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useAuth, type Permission } from "@/lib/auth/auth";
import { useI18n, type MessageKey } from "@/lib/i18n/i18n";
import { useTelemetry } from "@/lib/sentinel/telemetry";
import { useTheme } from "@/lib/theme/theme";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: MessageKey;
  icon: ComponentType<{ className?: string }>;
  permission?: Permission;
}

const SECTIONS: { title: MessageKey; items: NavItem[] }[] = [
  {
    title: "nav.section.operate",
    items: [
      { to: "/", label: "nav.overview", icon: LayoutDashboard },
      { to: "/incidents", label: "nav.incidents", icon: ShieldAlert, permission: "incidents:read" },
      { to: "/clusters", label: "nav.clusters", icon: Server, permission: "clusters:read" },
      { to: "/war-room", label: "nav.warRoom", icon: Building2, permission: "incidents:read" },
      { to: "/brain", label: "nav.brain", icon: Brain, permission: "brain:read" },
    ],
  },
  {
    title: "nav.section.govern",
    items: [
      { to: "/reports", label: "nav.reports", icon: BarChart3, permission: "reports:read" },
      { to: "/audit", label: "nav.audit", icon: ScrollText, permission: "audit:read" },
    ],
  },
  {
    title: "nav.section.admin",
    items: [
      { to: "/admin/users", label: "nav.users", icon: Users, permission: "users:manage" },
      { to: "/admin/teams", label: "nav.teams", icon: UserCog, permission: "teams:manage" },
    ],
  },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const { can } = useAuth();
  const { t } = useI18n();
  const path = useRouterState({ select: (s) => s.location.pathname });
  return (
    <nav aria-label="Principal" className="flex flex-col gap-5">
      {SECTIONS.map((section) => {
        const items = section.items.filter((i) => !i.permission || can(i.permission));
        if (!items.length) return null;
        return (
          <div key={section.title}>
            <p className="px-3 pb-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              {t(section.title)}
            </p>
            <ul className="flex flex-col gap-0.5">
              {items.map(({ to, label, icon: Icon }) => {
                const active = to === "/" ? path === "/" : path === to || path.startsWith(`${to}/`);
                return (
                  <li key={to}>
                    <Link
                      to={to}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
                        active
                          ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                          : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      {t(label)}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

function UserFooter() {
  const { user, logout } = useAuth();
  const { t } = useI18n();
  if (!user) return null;
  return (
    <div className="flex items-center gap-2 border-t border-sidebar-border pt-3">
      <Link
        to="/account"
        className="flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-sidebar-accent/60"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
          {user.name.slice(0, 2).toUpperCase()}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-foreground">{user.name}</span>
          <span className="block truncate text-xs text-muted-foreground">{user.roleLabel}</span>
        </span>
      </Link>
      <button
        type="button"
        onClick={() => void logout()}
        aria-label={t("top.logout")}
        title={t("top.logout")}
        className="rounded-md p-2 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
      >
        <LogOut className="h-4 w-4" />
      </button>
    </div>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 bg-sidebar px-3 py-5">
      <div className="px-2">
        <Logo />
      </div>
      <div className="flex-1 overflow-y-auto">
        <NavLinks {...(onNavigate ? { onNavigate } : {})} />
      </div>
      <UserFooter />
    </div>
  );
}

function TopBar({ onMenu }: { onMenu: () => void }) {
  const { theme, toggle } = useTheme();
  const { locale, setLocale, t } = useI18n();
  const { connection, approvals } = useTelemetry();
  const pending = Object.keys(approvals).length;
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-background/85 px-4 backdrop-blur sm:px-6">
      <button
        type="button"
        onClick={onMenu}
        aria-label={t("top.menu")}
        className="-ml-1 rounded-md p-2 text-muted-foreground hover:bg-accent lg:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Activity
          className={cn("h-3.5 w-3.5", connection === "open" ? "text-success" : "text-sev2")}
          aria-hidden
        />
        <span>{connection === "open" ? t("top.live") : t("top.offline")}</span>
      </div>
      {pending > 0 && (
        <Link
          to="/incidents"
          search={{ status: "waiting_approval" }}
          className="flex items-center gap-1.5 rounded-full bg-sev3/20 px-2.5 py-1 text-xs font-medium text-foreground hover:bg-sev3/30"
        >
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sev3" />
          {pending} {t("top.pending")}
        </Link>
      )}
      <div className="ml-auto flex items-center gap-1">
        <button
          type="button"
          onClick={() => setLocale(locale === "pt" ? "en" : "pt")}
          aria-label={t("top.language")}
          title={t("top.language")}
          className="flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          <Languages className="h-4 w-4" aria-hidden />
          {locale.toUpperCase()}
        </button>
        <button
          type="button"
          onClick={toggle}
          aria-label={t("top.theme")}
          title={t("top.theme")}
          className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </header>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  // A sala de guerra ocupa a tela inteira (cena isométrica); as outras páginas usam a largura de leitura.
  const fullBleed = useRouterState({ select: (s) => s.location.pathname === "/war-room" });
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r border-sidebar-border lg:block">
        <Sidebar />
      </aside>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="w-72 border-sidebar-border p-0">
          <SheetTitle className="sr-only">Menu</SheetTitle>
          <Sidebar onNavigate={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onMenu={() => setOpen(true)} />
        <main
          className={cn(
            "flex-1",
            fullBleed
              ? "h-[calc(100vh-3.5rem)] overflow-hidden"
              : "mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8",
          )}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
