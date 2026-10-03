import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { ApplicationStatus } from "../api/client";
import { api } from "../api/client";
import { formatDate, formatStatus, formatTimestamp, statuses } from "../api/format";
import { EmptyState, LoadingState, QueryError } from "../components/PageState";
import { ScoreResumePanel } from "../components/ScoreResumePanel";
import { useToast } from "../components/ToastContext";

export function ApplicationDetail() {
  const { id = "" } = useParams();
  const applicationId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [nextStatus, setNextStatus] = useState<ApplicationStatus>("wishlist");
  const [statusNote, setStatusNote] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [reminderNote, setReminderNote] = useState("");
  const application = useQuery({
    queryKey: ["application", applicationId],
    queryFn: () => api.application(applicationId),
    enabled: Number.isInteger(applicationId) && applicationId > 0,
  });
  const history = useQuery({
    queryKey: ["history", applicationId],
    queryFn: () => api.history(applicationId),
    enabled: application.isSuccess,
  });
  const resumes = useQuery({ queryKey: ["resumes"], queryFn: api.resumes });
  const scores = useQuery({
    queryKey: ["scores", applicationId],
    queryFn: () => api.scores(applicationId),
    enabled: application.isSuccess,
  });

  const statusMutation = useMutation({
    mutationFn: () => api.changeStatus(applicationId, nextStatus, statusNote || undefined),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["application", applicationId] });
      void queryClient.invalidateQueries({ queryKey: ["history", applicationId] });
      void queryClient.invalidateQueries({ queryKey: ["applications"] });
      void queryClient.invalidateQueries({ queryKey: ["stats"] });
      setStatusNote("");
      showToast("Status updated.");
    },
    onError: (error: Error) => showToast(error.message, "error"),
  });
  const reminderMutation = useMutation({
    mutationFn: () => api.createReminder(applicationId, new Date(dueAt).toISOString(), reminderNote),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reminders"] });
      setDueAt("");
      setReminderNote("");
      showToast("Reminder added.");
    },
    onError: (error: Error) => showToast(error.message, "error"),
  });
  const deleteMutation = useMutation({
    mutationFn: () => api.deleteApplication(applicationId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["applications"] });
      void queryClient.invalidateQueries({ queryKey: ["stats"] });
      showToast("Application deleted.");
      navigate("/applications", { replace: true });
    },
    onError: (error: Error) => showToast(error.message, "error"),
  });

  if (application.isLoading) return <LoadingState label="Loading application details" />;
  if (application.error) return <QueryError message={application.error.message} />;
  if (!application.data) return null;
  const item = application.data;

  return (
    <div className="page-content">
      <Link className="back-link" to="/applications">← All applications</Link>
      <div className="page-heading detail-heading">
        <div>
          <p className="eyebrow">{item.company.toUpperCase()}</p>
          <h1>{item.role}</h1>
          <p className="muted">{item.location || "Location not set"} · Applied {formatDate(item.applied_on)}</p>
        </div>
        <span className={`status-badge status-${item.status}`}>{formatStatus(item.status)}</span>
      </div>
      <div className="detail-grid">
        <section className="panel detail-main">
          <div className="section-heading"><div><p className="eyebrow">THE OPPORTUNITY</p><h2>Job description</h2></div></div>
          <p className="preserve-text">{item.jd_text || "No job description added yet."}</p>
          {item.job_url && <a className="text-link" href={item.job_url} rel="noreferrer" target="_blank">Open job posting ↗</a>}
          <div className="divider" />
          <h2>Notes</h2>
          <p className="preserve-text">{item.notes || "No notes yet."}</p>
          <div className="divider" />
          <div className="section-heading"><div><p className="eyebrow">THE JOURNEY</p><h2>Status history</h2></div></div>
          {history.isLoading && <LoadingState label="Loading status history" />}
          {history.error && <QueryError message={history.error.message} />}
          {history.data?.length === 0 && <EmptyState title="No history yet" description="Status changes will appear here." />}
          <ol className="timeline">
            {history.data?.map((event) => (
              <li key={event.id}>
                <span className="timeline-dot" />
                <div><strong>{event.from_status ? `${formatStatus(event.from_status)} → ` : "Started as "}{formatStatus(event.to_status)}</strong>
                  <p className="muted">{formatTimestamp(event.changed_at)}{event.note ? ` · ${event.note}` : ""}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="divider" />
          <h2>Resume scores</h2>
          {scores.data?.length === 0 && <p className="muted">Scores for this application will appear here.</p>}
          <div className="score-list">
            {scores.data?.map((score) => (
              <article className="score-row" key={score.id}>
                <strong>{score.match_score === null ? "Unavailable" : `${score.match_score}% match`}</strong>
                <span className={`pill ${score.scorer_status === "ok" ? "pill-good" : "pill-warn"}`}>{score.scorer_status}</span>
                {score.cache_hit && <span className="pill">Cached</span>}
                <span className="muted">{formatTimestamp(score.created_at)} · {score.latency_ms} ms</span>
                {score.missing_keywords && <p className="muted">Missing: {score.missing_keywords.join(", ") || "none"}</p>}
              </article>
            ))}
          </div>
        </section>
        <aside className="detail-sidebar">
          <section className="panel">
            <p className="eyebrow">KEEP IT MOVING</p><h2>Update status</h2>
            <form className="form-stack" onSubmit={(event) => { event.preventDefault(); statusMutation.mutate(); }}>
              <label>Status<select onChange={(event) => setNextStatus(event.target.value as ApplicationStatus)} value={nextStatus}>
                {statuses.map((status) => <option key={status} value={status}>{formatStatus(status)}</option>)}
              </select></label>
              <label>Note (optional)<input onChange={(event) => setStatusNote(event.target.value)} value={statusNote} /></label>
              <button className="button button-full" disabled={statusMutation.isPending || nextStatus === item.status} type="submit">
                {statusMutation.isPending ? "Saving…" : "Save status"}
              </button>
            </form>
          </section>
          <section className="panel">
            <p className="eyebrow">A TIMELY REMINDER</p><h2>Follow up</h2>
            <form className="form-stack" onSubmit={(event) => { event.preventDefault(); reminderMutation.mutate(); }}>
              <label>Due date and time<input onChange={(event) => setDueAt(event.target.value)} required type="datetime-local" value={dueAt} /></label>
              <label>What to remember<input onChange={(event) => setReminderNote(event.target.value)} value={reminderNote} /></label>
              <button className="button button-full" disabled={reminderMutation.isPending} type="submit">Add reminder</button>
            </form>
          </section>
          <ScoreResumePanel
            applicationId={applicationId}
            hasJobDescription={Boolean(item.jd_text?.trim())}
            resumes={resumes.data ?? []}
          />
          <button className="button button-danger button-full" disabled={deleteMutation.isPending} onClick={() => {
            if (window.confirm("Delete this application and its history, reminders, and scores?")) deleteMutation.mutate();
          }} type="button">
            Delete application
          </button>
        </aside>
      </div>
    </div>
  );
}
