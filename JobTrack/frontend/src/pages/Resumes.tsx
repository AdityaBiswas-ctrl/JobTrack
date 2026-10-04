import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { formatTimestamp } from "../api/format";
import { EmptyState, LoadingState, QueryError } from "../components/PageState";
import { useToast } from "../components/ToastContext";

export function Resumes() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [label, setLabel] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const resumes = useQuery({ queryKey: ["resumes"], queryFn: api.resumes });
  const upload = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Choose a PDF file first.");
      return api.uploadResume(label, file);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["resumes"] });
      setLabel("");
      setFile(null);
      const input = document.getElementById("resume-file") as HTMLInputElement | null;
      if (input) input.value = "";
      showToast("Resume uploaded.");
    },
    onError: (error: Error) => showToast(error.message, "error"),
  });
  const remove = useMutation({
    mutationFn: api.deleteResume,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["resumes"] });
      showToast("Resume deleted.");
    },
    onError: (error: Error) => showToast(error.message, "error"),
  });

  return (
    <div className="page-content">
      <div className="page-heading"><div><p className="eyebrow">YOUR MATERIALS</p><h1>Resumes</h1><p className="muted">A few versions for the roles you’re exploring.</p></div></div>
      <section className="panel form-panel">
        <p className="eyebrow">ADD A RESUME</p><h2>Keep a copy ready</h2>
        <form className="resume-upload" onSubmit={(event) => { event.preventDefault(); upload.mutate(); }}>
          <label>Label<input maxLength={120} onChange={(event) => setLabel(event.target.value)} placeholder="Backend roles" required value={label} /></label>
          <label>PDF file<input accept="application/pdf,.pdf" id="resume-file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required type="file" /></label>
          <p className="field-wide muted">PDF only · up to 2 MB · 5 resumes per account</p>
          <button className="button" disabled={upload.isPending || !file} type="submit">{upload.isPending ? "Uploading…" : "Upload PDF"}</button>
        </form>
      </section>
      <section className="resume-grid">
        {resumes.isLoading && <LoadingState label="Loading resumes" />}
        {resumes.error && <QueryError message={resumes.error.message} />}
        {resumes.data?.length === 0 && <div className="panel full-width"><EmptyState title="No resumes just yet" description="Upload a PDF to keep a copy with your account." /></div>}
        {resumes.data?.map((resume) => (
          <article className="panel resume-card" key={resume.id}>
            <span aria-hidden="true" className="resume-icon">PDF</span>
            <div className="resume-meta"><h2>{resume.label}</h2><p className="muted">{resume.filename}</p><p className="muted">Added {formatTimestamp(resume.uploaded_at)}</p></div>
            <button aria-label={`Delete ${resume.label}`} className="button button-quiet button-small" disabled={remove.isPending} onClick={() => {
              if (window.confirm(`Delete “${resume.label}”?`)) remove.mutate(resume.id);
            }} type="button">Delete</button>
          </article>
        ))}
      </section>
    </div>
  );
}
