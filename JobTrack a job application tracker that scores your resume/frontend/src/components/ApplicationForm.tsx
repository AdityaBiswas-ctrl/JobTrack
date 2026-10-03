import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api } from "../api/client";
import { useToast } from "./ToastContext";

const applicationSchema = z.object({
  company: z.string().trim().min(1, "Company is required").max(120),
  role: z.string().trim().min(1, "Role is required").max(120),
  job_url: z.union([z.literal(""), z.string().url("Enter a valid URL")]),
  location: z.string().max(120),
  source: z.string().max(80),
  applied_on: z.string(),
  notes: z.string(),
  jd_text: z.string().max(20_000, "Keep the job description under 20,000 characters"),
});

type FormValues = z.infer<typeof applicationSchema>;

export function ApplicationForm({ onCreated }: { onCreated: () => void }) {
  const { showToast } = useToast();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(applicationSchema),
    defaultValues: {
      company: "",
      role: "",
      job_url: "",
      location: "",
      source: "",
      applied_on: "",
      notes: "",
      jd_text: "",
    },
  });

  async function submit(values: FormValues) {
    try {
      await api.createApplication({
        company: values.company,
        role: values.role,
        job_url: values.job_url || null,
        location: values.location || null,
        source: values.source || null,
        applied_on: values.applied_on || null,
        notes: values.notes || null,
        jd_text: values.jd_text || null,
      });
      reset();
      onCreated();
      showToast("Application added to your tracker.");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Could not save this application.", "error");
    }
  }

  return (
    <form className="form-grid" onSubmit={handleSubmit(submit)}>
      <label>
        Company
        <input autoComplete="organization" {...register("company")} />
        {errors.company && <small className="field-error">{errors.company.message}</small>}
      </label>
      <label>
        Role
        <input {...register("role")} />
        {errors.role && <small className="field-error">{errors.role.message}</small>}
      </label>
      <label>
        Job URL
        <input placeholder="https://…" type="url" {...register("job_url")} />
        {errors.job_url && <small className="field-error">{errors.job_url.message}</small>}
      </label>
      <label>
        Location
        <input {...register("location")} />
      </label>
      <label>
        Source
        <input placeholder="Company site, referral…" {...register("source")} />
      </label>
      <label>
        Applied on
        <input type="date" {...register("applied_on")} />
      </label>
      <label className="field-wide">
        Notes
        <textarea rows={3} {...register("notes")} />
      </label>
      <label className="field-wide">
        Job description
        <textarea rows={5} {...register("jd_text")} />
        {errors.jd_text && <small className="field-error">{errors.jd_text.message}</small>}
      </label>
      <div className="field-wide">
        <button className="button" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Saving…" : "Add application"}
        </button>
      </div>
    </form>
  );
}
