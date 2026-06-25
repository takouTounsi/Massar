import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { verify2FA } from "../api/auth";
import { ErrorState } from "../components/ErrorState";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { useI18n } from "../i18n/useI18n";

export function Verify2FAPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useI18n();
  const [error, setError] = useState<string | null>(null);
  const token = (location.state as { temporary_login_token?: string } | null)?.temporary_login_token ?? "";

  return (
    <main className="grid min-h-screen place-items-center bg-paper px-4">
      <div className="absolute end-4 top-4">
        <LanguageSwitcher />
      </div>
      <section className="panel w-full max-w-md p-6">
        <h1 className="text-xl font-semibold text-ink-900">{t("auth.verify2faTitle")}</h1>
        <p className="mt-1 text-sm text-ink-500">{t("auth.verify2faHint")}</p>
        {error ? <div className="mt-4"><ErrorState message={error} /></div> : null}
        <form
          className="mt-5 grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            const code = String(new FormData(event.currentTarget).get("code"));
            verify2FA({ temporary_login_token: token, code })
              .then(() => navigate("/dashboard"))
              .catch((err) => setError(err instanceof Error ? err.message : t("auth.invalidCode")));
          }}
        >
          <input className="input text-center text-xl tracking-widest" name="code" inputMode="numeric" placeholder="123456" />
          <button className="btn btn-primary">{t("common.confirm")}</button>
        </form>
      </section>
    </main>
  );
}