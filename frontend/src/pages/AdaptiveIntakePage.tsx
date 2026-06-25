import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, Check, MessageSquare, Send, Sparkles } from "lucide-react";
import { useState } from "react";
import {
  AdaptiveQuestion,
  Contradiction,
  Diagnosis,
  answerSession,
  getDiagnosis,
  getSessionState,
  startSession
} from "../api/adaptiveClient";

type Turn = { question: string; answer: string };

export function AdaptiveIntakePage() {
  const [lang, setLang] = useState<"fr" | "ar">("fr");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState<AdaptiveQuestion | null>(null);
  const [answer, setAnswer] = useState("");
  const [transcript, setTranscript] = useState<Turn[]>([]);
  const [ready, setReady] = useState(false);
  const [firedProbes, setFiredProbes] = useState<string[]>([]);
  const [contradictions, setContradictions] = useState<Contradiction[]>([]);

  const dir = lang === "ar" ? "rtl" : "ltr";

  const stateQuery = useQuery({
    queryKey: ["adaptive-state", sessionId],
    queryFn: () => getSessionState(sessionId as string),
    enabled: Boolean(sessionId)
  });

  const diagnosisQuery = useQuery<Diagnosis>({
    queryKey: ["adaptive-diagnosis", sessionId],
    queryFn: () => getDiagnosis(sessionId as string),
    enabled: Boolean(sessionId) && ready
  });

  const start = useMutation({
    mutationFn: () => startSession(lang),
    onSuccess: (data) => {
      setSessionId(data.session_id);
      setQuestion(data.first_question);
      setTranscript([]);
      setReady(false);
      setFiredProbes([]);
      setContradictions([]);
    }
  });

  const submit = useMutation({
    mutationFn: () =>
      answerSession(sessionId as string, (question as AdaptiveQuestion).id, answer),
    onSuccess: (data) => {
      setTranscript((prev) => [
        ...prev,
        { question: question?.text[lang] ?? question?.text.fr ?? "", answer }
      ]);
      setAnswer("");
      setQuestion(data.next_question);
      setReady(data.diagnostic_ready);
      setFiredProbes(data.fired_probes);
      setContradictions(data.contradictions);
      stateQuery.refetch();
    }
  });

  // --- Pre-session: choose language and start ---
  if (!sessionId) {
    return (
      <section className="panel max-w-2xl p-5">
        <div className="mb-5 flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-md bg-emerald-700 text-white">
            <MessageSquare size={20} />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-slate-950">Adaptive intake (conversational)</h2>
            <p className="text-sm text-slate-600">
              Répondez en texte libre (FR/AR). L&apos;IA extrait les preuves; les questions sont
              déterministes.
            </p>
          </div>
        </div>
        <label className="mb-4 grid max-w-xs gap-1 text-sm font-medium text-slate-700">
          Language / اللغة
          <select
            className="rounded-md border border-slate-300 px-3 py-2"
            value={lang}
            onChange={(event) => setLang(event.target.value as "fr" | "ar")}
          >
            <option value="fr">Français</option>
            <option value="ar">العربية</option>
          </select>
        </label>
        <button
          className="btn btn-primary w-fit"
          disabled={start.isPending}
          onClick={() => start.mutate()}
        >
          <Sparkles size={16} /> Start diagnostic
        </button>
        {start.isError ? (
          <p className="mt-3 text-sm text-red-600">{String(start.error)}</p>
        ) : null}
      </section>
    );
  }

  const progress = stateQuery.data;
  const percent = progress?.percent_to_next ?? 0;
  const frontierLabel = progress
    ? progress.next_stage
      ? `Frontier ${progress.frontier_stage} — ${progress.gates_satisfied}/${progress.gates_total} gates to ${progress.next_stage}`
      : `Frontier ${progress.frontier_stage} — top stage reached`
    : "Frontier —";

  return (
    <section className="panel max-w-2xl p-5" dir={dir}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-950">Adaptive intake</h2>
          <p className="text-sm text-slate-600">
            Phase: {stateQuery.data?.phase ?? "—"} · Declared (isolated):{" "}
            {stateQuery.data?.declared_stage ?? "—"}
          </p>
        </div>
        <select
          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          value={lang}
          onChange={(event) => setLang(event.target.value as "fr" | "ar")}
        >
          <option value="fr">FR</option>
          <option value="ar">AR</option>
        </select>
      </div>

      {/* Progress — frontier-relative (gates satisfied toward the next stage) */}
      <div className="mb-5">
        <div className="mb-1 flex justify-between text-xs text-slate-500">
          <span>{frontierLabel}</span>
          <span>{percent}%</span>
        </div>
        <div className="h-2 w-full rounded-full bg-slate-200">
          <div className="h-2 rounded-full bg-emerald-600" style={{ width: `${percent}%` }} />
        </div>
      </div>

      {/* Transcript */}
      <div className="mb-4 grid gap-3">
        {transcript.map((turn, index) => (
          <div key={index} className="grid gap-1">
            <p className="text-sm font-medium text-slate-700">{turn.question}</p>
            <p className="rounded-md bg-slate-100 px-3 py-2 text-sm text-slate-800">{turn.answer}</p>
          </div>
        ))}
      </div>

      {/* Signals from the last turn */}
      {firedProbes.length > 0 ? (
        <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <span className="font-medium">Probes fired:</span> {firedProbes.join(", ")}
        </div>
      ) : null}
      {contradictions.length > 0 ? (
        <div className="mb-3 grid gap-1 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {contradictions.map((item) => (
            <div key={item.rule_id} className="flex items-start gap-2">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              <span>
                <span className="font-medium">{item.field}:</span> {item.reason}
              </span>
            </div>
          ))}
        </div>
      ) : null}

      {/* Current question or terminal state */}
      {ready || !question ? (
        <div className="grid gap-3">
          <div className="flex items-center gap-2 text-emerald-700">
            <Check size={18} /> Diagnostic ready — enough evidence collected.
          </div>

          {diagnosisQuery.isLoading ? (
            <p className="text-sm text-slate-500">Running maturity + scoring on the evidence ledger…</p>
          ) : null}
          {diagnosisQuery.isError ? (
            <p className="text-sm text-red-600">{String(diagnosisQuery.error)}</p>
          ) : null}
          {diagnosisQuery.data ? (
            <div className="grid gap-3 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3">
              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <span className="text-sm text-slate-600">
                  Diagnosed stage:{" "}
                  <span className="font-semibold text-slate-900">
                    {diagnosisQuery.data.diagnosis.diagnosed_stage}
                  </span>
                </span>
                <span className="text-sm text-slate-600">
                  Declared (isolated):{" "}
                  <span className="font-medium">{diagnosisQuery.data.diagnosis.declared_stage}</span>
                </span>
                <span className="text-sm text-slate-600">
                  Gap: <span className="font-medium">{diagnosisQuery.data.diagnosis.gap_level}</span>
                </span>
                <span className="text-sm text-slate-600">
                  Confidence:{" "}
                  <span className="font-medium">
                    {Math.round(diagnosisQuery.data.diagnosis.confidence * 100)}%
                  </span>
                </span>
              </div>
              <div className="grid gap-1">
                {diagnosisQuery.data.scores.scores.map((score) => (
                  <div key={score.name} className="flex justify-between text-sm text-slate-700">
                    <span>{score.name.replace(/_score$/, "")}</span>
                    <span className="tabular-nums">
                      {score.value}
                      <span className="text-slate-400"> · conf {Math.round(score.confidence * 100)}%</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <button className="btn btn-secondary w-fit" onClick={() => setSessionId(null)}>
            Start a new session
          </button>
        </div>
      ) : (
        <form
          className="grid gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (answer.trim()) submit.mutate();
          }}
        >
          <label className="grid gap-2 text-sm font-medium text-slate-700">
            {question.text[lang] ?? question.text.fr}
            <textarea
              className="min-h-[90px] rounded-md border border-slate-300 px-3 py-2"
              placeholder={lang === "ar" ? "اكتب إجابتك هنا…" : "Écrivez votre réponse…"}
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
            />
          </label>
          <button className="btn btn-primary w-fit" disabled={submit.isPending || !answer.trim()}>
            <Send size={16} /> Answer
          </button>
          {submit.isError ? (
            <p className="text-sm text-red-600">{String(submit.error)}</p>
          ) : null}
        </form>
      )}
    </section>
  );
}
