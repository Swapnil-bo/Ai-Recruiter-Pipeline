import { lazy, Suspense, useEffect, useState, useCallback } from "react";
import {
  Routes,
  Route,
  NavLink,
  useLocation,
  useNavigate,
  Navigate,
} from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "react-hot-toast";
import {
  LayoutDashboard,
  Upload,
  Activity,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
  Cpu,
  Wifi,
  WifiOff,
  Moon,
  Sun,
  Github,
  Twitter,
  Zap,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Menu,
  X,
} from "lucide-react";
import { useTheme } from "./main";
import clsx from "clsx";

// ── Lazy Pages ─────────────────────────────────────────────────────────────────

const Dashboard      = lazy(() => import("./pages/Dashboard"));
const ResumeUpload   = lazy(() => import("./pages/ResumeUpload"));
const PipelineStatus = lazy(() => import("./pages/PipelineStatus"));
const JobDetail      = lazy(() => import("./pages/JobDetail"));

// ── Constants ──────────────────────────────────────────────────────────────────

const API_BASE = "/api/v1";
const WS_URL   = `ws://${window.location.host}/ws/pipeline`;

const NAV_ITEMS = [
  {
    to:    "/",
    end:   true,
    icon:  LayoutDashboard,
    label: "Dashboard",
    description: "Ranked job matches",
  },
  {
    to:    "/resume",
    icon:  Upload,
    label: "Resume",
    description: "Upload & manage resume",
  },
  {
    to:    "/pipeline",
    icon:  Activity,
    label: "Pipeline",
    description: "Run & monitor agents",
  },
];

// ── Page Transition Variants ───────────────────────────────────────────────────

const PAGE_VARIANTS = {
  initial:  { opacity: 0, y: 12, scale: 0.99 },
  animate:  { opacity: 1, y: 0,  scale: 1    },
  exit:     { opacity: 0, y: -8, scale: 0.99 },
};

const PAGE_TRANSITION = {
  duration: 0.22,
  ease: [0.25, 0.46, 0.45, 0.94],
};

// ── Ollama Health Hook ─────────────────────────────────────────────────────────

function useOllamaHealth() {
  const [status, setStatus] = useState("checking"); // checking | ok | degraded | error
  const [model,  setModel]  = useState(null);

  const check = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE.replace("/api/v1", "")}/health/ollama`);
      if (res.ok) {
        const data = await res.json();
        setStatus("ok");
        setModel(data.model);
      } else {
        setStatus("degraded");
      }
    } catch {
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    check();
    const interval = setInterval(check, 30_000);
    return () => clearInterval(interval);
  }, [check]);

  return { status, model, check };
}

// ── Resume Status Hook ─────────────────────────────────────────────────────────

function useResumeStatus() {
  const [uploaded,  setUploaded]  = useState(false);
  const [meta,      setMeta]      = useState(null);
  const [loading,   setLoading]   = useState(true);

  const check = useCallback(async () => {
    try {
      const res  = await fetch(`${API_BASE}/resume/status`);
      const data = await res.json();
      setUploaded(data.uploaded);
      setMeta(data.meta || null);
    } catch {
      setUploaded(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    check();
    // Re-check when window regains focus
    window.addEventListener("focus", check);
    return () => window.removeEventListener("focus", check);
  }, [check]);

  return { uploaded, meta, loading, refresh: check };
}

// ── Pipeline Running Hook ─────────────────────────────────────────────────────

function usePipelineRunning() {
  const [running, setRunning] = useState(false);

  useEffect(() => {
    const check = async () => {
      try {
        const res  = await fetch(`${API_BASE}/pipeline/status`);
        const data = await res.json();
        setRunning(data.is_running);
      } catch {}
    };

    check();
    const interval = setInterval(check, 5000);
    return () => clearInterval(interval);
  }, []);

  return running;
}

// ── Sidebar ────────────────────────────────────────────────────────────────────

function Sidebar({
  collapsed,
  onToggle,
  ollamaStatus,
  ollamaModel,
  resumeUploaded,
  resumeMeta,
  pipelineRunning,
}) {
  const location  = useLocation();
  const { theme, toggleTheme } = useTheme();

  return (
    <aside
      className={clsx(
        "relative flex flex-col h-screen bg-surface-900/80 backdrop-blur-xl",
        "border-r border-white/[0.06] transition-all duration-300 ease-in-out",
        "flex-shrink-0 z-40",
        collapsed ? "w-16" : "w-60"
      )}
    >
      {/* ── Logo ────────────────────────────────────────────────────────── */}
      <div
        className={clsx(
          "flex items-center h-16 border-b border-white/[0.06] flex-shrink-0",
          collapsed ? "justify-center px-0" : "px-4 gap-3"
        )}
      >
        <div className="relative flex-shrink-0">
          <div
            className={clsx(
              "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0",
              "bg-gradient-to-br from-primary-600 to-accent-600",
              "shadow-[0_0_16px_rgba(59,130,246,0.4)]"
            )}
          >
            <Zap className="w-4 h-4 text-white" strokeWidth={2.5} />
          </div>
          {pipelineRunning && (
            <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.8)] animate-pulse" />
          )}
        </div>

        {!collapsed && (
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-bold text-surface-50 leading-tight tracking-tight truncate">
              AI Recruiter
            </span>
            <span className="text-[10px] text-surface-500 font-mono tracking-wider truncate">
              PIPELINE v1.0
            </span>
          </div>
        )}
      </div>

      {/* ── Nav ─────────────────────────────────────────────────────────── */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden py-4 space-y-1 px-2 scrollbar-none">
        {NAV_ITEMS.map((item) => {
          const Icon    = item.icon;
          const isActive = item.end
            ? location.pathname === item.to
            : location.pathname.startsWith(item.to);

          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={clsx(
                "group relative flex items-center rounded-xl transition-all duration-150",
                "outline-none focus-visible:ring-2 focus-visible:ring-primary-500",
                collapsed ? "justify-center h-10 w-10 mx-auto" : "gap-3 px-3 h-10",
                isActive
                  ? "bg-primary-600/15 text-primary-400"
                  : "text-surface-400 hover:text-surface-200 hover:bg-white/[0.04]"
              )}
            >
              {/* Active indicator */}
              {isActive && (
                <motion.div
                  layoutId="nav-active"
                  className="absolute inset-0 rounded-xl bg-primary-600/10 border border-primary-500/20"
                  transition={{ duration: 0.2, ease: "easeOut" }}
                />
              )}

              <Icon
                className={clsx(
                  "relative w-4 h-4 flex-shrink-0 transition-colors duration-150",
                  isActive ? "text-primary-400" : "text-surface-500 group-hover:text-surface-300"
                )}
                strokeWidth={isActive ? 2.5 : 2}
              />

              {!collapsed && (
                <div className="relative flex flex-col min-w-0">
                  <span className={clsx(
                    "text-sm font-medium leading-tight truncate",
                    isActive ? "text-primary-300" : ""
                  )}>
                    {item.label}
                  </span>
                </div>
              )}

              {/* Tooltip when collapsed */}
              {collapsed && (
                <div className={clsx(
                  "absolute left-full ml-3 px-2.5 py-1.5 rounded-lg z-50",
                  "bg-surface-800 border border-white/[0.08] shadow-xl",
                  "text-xs text-surface-200 whitespace-nowrap font-medium",
                  "opacity-0 pointer-events-none group-hover:opacity-100",
                  "translate-x-1 group-hover:translate-x-0 transition-all duration-150"
                )}>
                  {item.label}
                  <div className="text-[10px] text-surface-500 mt-0.5">
                    {item.description}
                  </div>
                </div>
              )}
            </NavLink>
          );
        })}

        {/* ── Divider ───────────────────────────────────────────────────── */}
        <div className="my-2 border-t border-white/[0.04]" />

        {/* ── Resume Status Card ─────────────────────────────────────────── */}
        {!collapsed && (
          <div className={clsx(
            "mx-1 p-3 rounded-xl border transition-all duration-200",
            resumeUploaded
              ? "bg-green-500/5 border-green-500/15"
              : "bg-surface-800/50 border-white/[0.04]"
          )}>
            <div className="flex items-center gap-2 mb-1">
              <div className={clsx(
                "w-1.5 h-1.5 rounded-full flex-shrink-0",
                resumeUploaded
                  ? "bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.7)]"
                  : "bg-surface-600"
              )} />
              <span className="text-[11px] font-semibold text-surface-400 uppercase tracking-wider">
                Resume
              </span>
            </div>
            {resumeUploaded && resumeMeta ? (
              <div className="space-y-0.5">
                <p className="text-xs text-surface-300 font-medium truncate">
                  {resumeMeta.filename}
                </p>
                <p className="text-[10px] text-surface-500 font-mono">
                  {resumeMeta.skills_count} skills · {resumeMeta.experience_years ?? "?"}yr exp
                </p>
              </div>
            ) : (
              <p className="text-[11px] text-surface-500">
                No resume uploaded
              </p>
            )}
          </div>
        )}
      </nav>

      {/* ── Bottom Section ───────────────────────────────────────────────── */}
      <div className={clsx(
        "flex-shrink-0 border-t border-white/[0.06] py-3 space-y-1 px-2"
      )}>

        {/* Ollama Status */}
        {!collapsed && (
          <div className={clsx(
            "flex items-center gap-2 px-3 py-2 rounded-xl",
            "bg-surface-800/50 border border-white/[0.04]"
          )}>
            <div className={clsx(
              "w-1.5 h-1.5 rounded-full flex-shrink-0",
              ollamaStatus === "ok"       && "bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.6)] animate-pulse",
              ollamaStatus === "degraded" && "bg-yellow-400",
              ollamaStatus === "error"    && "bg-red-400",
              ollamaStatus === "checking" && "bg-surface-500 animate-pulse",
            )} />
            <div className="flex flex-col min-w-0 flex-1">
              <span className="text-[10px] font-mono text-surface-500 uppercase tracking-wider">
                Ollama
              </span>
              <span className="text-[11px] text-surface-400 truncate font-medium">
                {ollamaStatus === "ok"       && (ollamaModel || "Connected")}
                {ollamaStatus === "degraded" && "Model missing"}
                {ollamaStatus === "error"    && "Unreachable"}
                {ollamaStatus === "checking" && "Checking..."}
              </span>
            </div>
            {ollamaStatus === "ok"
              ? <Wifi    className="w-3 h-3 text-green-500 flex-shrink-0" />
              : <WifiOff className="w-3 h-3 text-red-500  flex-shrink-0" />
            }
          </div>
        )}

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className={clsx(
            "group flex items-center rounded-xl transition-all duration-150 w-full",
            "text-surface-500 hover:text-surface-300 hover:bg-white/[0.04]",
            collapsed ? "justify-center h-10 w-10 mx-auto" : "gap-3 px-3 h-9"
          )}
        >
          {theme === "dark"
            ? <Sun  className="w-4 h-4 flex-shrink-0" />
            : <Moon className="w-4 h-4 flex-shrink-0" />
          }
          {!collapsed && (
            <span className="text-sm">
              {theme === "dark" ? "Light mode" : "Dark mode"}
            </span>
          )}
        </button>

        {/* GitHub Link */}
        
          <a href="https://github.com/Swapnil-bo/Ai-Recruiter-Pipeline"
          target="_blank"
          rel="noopener noreferrer"
          className={clsx(
            "group flex items-center rounded-xl transition-all duration-150 w-full",
            "text-surface-500 hover:text-surface-300 hover:bg-white/[0.04]",
            collapsed ? "justify-center h-10 w-10 mx-auto" : "gap-3 px-3 h-9"
          )}
        >
          <Github className="w-4 h-4 flex-shrink-0" />
          {!collapsed && <span className="text-sm">Source Code</span>}
        </a>
      </div>

      {/* ── Collapse Toggle ──────────────────────────────────────────────── */}
      <button
        onClick={onToggle}
        className={clsx(
          "absolute -right-3 top-20 w-6 h-6 rounded-full z-50",
          "bg-surface-800 border border-white/[0.10] shadow-lg",
          "flex items-center justify-center",
          "text-surface-400 hover:text-surface-200",
          "transition-all duration-150 hover:scale-110",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
        )}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed
          ? <ChevronRight className="w-3 h-3" />
          : <ChevronLeft  className="w-3 h-3" />
        }
      </button>
    </aside>
  );
}

// ── Top Bar ────────────────────────────────────────────────────────────────────

function TopBar({
  pipelineRunning,
  ollamaStatus,
  resumeUploaded,
  onMobileMenuToggle,
}) {
  const location = useLocation();

  const PAGE_TITLES = {
    "/":         { title: "Dashboard",       sub: "Ranked job opportunities" },
    "/resume":   { title: "Resume",          sub: "Upload and manage your resume" },
    "/pipeline": { title: "Pipeline",        sub: "Run the AI agent pipeline" },
  };

  const current = PAGE_TITLES[location.pathname] || { title: "AI Recruiter", sub: "" };

  return (
    <header className={clsx(
      "h-16 flex-shrink-0 flex items-center justify-between",
      "px-4 sm:px-6 border-b border-white/[0.06]",
      "bg-surface-950/80 backdrop-blur-xl sticky top-0 z-30"
    )}>
      {/* Left — page title */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMobileMenuToggle}
          className="lg:hidden p-2 rounded-lg text-surface-400 hover:text-surface-200 hover:bg-white/[0.04] transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>

        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0  }}
            exit={{    opacity: 0, x:  8 }}
            transition={{ duration: 0.15 }}
          >
            <h1 className="text-base font-bold text-surface-50 leading-tight">
              {current.title}
            </h1>
            <p className="text-xs text-surface-500 hidden sm:block">
              {current.sub}
            </p>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Right — status pills */}
      <div className="flex items-center gap-2">

        {/* Pipeline running indicator */}
        {pipelineRunning && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1   }}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-primary-600/15 border border-primary-500/25"
          >
            <Loader2 className="w-3 h-3 text-primary-400 animate-spin" />
            <span className="text-[11px] font-medium text-primary-300 font-mono">
              Running
            </span>
          </motion.div>
        )}

        {/* Resume status pill */}
        <div className={clsx(
          "hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full border",
          resumeUploaded
            ? "bg-green-500/10 border-green-500/20 text-green-400"
            : "bg-surface-800 border-white/[0.06] text-surface-500"
        )}>
          {resumeUploaded
            ? <CheckCircle2 className="w-3 h-3" />
            : <AlertCircle  className="w-3 h-3" />
          }
          <span className="text-[11px] font-medium">
            {resumeUploaded ? "Resume Ready" : "No Resume"}
          </span>
        </div>

        {/* Ollama status pill */}
        <div className={clsx(
          "hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full border",
          ollamaStatus === "ok"
            ? "bg-green-500/10 border-green-500/20"
            : "bg-red-500/10 border-red-500/20"
        )}>
          <Cpu className={clsx(
            "w-3 h-3",
            ollamaStatus === "ok" ? "text-green-400" : "text-red-400"
          )} />
          <span className={clsx(
            "text-[11px] font-mono font-medium",
            ollamaStatus === "ok" ? "text-green-400" : "text-red-400"
          )}>
            {ollamaStatus === "ok" ? "Ollama" : "Offline"}
          </span>
        </div>

      </div>
    </header>
  );
}

// ── Mobile Nav Drawer ──────────────────────────────────────────────────────────

function MobileDrawer({ open, onClose }) {
  const location = useLocation();

  useEffect(() => {
    onClose();
  }, [location.pathname, onClose]);

  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1  }}
            exit={{    opacity: 0  }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
            onClick={onClose}
          />

          {/* Drawer */}
          <motion.div
            initial={{ x: "-100%" }}
            animate={{ x: 0        }}
            exit={{    x: "-100%"  }}
            transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="fixed inset-y-0 left-0 z-50 w-64 bg-surface-900 border-r border-white/[0.06] lg:hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between h-16 px-4 border-b border-white/[0.06]">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-600 to-accent-600 flex items-center justify-center">
                  <Zap className="w-4 h-4 text-white" />
                </div>
                <span className="font-bold text-surface-50">AI Recruiter</span>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-surface-400 hover:text-surface-200 hover:bg-white/[0.04] transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Nav items */}
            <nav className="p-3 space-y-1">
              {NAV_ITEMS.map((item) => {
                const Icon     = item.icon;
                const isActive = item.end
                  ? location.pathname === item.to
                  : location.pathname.startsWith(item.to);

                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={clsx(
                      "flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-150",
                      isActive
                        ? "bg-primary-600/15 text-primary-300 border border-primary-500/20"
                        : "text-surface-400 hover:text-surface-200 hover:bg-white/[0.04]"
                    )}
                  >
                    <Icon className="w-4 h-4 flex-shrink-0" strokeWidth={isActive ? 2.5 : 2} />
                    <div>
                      <p className="text-sm font-medium">{item.label}</p>
                      <p className="text-[11px] text-surface-500">{item.description}</p>
                    </div>
                  </NavLink>
                );
              })}
            </nav>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// ── Page Transition Wrapper ────────────────────────────────────────────────────

function PageTransition({ children }) {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        variants={PAGE_VARIANTS}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={PAGE_TRANSITION}
        className="flex-1 min-h-0"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

// ── Page Loader ────────────────────────────────────────────────────────────────

function PageLoader() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="relative w-10 h-10">
          <div className="absolute inset-0 rounded-full border-2 border-surface-700" />
          <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-primary-500 animate-spin" />
          <Cpu className="absolute inset-0 m-auto w-4 h-4 text-surface-500" />
        </div>
        <p className="text-sm text-surface-500 font-mono tracking-wide">
          Loading...
        </p>
      </div>
    </div>
  );
}

// ── Not Found Page ─────────────────────────────────────────────────────────────

function NotFound() {
  const navigate = useNavigate();

  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center space-y-6 max-w-md">
        <div className="text-8xl font-black text-surface-800 font-mono">
          404
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-bold text-surface-200">
            Page not found
          </h2>
          <p className="text-surface-500 text-sm">
            The page you're looking for doesn't exist or has been moved.
          </p>
        </div>
        <button
          onClick={() => navigate("/")}
          className={clsx(
            "inline-flex items-center gap-2 px-5 py-2.5 rounded-xl",
            "bg-primary-600 hover:bg-primary-500 text-white font-medium text-sm",
            "transition-all duration-150 shadow-lg hover:shadow-primary-500/25"
          )}
        >
          <LayoutDashboard className="w-4 h-4" />
          Back to Dashboard
        </button>
      </div>
    </div>
  );
}

// ── Background Effects ─────────────────────────────────────────────────────────

function BackgroundEffects() {
  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-0" aria-hidden="true">
      {/* Top ambient */}
      <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[800px] h-[400px] rounded-full opacity-30"
        style={{
          background: "radial-gradient(ellipse, rgba(59,130,246,0.08) 0%, transparent 70%)",
          filter: "blur(40px)",
        }}
      />
      {/* Bottom right ambient */}
      <div className="absolute -bottom-20 -right-20 w-[500px] h-[500px] rounded-full opacity-20"
        style={{
          background: "radial-gradient(ellipse, rgba(139,92,246,0.10) 0%, transparent 70%)",
          filter: "blur(60px)",
        }}
      />
      {/* Dot grid */}
      <div
        className="absolute inset-0 opacity-[0.015]"
        style={{
          backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.8) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }}
      />
    </div>
  );
}

// ── App Shell ──────────────────────────────────────────────────────────────────

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen,   setMobileMenuOpen]   = useState(false);

  const { status: ollamaStatus, model: ollamaModel } = useOllamaHealth();
  const { uploaded: resumeUploaded, meta: resumeMeta } = useResumeStatus();
  const pipelineRunning = usePipelineRunning();
  const location = useLocation();

  // Persist sidebar state
  useEffect(() => {
    try {
      const saved = localStorage.getItem("sidebar-collapsed");
      if (saved !== null) setSidebarCollapsed(JSON.parse(saved));
    } catch {}
  }, []);

  const handleSidebarToggle = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem("sidebar-collapsed", JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  // Ollama warning toast on startup
  useEffect(() => {
    if (ollamaStatus === "error") {
      toast.error(
        "Ollama is not running. Start it with: ollama serve",
        { id: "ollama-error", duration: 8000 }
      );
    }
    if (ollamaStatus === "degraded") {
      toast(
        "Ollama is running but the model is missing. Run: ollama pull qwen2.5:7b",
        { id: "ollama-degraded", duration: 8000, icon: "⚠️" }
      );
    }
  }, [ollamaStatus]);

  // Resume upload reminder
  useEffect(() => {
    if (!resumeUploaded && location.pathname === "/") {
      const timer = setTimeout(() => {
        toast(
          "Upload your resume to start matching jobs.",
          { id: "resume-reminder", duration: 5000, icon: "📄" }
        );
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [resumeUploaded, location.pathname]);

  return (
    <>
      <BackgroundEffects />

      <div className="relative flex h-screen overflow-hidden z-10">

        {/* ── Sidebar (desktop) ────────────────────────────────────────── */}
        <div className="hidden lg:block">
          <Sidebar
            collapsed={sidebarCollapsed}
            onToggle={handleSidebarToggle}
            ollamaStatus={ollamaStatus}
            ollamaModel={ollamaModel}
            resumeUploaded={resumeUploaded}
            resumeMeta={resumeMeta}
            pipelineRunning={pipelineRunning}
          />
        </div>

        {/* ── Mobile Drawer ────────────────────────────────────────────── */}
        <MobileDrawer
          open={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
        />

        {/* ── Main Content ─────────────────────────────────────────────── */}
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">

          <TopBar
            pipelineRunning={pipelineRunning}
            ollamaStatus={ollamaStatus}
            resumeUploaded={resumeUploaded}
            onMobileMenuToggle={() => setMobileMenuOpen(true)}
          />

          {/* ── Scrollable Page Area ──────────────────────────────────── */}
          <main className="flex-1 overflow-y-auto overflow-x-hidden">
            <Suspense fallback={<PageLoader />}>
              <PageTransition>
                <Routes location={location}>
                  <Route
                    path="/"
                    element={
                      <Dashboard
                        resumeUploaded={resumeUploaded}
                        pipelineRunning={pipelineRunning}
                      />
                    }
                  />
                  <Route
                    path="/resume"
                    element={
                      <ResumeUpload
                        resumeUploaded={resumeUploaded}
                        resumeMeta={resumeMeta}
                      />
                    }
                  />
                  <Route
                    path="/pipeline"
                    element={
                      <PipelineStatus
                        ollamaStatus={ollamaStatus}
                        resumeUploaded={resumeUploaded}
                      />
                    }
                  />
                  <Route
                    path="/jobs/:jobId"
                    element={<JobDetail />}
                  />
                  <Route path="/404" element={<NotFound />} />
                  <Route path="*"    element={<Navigate to="/404" replace />} />
                </Routes>
              </PageTransition>
            </Suspense>
          </main>

        </div>
      </div>
    </>
  );
}