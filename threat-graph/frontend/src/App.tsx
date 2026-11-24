import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Loading } from "./components/UI";
import { useAuth } from "./auth";
import { Analytics } from "./pages/Analytics";
import { Dashboard } from "./pages/Dashboard";
import { Feeds } from "./pages/Feeds";
import { GraphExplorer } from "./pages/GraphExplorer";
import { Indicators } from "./pages/Indicators";
import { Ingestion } from "./pages/Ingestion";
import { Investigations } from "./pages/Investigations";
import { Login } from "./pages/Login";
import { Reports } from "./pages/Reports";
import type { ReactNode } from "react";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  if (!ready) return <Loading label="Restoring session…" />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export function App() {
  const { user, ready } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={ready && user ? <Navigate to="/dashboard" replace /> : <Login />}
      />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/ingestion" element={<Ingestion />} />
        <Route path="/indicators" element={<Indicators />} />
        <Route path="/graph" element={<GraphExplorer />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/investigations" element={<Investigations />} />
        <Route path="/feeds" element={<Feeds />} />
        <Route path="/reports" element={<Reports />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
