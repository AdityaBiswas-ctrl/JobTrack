import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api/client";
import { LoadingState, QueryError } from "../components/PageState";
import { useToast } from "../components/ToastContext";

export function Settings() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const profile = useQuery({ queryKey: ["me"], queryFn: api.me });
  const remove = useMutation({
    mutationFn: api.deleteAccount,
    onSuccess: () => {
      setToken(null);
      queryClient.clear();
      navigate("/signup", { replace: true });
    },
    onError: (error: Error) => showToast(error.message, "error"),
  });
  if (profile.isLoading) return <LoadingState label="Loading account settings" />;
  if (profile.error) return <QueryError message={profile.error.message} />;

  return (
    <div className="page-content">
      <div className="page-heading"><div><p className="eyebrow">YOUR ACCOUNT</p><h1>Settings</h1><p className="muted">A few choices for your JobTrack account.</p></div></div>
      <section className="panel settings-panel">
        <p className="eyebrow">PROFILE</p><h2>Account details</h2>
        <p className="settings-email">{profile.data?.email}</p>
        <p className="muted">Your account and job-search data belong to you.</p>
      </section>
      <section className="panel settings-panel danger-zone">
        <p className="eyebrow">PERMANENT ACTION</p><h2>Delete your account</h2>
        <p className="muted">This permanently deletes your applications, reminders, history, and resumes.</p>
        <button className="button button-danger" disabled={remove.isPending} onClick={() => {
          if (window.confirm("Permanently delete your account and all JobTrack data? This cannot be undone.")) remove.mutate();
        }} type="button">{remove.isPending ? "Deleting…" : "Delete my account and data"}</button>
      </section>
    </div>
  );
}
