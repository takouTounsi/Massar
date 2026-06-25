import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { confirm2FA, disable2FA, setup2FA } from "../api/auth";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { useAuth } from "../hooks/useAuth";
import { useI18n } from "../i18n/useI18n";

export function SecuritySettingsPage() {
  const auth = useAuth();
  const { t } = useI18n();
  const [setup, setSetup] = useState<{ otpauth_uri: string; secret: string } | null>(null);
  const [setupCode, setSetupCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSettingUp, setIsSettingUp] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [isDisabling, setIsDisabling] = useState(false);

  if (auth.isLoading) return <LoadingState />;

  const isEnabled = Boolean(auth.user?.two_factor_enabled);
  const status = isEnabled ? t("security.enabled") : setup ? t("security.inSetup") : t("security.disabled");

  return (
    <section className="grid max-w-3xl gap-4">
      <div>
        <h2 className="text-2xl font-semibold text-ink-900">{t("security.title")}</h2>
        <p className="text-sm text-ink-500">{t("security.subtitle")}</p>
      </div>
      {error ? <ErrorState message={error} /> : null}
      {message ? <div className="panel border-evidence-200 bg-evidence-50 p-4 text-sm text-evidence-700">{message}</div> : null}
      <div className="panel p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="font-semibold text-ink-900">{t("security.2faTitle")}</h3>
            <p className="text-sm text-ink-500">{t("security.status", { status })}</p>
          </div>
          <button
            className="btn btn-primary"
            disabled={isEnabled || Boolean(setup) || isSettingUp}
            onClick={() => {
              setError(null);
              setMessage(null);
              setIsSettingUp(true);
              setup2FA()
                .then((data) => {
                  setSetup(data);
                  setSetupCode("");
                })
                .catch((err) => setError(err instanceof Error ? err.message : t("security.activationFailed")))
                .finally(() => setIsSettingUp(false));
            }}
          >
            {isEnabled ? t("security.enabledButton") : setup ? t("security.qrGenerated") : t("security.enable2fa")}
          </button>
        </div>
        {setup ? (
          <div className="mt-4 rounded-md border border-navy-100 p-4">
            <div className="grid gap-4 md:grid-cols-[220px_1fr]">
              <div className="rounded-md border border-navy-100 bg-white p-3">
                <QRCodeSVG
                  value={setup.otpauth_uri}
                  size={188}
                  level="M"
                  includeMargin
                  className="h-auto w-full"
                  role="img"
                  aria-label="QR code 2FA Massar"
                />
              </div>
              <div className="grid content-start gap-3">
                <div>
                  <p className="font-medium text-ink-900">{t("security.scanQr")}</p>
                  <p className="mt-1 text-sm text-ink-500">{t("security.scanQrHint")}</p>
                </div>
                <details className="rounded-md border border-navy-100 p-3">
                  <summary className="cursor-pointer text-sm font-medium text-ink-700">{t("security.manualKey")}</summary>
                  <code className="mt-3 block break-all rounded bg-navy-50 p-2 text-sm">{setup.secret}</code>
                  <code className="mt-2 block break-all rounded bg-navy-50 p-2 text-xs">{setup.otpauth_uri}</code>
                </details>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <input
                className="input max-w-40"
                inputMode="numeric"
                value={setupCode}
                onChange={(event) => setSetupCode(event.target.value)}
                placeholder="123456"
              />
              <button
                className="btn btn-primary"
                disabled={isConfirming || setupCode.trim().length < 6}
                onClick={() => {
                  setError(null);
                  setMessage(null);
                  setIsConfirming(true);
                  confirm2FA(setupCode)
                    .then(() => {
                      setMessage(t("security.activated"));
                      setSetup(null);
                      setSetupCode("");
                      auth.meQuery.refetch();
                    })
                    .catch((err) => setError(err instanceof Error ? err.message : t("auth.invalidCode")))
                    .finally(() => setIsConfirming(false));
                }}
              >
                {t("common.confirm")}
              </button>
            </div>
          </div>
        ) : null}
      </div>
      {isEnabled ? (
        <div className="panel p-5">
          <h3 className="font-semibold text-ink-900">{t("security.disableTitle")}</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            <input
              className="input max-w-40"
              inputMode="numeric"
              value={disableCode}
              onChange={(event) => setDisableCode(event.target.value)}
              placeholder="123456"
            />
            <button
              className="btn btn-secondary"
              disabled={isDisabling || disableCode.trim().length < 6}
              onClick={() => {
                setError(null);
                setMessage(null);
                setIsDisabling(true);
                disable2FA(disableCode)
                  .then(() => {
                    setMessage(t("security.deactivated"));
                    setDisableCode("");
                    auth.meQuery.refetch();
                  })
                  .catch((err) => setError(err instanceof Error ? err.message : t("security.disableFailed")))
                  .finally(() => setIsDisabling(false));
              }}
            >
              {t("security.disableTitle")}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}