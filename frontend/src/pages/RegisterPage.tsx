import { Compass } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AuthBrandPanel } from "../components/AuthBrandPanel";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { useAuth } from "../hooks/useAuth";
import { useI18n } from "../i18n/useI18n";

export function RegisterPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const { t } = useI18n();
  const [error, setError] = useState<string | null>(null);

  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      {/* ── Left panel — brand story (shared with Login) ── */}
      <AuthBrandPanel
        headline={t("auth.registerHeadline")}
        subhead={t("auth.registerSubhead")}
      />

      {/* ── Right panel — register form ── */}
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
          <p className="overline mb-2">{t("auth.registerEyebrow")}</p>
          <h2
            className="text-2xl font-medium text-ink-900"
            style={{ letterSpacing: "-0.01em" }}
          >
            {t("auth.registerTitle")}
          </h2>
          <p className="text-sm text-ink-500 mt-1">{t("auth.registerHint")}</p>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-flag-100 bg-flag-50 px-4 py-3">
            <p className="text-sm text-flag-700">{error}</p>
          </div>
        )}

        <form
          className="flex flex-col gap-5"
          onSubmit={(event) => {
            event.preventDefault();
            setError(null);
            const form = new FormData(event.currentTarget);
            auth.registerMutation.mutate(
              {
                email: String(form.get("email")),
                full_name: String(form.get("full_name")),
                password: String(form.get("password")),
              },
              {
                onSuccess: () => navigate("/login"),
                onError: (err) =>
                  setError(
                    err instanceof Error
                      ? err.message
                      : t("auth.registerFailed"),
                  ),
              },
            );
          }}
        >
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-ink-700">
              {t("auth.fullName")}
            </span>
            <input
              className="input"
              name="full_name"
              defaultValue="Founder Demo"
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-ink-700">
              {t("auth.email")}
            </span>
            <input
              className="input"
              name="email"
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
              type="password"
              placeholder={t("auth.passwordPlaceholder")}
            />
          </label>

          <button
            className="btn btn-primary mt-1 w-full py-3"
            disabled={auth.registerMutation.isPending}
          >
            {auth.registerMutation.isPending
              ? t("auth.creatingAccount")
              : t("auth.createAccount")}
          </button>
        </form>

        <p className="mt-8 text-sm text-ink-400">
          {t("auth.alreadyRegistered")}{" "}
          <Link
            className="font-semibold text-navy-700 hover:text-navy-600"
            to="/login"
          >
            {t("auth.signIn")}
          </Link>
        </p>
      </div>
    </main>
  );
}
