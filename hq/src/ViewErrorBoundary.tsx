import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode; view?: string };
type State = { error: Error | null };

/** Contain residual render errors so HQ never white-screens. */
export class ViewErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("hq view render error", this.props.view ?? "unknown", error, info.componentStack);
  }

  componentDidUpdate(prevProps: Props): void {
    if (prevProps.view !== this.props.view && this.state.error) {
      this.setState({ error: null });
    }
  }

  private reload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="empty view-error" role="alert">
          <p className="empty-title">view_error()</p>
          <p className="empty-hint">
            {this.state.error.message || "unexpected render error"} — this panel is contained; the
            shell stays up.
          </p>
          <button type="button" className="btn" onClick={this.reload}>
            reload page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
