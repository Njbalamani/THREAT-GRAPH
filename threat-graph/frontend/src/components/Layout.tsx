import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { systemApi } from "../api";
import { useAuth } from "../auth";
import { formatDate } from "./UI";

const navigation = [
  { to: "/dashboard", label: "Dashboard", icon: "◧" },
  { to: "/ingestion", label: "Ingestion", icon: "⇩" },
  { to: "/indicators", label: "Indicators", icon: "◈" },
  { to: "/graph", label: "Graph Explorer", icon: "⌘" },
  { to: "/analytics", label: "Analytics & ML", icon: "◇" },
  { to: "/investigations", label: "Investigations", icon: "▤" },
  { to: "/feeds", label: "Feeds", icon: "⇄" },
  { to: "/reports", label: "Reports", icon: "▣" },
];

export function Layout() {
  const { user, logout, canWrite } = useAuth();
  const location = useLocation();
  const [health, setHealth] = useState<string>("checking");

  useEffect(() => {
    let mounted = true;
    systemApi
      .health()
      .then((result) => {
        if (mounted) setHealth(result.status);
      })
      .catch(() => {
        if (mounted) setHealth("offline");
      });
    return () => {
      mounted = false;
    };
  }, []);

  const current = navigation.find((item) => location.pathname.startsWith(item.to));
  const title = current?.label ?? "Dashboard";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__mark">TG</span>
          <div>
            <strong>THREATGRAPH</strong>
            <span>Attack relationship intelligence</span>
          </div>
        </div>
        <nav className="nav">
          {navigation.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav__item ${isActive ? "nav__item--active" : ""}`}>
              <span className="nav__icon">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__footer">
          <div className="api-status">
            <span className={`status-dot status-dot--${health}`} />
            <span>API {health}</span>
          </div>
          <span className="sidebar__role">{user?.role ?? "unauthenticated"}</span>
          {!canWrite && <span className="sidebar__hint">Read-only access</span>}
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div>
            <span className="topbar__eyebrow">Workspace</span>
            <h1>{title}</h1>
          </div>
          <div className="topbar__right">
            <div className="user-chip">
              <span className="avatar">{(user?.full_name ?? "TG").slice(0, 2).toUpperCase()}</span>
              <div>
                <strong>{user?.full_name ?? "Unknown user"}</strong>
                <span>{user?.email ?? ""}</span>
              </div>
            </div>
            <button type="button" className="button button--ghost" onClick={logout}>
              Sign out
            </button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>THREATGRAPH v1.0.0</span>
          <span>Session started {formatDate(user?.created_at)}</span>
          <span>Model predictions are advisory and are not confirmed attacks.</span>
        </footer>
      </div>
    </div>
  );
}

export function useCurrentTitle(): string {
  const location = useLocation();
  const current = useMemo(() => navigation.find((item) => location.pathname.startsWith(item.to)), [location.pathname]);
  return current?.label ?? "Dashboard";
}
