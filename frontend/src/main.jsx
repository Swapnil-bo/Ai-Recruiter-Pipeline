import React, {
    StrictMode,
    Suspense,
    useState,
    useEffect,
    useCallback,
    createContext,
    useContext,
  } from "react";
  import { createRoot } from "react-dom/client";
  import { BrowserRouter } from "react-router-dom";
  import { Toaster, toast } from "react-hot-toast";
  import App from "./App";
  import "./index.css";
  
  // ── Theme Context ──────────────────────────────────────────────────────────────
  
  const ThemeContext = createContext({
    theme: "dark",
    toggleTheme: () => {},
  });
  
  export const useTheme = () => useContext(ThemeContext);
  
  function ThemeProvider({ children }) {
    const [theme, setTheme] = useState(() => {
      try {
        return localStorage.getItem("theme") || "dark";
      } catch {
        return "dark";
      }
    });
  
    useEffect(() => {
      const root = document.documentElement;
      if (theme === "dark") {
        root.classList.add("dark");
        root.classList.remove("light");
      } else {
        root.classList.remove("dark");
        root.classList.add("light");
      }
      try {
        localStorage.setItem("theme", theme);
      } catch {}
    }, [theme]);
  
    const toggleTheme = useCallback(() => {
      setTheme((prev) => (prev === "dark" ? "light" : "dark"));
    }, []);
  
    return (
      <ThemeContext.Provider value={{ theme, toggleTheme }}>
        {children}
      </ThemeContext.Provider>
    );
  }
  
  // ── Error Boundary ─────────────────────────────────────────────────────────────
  
  class ErrorBoundary extends React.Component {
    constructor(props) {
      super(props);
      this.state = {
        hasError: false,
        error: null,
        errorInfo: null,
        errorId: null,
      };
    }
  
    static getDerivedStateFromError(error) {
      return {
        hasError: true,
        error,
        errorId: `ERR_${Date.now().toString(36).toUpperCase()}`,
      };
    }
  
    componentDidCatch(error, errorInfo) {
      this.setState({ errorInfo });
      console.error("[AI Recruiter] Uncaught error:", error, errorInfo);
    }
  
    handleReset = () => {
      this.setState({
        hasError: false,
        error: null,
        errorInfo: null,
        errorId: null,
      });
    };
  
    handleReload = () => {
      window.location.reload();
    };
  
    render() {
      if (!this.state.hasError) return this.props.children;
  
      const { error, errorId } = this.state;
      const isDev = import.meta.env.DEV;
  
      return (
        <div className="error-boundary-screen">
          <div className="error-boundary-orb error-boundary-orb-1" />
          <div className="error-boundary-orb error-boundary-orb-2" />
  
          <div className="error-boundary-card">
            {/* Icon */}
            <div className="error-boundary-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                />
              </svg>
            </div>
  
            {/* Headline */}
            <div className="error-boundary-content">
              <h1 className="error-boundary-title">Something went wrong</h1>
              <p className="error-boundary-subtitle">
                An unexpected error occurred in the application.
                {isDev ? " See details below." : " Try resetting or reloading."}
              </p>
  
              {/* Error ID */}
              <div className="error-boundary-id">
                <span className="error-boundary-id-label">Error ID</span>
                <code className="error-boundary-id-value">{errorId}</code>
              </div>
  
              {/* Dev: show error details */}
              {isDev && error && (
                <div className="error-boundary-details">
                  <p className="error-boundary-message">{error.message}</p>
                  {this.state.errorInfo?.componentStack && (
                    <pre className="error-boundary-stack">
                      {this.state.errorInfo.componentStack.trim()}
                    </pre>
                  )}
                </div>
              )}
  
              {/* Actions */}
              <div className="error-boundary-actions">
                <button
                  className="error-boundary-btn error-boundary-btn-primary"
                  onClick={this.handleReset}
                >
                  Try Again
                </button>
                <button
                  className="error-boundary-btn error-boundary-btn-secondary"
                  onClick={this.handleReload}
                >
                  Reload Page
                </button>
              </div>
            </div>
          </div>
  
          {/* Version */}
          <p className="error-boundary-version">
            AI Recruiter Pipeline v1.0.0
          </p>
        </div>
      );
    }
  }
  
  // ── Suspense Fallback ──────────────────────────────────────────────────────────
  
  function SuspenseFallback() {
    return (
      <div className="suspense-fallback">
        <div className="suspense-spinner" />
        <span className="suspense-text">Loading...</span>
      </div>
    );
  }
  
  // ── Global Toast Config ────────────────────────────────────────────────────────
  
  const TOAST_CONFIG = {
    position: "bottom-right",
    toastOptions: {
      duration: 4000,
      style: {
        background:   "#1e293b",
        color:        "#f1f5f9",
        border:       "1px solid rgba(255, 255, 255, 0.08)",
        borderRadius: "10px",
        fontSize:     "0.875rem",
        fontFamily:   '"Inter", system-ui, sans-serif',
        boxShadow:    "0 8px 32px rgba(0, 0, 0, 0.4)",
        padding:      "12px 16px",
        maxWidth:     "380px",
      },
      success: {
        iconTheme: {
          primary:    "#10b981",
          secondary:  "#1e293b",
        },
        style: {
          background:  "#1e293b",
          borderColor: "rgba(16, 185, 129, 0.25)",
        },
      },
      error: {
        iconTheme: {
          primary:   "#ef4444",
          secondary: "#1e293b",
        },
        style: {
          background:  "#1e293b",
          borderColor: "rgba(239, 68, 68, 0.25)",
        },
        duration: 6000,
      },
      loading: {
        iconTheme: {
          primary:   "#3b82f6",
          secondary: "#1e293b",
        },
        style: {
          background:  "#1e293b",
          borderColor: "rgba(59, 130, 246, 0.25)",
        },
      },
    },
  };
  
  // ── Network Status Monitor ────────────────────────────────────────────────────
  
  function NetworkMonitor() {
    useEffect(() => {
      let offlineToastId = null;
  
      const handleOffline = () => {
        offlineToastId = toast.error(
          "You are offline. Some features may not work.",
          { duration: Infinity, id: "network-offline" }
        );
      };
  
      const handleOnline = () => {
        toast.dismiss("network-offline");
        toast.success("Connection restored.", { id: "network-online" });
      };
  
      window.addEventListener("offline", handleOffline);
      window.addEventListener("online", handleOnline);
  
      return () => {
        window.removeEventListener("offline", handleOffline);
        window.removeEventListener("online", handleOnline);
      };
    }, []);
  
    return null;
  }
  
  // ── Unhandled Promise Rejection Monitor ───────────────────────────────────────
  
  function PromiseRejectionMonitor() {
    useEffect(() => {
      const handler = (event) => {
        const reason = event.reason;
        const message =
          reason?.message || String(reason) || "Unknown error";
  
        // Suppress known benign errors
        if (
          message.includes("ResizeObserver loop") ||
          message.includes("AbortError") ||
          message.includes("NetworkError")
        ) {
          return;
        }
  
        console.error("[AI Recruiter] Unhandled promise rejection:", reason);
  
        if (import.meta.env.DEV) {
          toast.error(`Unhandled Error: ${message.slice(0, 80)}`, {
            id: "unhandled-rejection",
            duration: 5000,
          });
        }
      };
  
      window.addEventListener("unhandledrejection", handler);
      return () => window.removeEventListener("unhandledrejection", handler);
    }, []);
  
    return null;
  }
  
  // ── Performance Monitor (Dev Only) ────────────────────────────────────────────
  
  function PerformanceMonitor() {
    useEffect(() => {
      if (!import.meta.env.DEV) return;
  
      // Log Web Vitals to console in dev
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.entryType === "largest-contentful-paint") {
            console.debug(`[Perf] LCP: ${entry.startTime.toFixed(0)}ms`);
          }
          if (entry.entryType === "first-input") {
            console.debug(`[Perf] FID: ${entry.processingStart - entry.startTime.toFixed(0)}ms`);
          }
        }
      });
  
      try {
        observer.observe({ entryTypes: ["largest-contentful-paint", "first-input"] });
      } catch {}
  
      // Log initial load time
      const nav = performance.getEntriesByType("navigation")[0];
      if (nav) {
        console.debug(
          `[Perf] Page load: ${nav.loadEventEnd.toFixed(0)}ms | ` +
          `DOM ready: ${nav.domContentLoadedEventEnd.toFixed(0)}ms`
        );
      }
  
      return () => observer.disconnect();
    }, []);
  
    return null;
  }
  
  // ── Keyboard Shortcut Handler ─────────────────────────────────────────────────
  
  function KeyboardShortcutProvider() {
    useEffect(() => {
      const handler = (e) => {
        // Ctrl/Cmd + K — command palette (future feature)
        if ((e.ctrlKey || e.metaKey) && e.key === "k") {
          e.preventDefault();
          // Dispatch custom event for command palette
          window.dispatchEvent(new CustomEvent("open-command-palette"));
        }
  
        // Ctrl/Cmd + Shift + D — toggle debug panel (dev only)
        if (
          import.meta.env.DEV &&
          (e.ctrlKey || e.metaKey) &&
          e.shiftKey &&
          e.key === "D"
        ) {
          e.preventDefault();
          window.dispatchEvent(new CustomEvent("toggle-debug-panel"));
        }
      };
  
      window.addEventListener("keydown", handler);
      return () => window.removeEventListener("keydown", handler);
    }, []);
  
    return null;
  }
  
  // ── Hide Loader on Mount ───────────────────────────────────────────────────────
  
  function LoaderDismisser() {
    useEffect(() => {
      // Give React one frame to paint before hiding loader
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (typeof window.__hideLoader === "function") {
            window.__hideLoader();
          }
        });
      });
    }, []);
  
    return null;
  }
  
  // ── Dev Overlay ────────────────────────────────────────────────────────────────
  
  function DevOverlay() {
    const [visible, setVisible] = useState(false);
  
    useEffect(() => {
      if (!import.meta.env.DEV) return;
  
      const toggle = () => setVisible((v) => !v);
      window.addEventListener("toggle-debug-panel", toggle);
      return () => window.removeEventListener("toggle-debug-panel", toggle);
    }, []);
  
    if (!import.meta.env.DEV || !visible) return null;
  
    return (
      <div className="dev-overlay">
        <div className="dev-overlay-badge">
          DEV · {import.meta.env.MODE} · {window.innerWidth}×{window.innerHeight}
        </div>
      </div>
    );
  }
  
  // ── Root Component ─────────────────────────────────────────────────────────────
  
  function Root() {
    return (
      <StrictMode>
        <ErrorBoundary>
          <ThemeProvider>
            <BrowserRouter>
              <Suspense fallback={<SuspenseFallback />}>
  
                {/* Side-effect only components */}
                <LoaderDismisser />
                <NetworkMonitor />
                <PromiseRejectionMonitor />
                <PerformanceMonitor />
                <KeyboardShortcutProvider />
                <DevOverlay />
  
                {/* Main App */}
                <App />
  
                {/* Global Toast Notifications */}
                <Toaster
                  position={TOAST_CONFIG.position}
                  toastOptions={TOAST_CONFIG.toastOptions}
                />
  
              </Suspense>
            </BrowserRouter>
          </ThemeProvider>
        </ErrorBoundary>
      </StrictMode>
    );
  }
  
  // ── Mount ──────────────────────────────────────────────────────────────────────
  
  const container = document.getElementById("root");
  
  if (!container) {
    throw new Error(
      "[AI Recruiter] Root element #root not found. " +
      "Check your index.html."
    );
  }
  
  const root = createRoot(container);
  root.render(<Root />);
  
  // ── Export Contexts ────────────────────────────────────────────────────────────
  
  export { ThemeContext };