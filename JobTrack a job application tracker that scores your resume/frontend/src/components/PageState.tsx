export function LoadingState({ label = "Loading your data…" }: { label?: string }) {
  return (
    <div aria-label={label} className="skeleton-list" role="status">
      <span className="skeleton skeleton-heading" />
      <span className="skeleton" />
      <span className="skeleton" />
      <span className="skeleton skeleton-short" />
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <span aria-hidden="true" className="empty-icon">✦</span>
      <h3>{title}</h3>
      <p className="muted">{description}</p>
      {action}
    </div>
  );
}

export function QueryError({ message }: { message: string }) {
  return <div className="error-panel" role="alert">{message}</div>;
}
