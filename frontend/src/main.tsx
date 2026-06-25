import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { RouteErrorBoundary } from "./components/RouteErrorBoundary";
import { AuthProvider } from "./hooks/useAuth";
import { I18nProvider } from "./i18n/I18nProvider";
import { DashboardPage } from "./pages/DashboardPage";
import { HomeDashboardPage } from "./pages/HomeDashboardPage";
import { ProjectIntakeFlow } from "./pages/ProjectIntakeFlow";
import { IntelligencePage } from "./pages/IntelligencePage";
import { JourneyPage } from "./pages/JourneyPage";
import { LoginPage } from "./pages/LoginPage";
import { NewProjectPage } from "./pages/NewProjectPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ResourcesPage } from "./pages/ResourcesPage";
import { RoadmapPage } from "./pages/RoadmapPage";
import { ScoresPage } from "./pages/ScoresPage";
import { SecuritySettingsPage } from "./pages/SecuritySettingsPage";
import { Verify2FAPage } from "./pages/Verify2FAPage";
import "./styles.css";

const queryClient = new QueryClient();

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  { path: "/verify-2fa", element: <Verify2FAPage /> },
  {
    path: "/",
    element: <ProtectedRoute />,
    errorElement: <RouteErrorBoundary />,
    children: [
      {
        element: <AppLayout />,
        errorElement: <RouteErrorBoundary />,
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          { path: "dashboard", element: <HomeDashboardPage /> },
          { path: "projects/new", element: <NewProjectPage /> },
          { path: "projects/:projectId/intake", element: <ProjectIntakeFlow /> },
          { path: "projects/:projectId/dashboard", element: <DashboardPage /> },
          { path: "projects/:projectId/scores", element: <ScoresPage /> },
          { path: "projects/:projectId/roadmap", element: <RoadmapPage /> },
          { path: "projects/:projectId/resources", element: <ResourcesPage /> },
          { path: "projects/:projectId/intelligence", element: <IntelligencePage /> },
          { path: "projects/:projectId/journey", element: <JourneyPage /> },
          { path: "settings/security", element: <SecuritySettingsPage /> }
        ]
      }
    ]
  }
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <I18nProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>
    </I18nProvider>
  </React.StrictMode>
);