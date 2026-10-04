import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { formatDate, formatStatus, statuses } from "../api/format";
import { ApplicationForm } from "../components/ApplicationForm";
import { EmptyState, LoadingState, QueryError } from "../components/PageState";

export function Applications() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState(searchParams.get("q") ?? "");
  const selectedStatus = searchParams.get("status") ?? "";
  const applications = useQuery({
    queryKey: ["applications", selectedStatus, search],
    queryFn: () => api.applications({ status: selectedStatus || undefined, q: search || undefined }),
  });

  function updateFilter(status: string) {
    const next = new URLSearchParams(searchParams);
    if (status) next.set("status", status);
    else next.delete("status");
    setSearchParams(next);
  }

  return (
    <div className="page-content">
      <div className="page-heading">
        <div><p className="eyebrow">YOUR OPPORTUNITIES</p><h1>Applications</h1><p className="muted">Every possibility, in one tidy place.</p></div>
      </div>
      <details className="panel form-panel">
        <summary className="summary-heading">Add a new application <span>＋</span></summary>
        <ApplicationForm onCreated={() => queryClient.invalidateQueries({ queryKey: ["applications"] })} />
      </details>
      <section className="panel table-panel">
        <div className="filter-row">
          <label className="search-field">
            Search company or role
            <input
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Try “designer” or “Acme”"
              value={search}
            />
          </label>
          <label>
            Status
            <select onChange={(event) => updateFilter(event.target.value)} value={selectedStatus}>
              <option value="">All statuses</option>
              {statuses.map((status) => <option key={status} value={status}>{formatStatus(status)}</option>)}
            </select>
          </label>
        </div>
        {applications.isLoading && <LoadingState label="Loading applications" />}
        {applications.error && <QueryError message={applications.error.message} />}
        {applications.data?.items.length === 0 && (
          <EmptyState title="Your next opportunity starts here" description="Add an application to keep its details and follow-ups close." />
        )}
        {!!applications.data?.items.length && (
          <div className="table-scroll">
            <table>
              <thead><tr><th>Company & role</th><th>Status</th><th>Applied</th><th>Location</th><th /></tr></thead>
              <tbody>
                {applications.data.items.map((application) => (
                  <tr key={application.id}>
                    <td>
                      <Link className="table-title" to={`/applications/${application.id}`}>{application.company}</Link>
                      <span className="table-subtitle">{application.role}</span>
                    </td>
                    <td><span className={`status-badge status-${application.status}`}>{formatStatus(application.status)}</span></td>
                    <td>{formatDate(application.applied_on)}</td>
                    <td>{application.location || "—"}</td>
                    <td><Link aria-label={`Open ${application.company}`} className="row-arrow" to={`/applications/${application.id}`}>↗</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
