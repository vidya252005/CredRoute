import { percent } from "../lib/format.js";

export default function SiteHeader({ view, onNavigate }) {
  const links = [
    { id: "home", label: "Home" },
    { id: "workspace", label: "Apply" },
    { id: "applications", label: "Applications" },
    { id: "lenders", label: "Partners" },
    { id: "admin", label: "Admin" },
  ];

  return (
    <header className="app-header">
      <button type="button" className="wordmark" onClick={() => onNavigate("home")}>
        credroute
      </button>

      <nav className="app-nav" aria-label="Platform">
        {links.map((link) => (
          <button
            key={link.id}
            type="button"
            className={view === link.id ? "is-active" : ""}
            aria-current={view === link.id ? "page" : undefined}
            onClick={() => onNavigate(link.id)}
          >
            {link.label}
          </button>
        ))}
      </nav>
    </header>
  );
}

export function WorkspaceIntro() {
  return (
    <section className="workspace-intro">
      <h1>Check your offers</h1>
      <p>
        Enter the request, get a credit decision, then route to the top-ranked mock lender.
      </p>
    </section>
  );
}

export function MetricsFooter({ metrics }) {
  if (!metrics) return null;

  return (
    <footer className="metrics-footer">
      <div>
        <span>Applications</span>
        <strong>{metrics.applications}</strong>
      </div>
      <div>
        <span>Lender success</span>
        <strong>{percent(metrics.lenderSuccessRate)}</strong>
      </div>
      <div>
        <span>Average latency</span>
        <strong>{metrics.averageLatencyMs}ms</strong>
      </div>
      <div>
        <span>Cache hit rate</span>
        <strong>{percent(metrics.cacheHitRate)}</strong>
      </div>
      <div>
        <span>Storage</span>
        <strong>{metrics.storage}</strong>
      </div>
    </footer>
  );
}
