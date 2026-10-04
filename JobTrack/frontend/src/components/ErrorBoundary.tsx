import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { hasError: boolean };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Frontend rendering error", error.name, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="auth-shell">
          <section className="panel">
            <h1>Something went wrong</h1>
            <p className="muted">Refresh the page to try again.</p>
            <button className="button" onClick={() => window.location.reload()} type="button">
              Refresh
            </button>
          </section>
        </main>
      );
    }
    return this.props.children;
  }
}
