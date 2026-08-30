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
      <button type="button" className="app-header__brand" onClick={() => onNavigate("home")}>
        <span className="app-header__icon" aria-hidden="true">CR</span>
        <span>
          <strong>CredRoute</strong>
          <small>Digital lending marketplace</small>
        </span>
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
      <p className="workspace-intro__kicker">Application flow</p>
      <h1>Evaluate, rank, and route your loan request</h1>
      <p>
        Submit financial information, run eligibility and risk assessment, query mock lenders in
        parallel, compare ranked offers, and route to the recommended partner.
      </p>
    </section>
  );
}

export function MetricsFooter({ metrics }) {
  if (!metrics) return null;

  return (
    <footer className="metrics-footer">
      <div>
        <span className="metrics-footer__label">Applications</span>
        <strong className="mono">{metrics.applications}</strong>
      </div>
      <div>
        <span className="metrics-footer__label">Lender success</span>
        <strong className="mono">{percent(metrics.lenderSuccessRate)}</strong>
      </div>
      <div>
        <span className="metrics-footer__label">Avg latency</span>
        <strong className="mono">{metrics.averageLatencyMs}ms</strong>
      </div>
      <div>
        <span className="metrics-footer__label">Cache hit rate</span>
        <strong className="mono">{percent(metrics.cacheHitRate)}</strong>
      </div>
      <div>
        <span className="metrics-footer__label">Storage</span>
        <strong className="mono">{metrics.storage}</strong>
      </div>
    </footer>
  );
}
