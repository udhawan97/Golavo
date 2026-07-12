import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertIcon } from "./icons";

interface Props {
  children: ReactNode;
  /** Changing this value resets the boundary — pass the route so navigating
   *  away from a crashed view clears the error instead of stranding the user. */
  resetKey?: string;
}
interface State {
  error: Error | null;
}

/** Catches render-time throws so a single bad view (or a malformed deep link)
 *  degrades to a recoverable panel instead of unmounting the whole app to a
 *  blank page. React has no hook equivalent — a class is the only way. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Local-only: no telemetry. Surfaced for the dev console / desktop logs.
    console.error("Golavo render error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="state" role="alert">
          <AlertIcon size={48} className="state__glyph" style={{ color: "var(--orange)" }} />
          <p className="state__title">This view hit a snag</p>
          <p className="state__body">
            Something rendered wrong and Golavo caught it before it took the page down.{" "}
            <a href="#/">Back to games ›</a>
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
