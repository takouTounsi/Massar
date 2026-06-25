import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useI18n } from "../i18n/useI18n";
import { LoadingState } from "./LoadingState";

export function ProtectedRoute() {
  const auth = useAuth();
  const location = useLocation();
  const { t } = useI18n();

  // "unknown" → still restoring the session on boot: show a loader, never
  // redirect. Only a settled "unauthenticated" sends the user to /login.
  if (auth.status === "unknown") {
    return <LoadingState label={t("common.loading")} />;
  }
  if (auth.status === "unauthenticated") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}