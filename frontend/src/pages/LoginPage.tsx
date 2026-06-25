import { Compass } from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AuthBrandPanel } from "../components/AuthBrandPanel";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { useAuth } from "../hooks/useAuth";
import { useI18n } from "../i18n/useI18n";

export function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useI18n();
  const [error, setError] = useState<string | null>(null);
  const from =
    (location.state as { from?: string } | null)?.from ?? "/dashboard";

  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      {/* ── Left panel — brand story (sovereign navy, mirrors the sidebar) ── */}
      <AuthBrandPanel
        headline={t("auth.loginHeadline")}
        subhead={t("auth.loginSubhead")}
      />

      {/* ── Right panel — login form ── */}
      <div className="flex flex-col justify-center bg-paper px-8 py-12 lg:px-12">
        <div className="absolute end-4 top-4">
          <LanguageSwitcher />
        </div>

        {/* Mobile logo */}
        <div className="flex items-center gap-3 mb-10 lg:hidden">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-flag-600">
            <Compass size={18} className="text-white" />
          </div>
          <span className="text-lg font-medium text-ink-900">MASSAR</span>
        </div>

        <div className="mb-8">
          <p className="overline mb-2">{t("auth.loginTitle")}</p>
          <h2
            className="text-2xl font-medium text-ink-900"
            style={{ letterSpacing: "-0.01em" }}
          >
            {t("auth.loginWelcome")}
          </h2>
          <p className="text-sm text-ink-500 mt-1">
            {t("auth.loginWelcomeSub")}
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-flag-100 bg-flag-50 px-4 py-3">
            <p className="text-sm text-flag-700">{error}</p>
          </div>
        )}

        <form
          className="flex flex-col gap-5"
          onSubmit={(e) => {
            e.preventDefault();
            setError(null);
            const form = new FormData(e.currentTarget);
            auth.loginMutation.mutate(
              {
                email: String(form.get("email")),
                password: String(form.get("password")),
              },
              {
                onSuccess: (res) => {
                  if (res.requires_2fa && res.temporary_login_token) {
                    navigate("/verify-2fa", {
                      state: {
                        temporary_login_token: res.temporary_login_token,
                      },
                    });
                    return;
                  }
                  navigate(from);
                },
                onError: (err) =>
                  setError(
                    err instanceof Error ? err.message : t("auth.loginFailed"),
                  ),
              },
            );
          }}
        >
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-ink-700">
              {t("auth.email")}
            </span>
            <input
              className="input"
              name="email"
              defaultValue="demo@massar.local"
              type="email"
              placeholder={t("auth.emailPlaceholder")}
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-ink-700">
              {t("auth.password")}
            </span>
            <input
              className="input"
              name="password"
              defaultValue="MassarDemo123!"
              type="password"
              placeholder="••••••••••"
            />
          </label>

          <button
            className="btn btn-primary mt-1 w-full py-3"
            disabled={auth.loginMutation.isPending}
          >
            {auth.loginMutation.isPending
              ? t("auth.signingIn")
              : t("auth.signIn")}
          </button>
        </form>

        {/* Demo shortcut */}
        <div className="mt-6 rounded-lg border border-navy-100 bg-white px-4 py-3">
          <p className="text-xs font-medium text-ink-700 mb-1">
            {t("auth.demoTitle")}
          </p>
          <p className="text-xs text-ink-500">
            demo@massar.local · MassarDemo123!
          </p>
        </div>

        <p className="mt-8 text-sm text-ink-400">
          {t("auth.noAccount")}{" "}
          <Link
            className="font-semibold text-navy-700 hover:text-navy-600"
            to="/register"
          >
            {t("auth.createAccount")}
          </Link>
        </p>
      </div>
    </main>
  );
}
