import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { Resume } from "../api/client";
import { api, ApiError } from "../api/client";
import { useToast } from "./ToastContext";

export function ScoreResumePanel({
  applicationId,
  hasJobDescription,
  resumes,
}: {
  applicationId: number;
  hasJobDescription: boolean;
  resumes: Resume[];
}) {
  const [resumeId, setResumeId] = useState("");
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const scoreMutation = useMutation({
    mutationFn: () => api.score(applicationId, Number(resumeId)),
    onSuccess: (score) => {
      void queryClient.invalidateQueries({ queryKey: ["scores", applicationId] });
      showToast(score.cache_hit ? "Using your saved score." : "Resume scored successfully.");
    },
    onError: (error: Error) => {
      if (error instanceof ApiError && error.status === 503) {
        showToast("The scorer may be waking up. Please try again shortly.", "error");
      } else if (error instanceof ApiError && error.status === 429) {
        showToast("You’ve reached 10 scoring attempts this hour. The limit resets within an hour.", "error");
      } else {
        showToast(error.message, "error");
      }
    },
  });

  return (
    <section className="panel score-panel">
      <p className="eyebrow">A LITTLE EXTRA CLARITY</p><h2>Score your resume</h2>
      {resumes.length ? (
        <form className="form-stack" onSubmit={(event) => { event.preventDefault(); scoreMutation.mutate(); }}>
          <label>Choose a resume<select onChange={(event) => setResumeId(event.target.value)} required value={resumeId}>
            <option value="">Select resume…</option>
            {resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.label}</option>)}
          </select></label>
          {scoreMutation.isPending && <p aria-live="polite" className="scoring-note" role="status">Scoring can take a minute; the scorer may be waking up.</p>}
          <button className="button button-full" disabled={!resumeId || scoreMutation.isPending || !hasJobDescription} type="submit">
            {scoreMutation.isPending ? "Scoring…" : "Score resume"}
          </button>
        </form>
      ) : (
        <p className="muted">Upload a PDF resume first to compare it with this role.</p>
      )}
      {!hasJobDescription && <p className="field-error">Add a job description before scoring.</p>}
    </section>
  );
}
