import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { formatDate, formatStatus } from "../api/format";
import { EmptyState, LoadingState, QueryError } from "../components/PageState";
import { useToast } from "../components/ToastContext";

export function Dashboard() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const stats = useQuery({ queryKey: ["stats"], queryFn: api.stats });
  const due = useQuery({ queryKey: ["reminders", true], queryFn: () => api.reminders(true) });
  const doneMutation = useMutation({
    mutationFn: api.markReminderDone,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reminders"] });
      showToast("Reminder marked done.");
    },
    onError: (error: Error) => showToast(error.message, "error"),
  });
  if (stats.isLoading) return <LoadingState label="Loading dashboard" />;
  if (stats.error) return <QueryError message={stats.error.message} />;
  const data = stats.data;
  if (!data) return null;
  const total = Object.values(data.counts_by_status).reduce((sum, count) => sum + count, 0);
  const chartData = data.applications_per_week.map((week) => ({
    week: new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(
      new Date(`${week.week_start}T00:00:00`),
    ),
    applications: week.count,
  }));

  return (
    <div className="page-content">
      <div className="page-heading">
        <div>
          <p className="eyebrow">YOUR JOB SEARCH, AT A GLANCE</p>
          <h1>Good things take a little tracking.</h1>
          <p className="muted">Here’s where each opportunity stands today.</p>
        </div>
        <Link className="button" to="/applications">Add an application</Link>
      </div>
      <section aria-label="Job search summary" className="stats-grid">
        <StatCard label="Applications" value={total} detail="Across your pipeline" />
        <StatCard
          label="Response rate"
          value={data.response_rate === null ? "—" : `${data.response_rate}%`}
          detail="Assessment, interview, offer or rejection"
        />
        <StatCard
          label="Days to first response"
          value={data.average_days_to_first_response === null ? "—" : data.average_days_to_first_response}
          detail={
            data.median_days_to_first_response === null
              ? "Average · Median —"
              : `Average · Median ${data.median_days_to_first_response} days`
          }
        />
        <StatCard
          label="Follow-ups due"
          value={due.data?.total ?? (due.isLoading ? "…" : 0)}
          detail="Worth a gentle nudge"
        />
      </section>

      <div className="dashboard-grid">
        <section className="panel chart-panel">
          <div className="section-heading">
            <div><p className="eyebrow">MOMENTUM</p><h2>Applications by week</h2></div>
            <span className="pill">Last 12 weeks</span>
          </div>
          <div aria-label="Applications per week bar chart" className="chart">
            <ResponsiveContainer height="100%" width="100%">
              <BarChart data={chartData} margin={{ left: -20, right: 10, top: 10 }}>
                <CartesianGrid stroke="#e8eeea" strokeDasharray="3 3" vertical={false} />
                <XAxis axisLine={false} dataKey="week" tickLine={false} tick={{ fill: "#718078", fontSize: 12 }} />
                <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: "#718078", fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="applications" fill="#477762" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="panel pipeline-panel">
          <div className="section-heading"><div><p className="eyebrow">PIPELINE</p><h2>Status overview</h2></div></div>
          <div className="pipeline-list">
            {Object.entries(data.counts_by_status).map(([key, count]) => (
              <Link className="pipeline-row" key={key} to={`/applications?status=${key}`}>
                <span className={`status-dot status-${key}`} />
                <span>{formatStatus(key as keyof typeof data.counts_by_status)}</span>
                <strong>{count}</strong>
              </Link>
            ))}
          </div>
        </section>
        <section className="panel due-panel">
          <div className="section-heading">
            <div><p className="eyebrow">A LITTLE NUDGE</p><h2>Follow-ups due</h2></div>
            <Link className="text-link" to="/applications">View applications</Link>
          </div>
          {due.isLoading ? <LoadingState label="Loading due reminders" /> : null}
          {due.error ? <QueryError message={due.error.message} /> : null}
          {due.data?.items.length === 0 && (
            <EmptyState title="You’re all caught up" description="No reminders need your attention today." />
          )}
          {due.data?.items.map((reminder) => (
            <div className="reminder-row" key={reminder.id}>
              <div>
                <Link className="strong-link" to={`/applications/${reminder.application_id}`}>
                  {reminder.company} · {reminder.role}
                </Link>
                <p className="muted">{reminder.note || "Follow-up"} · {formatDate(reminder.due_at)}</p>
              </div>
              <button
                aria-label={`Mark reminder for ${reminder.company} done`}
                className="button button-quiet button-small"
                disabled={doneMutation.isPending}
                onClick={() => doneMutation.mutate(reminder.id)}
                type="button"
              >
                Mark done
              </button>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}

function StatCard({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return (
    <article className="panel stat-card">
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
      <p className="stat-detail">{detail}</p>
    </article>
  );
}
