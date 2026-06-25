import { useMutation } from "@tanstack/react-query";
import { Rocket } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { createProject } from "../api/projects";
import { useI18n } from "../i18n/useI18n";

export function NewProjectPage() {
  const navigate = useNavigate();
  const { t, label } = useI18n();
  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: (project) => navigate(`/projects/${project.project_id}/intake`)
  });

  return (
    <section className="panel max-w-2xl p-5">
      <div className="mb-5 flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-lg bg-flag-600 text-white">
          <Rocket size={20} />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-ink-900">{t("project.newTitle")}</h2>
          <p className="text-sm text-ink-500">{t("project.newSubtitle")}</p>
        </div>
      </div>
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          mutation.mutate({
            country: form.get("country"),
            business_type: form.get("business_type"),
            declared_stage: form.get("declared_stage"),
            primary_goal: form.get("primary_goal"),
            sector: form.get("sector")
          });
        }}
      >
        <label className="grid gap-1 text-sm font-medium text-ink-700">
          {t("project.country")}
          <select className="input" name="country" defaultValue="TN">
            <option value="TN">{label("country", "TN")}</option>
            <option value="MA">{label("country", "MA")}</option>
            <option value="DZ">{label("country", "DZ")}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm font-medium text-ink-700">
          {t("project.businessType")}
          <select className="input" name="business_type" defaultValue="startup">
            <option value="startup">{label("businessType", "startup")}</option>
            <option value="traditional_business">{label("businessType", "traditional_business")}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm font-medium text-ink-700">
          {t("project.declaredStage")}
          <select className="input" name="declared_stage" defaultValue="FUNDRAISING">
            <option value="IDEATION">{label("stage", "IDEATION")}</option>
            <option value="MARKET_VALIDATION">{label("stage", "MARKET_VALIDATION")}</option>
            <option value="STRUCTURATION">{label("stage", "STRUCTURATION")}</option>
            <option value="FUNDRAISING">{label("stage", "FUNDRAISING")}</option>
            <option value="LAUNCH_PLANNING">{label("stage", "LAUNCH_PLANNING")}</option>
            <option value="GROWTH">{label("stage", "GROWTH")}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm font-medium text-ink-700">
          {t("project.goal")}
          <select className="input" name="primary_goal" defaultValue="funding">
            <option value="funding">{label("goal", "funding")}</option>
            <option value="public_procurement">{label("goal", "public_procurement")}</option>
            <option value="export">{label("goal", "export")}</option>
            <option value="growth">{label("goal", "growth")}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm font-medium text-ink-700">
          {t("project.sector")}
          <input className="input" name="sector" defaultValue="technology" />
        </label>
        <button className="btn btn-primary w-fit" disabled={mutation.isPending}>
          <Rocket size={16} /> {t("project.start")}
        </button>
      </form>
    </section>
  );
}