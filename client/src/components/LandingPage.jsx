import { money, percent } from "../lib/format.js";

const features = [
  {
    title: "Eligibility engine",
    detail: "Configurable lender policies evaluate income, FOIR, credit score, and profile segment.",
  },
  {
    title: "Risk assessment",
    detail: "Structured default probability from an ONNX model with heuristic fallback.",
  },
  {
    title: "Lender mesh",
    detail: "Parallel mock lender calls with retries, timeouts, and circuit breakers.",
  },
  {
    title: "Offer ranking",
    detail: "Weighted scoring across rate, fee, approval probability, and profile fit.",
  },
];

export default function LandingPage({ onNavigate, lenders, metrics }) {
  const maxOffer = lenders.reduce((max, lender) => Math.max(max, lender.maxAmount || 0), 0);

  return (
    <div className="landing">
      <header className="landing-header">
        <button type="button" className="landing-brand" onClick={() => onNavigate("home")}>
          <span className="landing-brand__icon" aria-hidden="true">
            CR
          </span>
          <span>
            <strong>CredRoute</strong>
            <small>Digital lending marketplace</small>
          </span>
        </button>

        <nav className="landing-nav" aria-label="Landing">
          <a href="#platform">Platform</a>
          <a href="#flow">Flow</a>
          <a href="#faq">FAQ</a>
        </nav>

        <button type="button" className="btn btn--primary" onClick={() => onNavigate("workspace")}>
          Apply now
        </button>
      </header>

      <section className="landing-hero">
        <div className="landing-hero__copy">
          <p className="landing-hero__eyebrow">
            {maxOffer ? `Up to ${money(maxOffer)}` : "Digital lending marketplace"}
          </p>
          <h1>Digital lending marketplace and credit decisioning platform</h1>
          <p className="landing-hero__lede">
            Evaluate eligibility, score risk, query simulated lending partners, rank offers, and
            route applications through a backend built for reliability, not templates.
          </p>
          <div className="landing-hero__actions">
            <button type="button" className="btn btn--primary" onClick={() => onNavigate("lenders")}>
              View current offers
            </button>
            <button type="button" className="btn btn--secondary" onClick={() => onNavigate("workspace")}>
              Run live demo
            </button>
          </div>
        </div>

        <aside className="landing-preview" aria-label="Live platform preview">
          <div className="landing-preview__frame">
            <div className="landing-preview__bar">
              <span>CredRoute workspace</span>
              <span className="mono">{metrics ? `${metrics.applications} apps processed` : "Loading metrics…"}</span>
            </div>
            <dl className="landing-preview__stats">
              <div>
                <dt>Lender success</dt>
                <dd className="mono">{metrics ? percent(metrics.lenderSuccessRate) : "—"}</dd>
              </div>
              <div>
                <dt>Avg latency</dt>
                <dd className="mono">{metrics ? `${metrics.averageLatencyMs}ms` : "—"}</dd>
              </div>
              <div>
                <dt>Partners</dt>
                <dd className="mono">{lenders.length || "—"}</dd>
              </div>
            </dl>
            <p className="landing-preview__note">
              This panel reads from the running API. Submit an application in the workspace to update
              these numbers.
            </p>
          </div>
        </aside>
      </section>

      <section className="landing-features" id="platform">
        {features.map((feature) => (
          <article key={feature.title} className="landing-feature-card">
            <h2>{feature.title}</h2>
            <p>{feature.detail}</p>
          </article>
        ))}
      </section>

      <section className="landing-section" id="flow">
        <h2>Application flow</h2>
        <ol className="landing-flow-list">
          <li>Create loan application and submit financial information</li>
          <li>Run eligibility evaluation and risk assessment</li>
          <li>Query multiple mock lenders in parallel</li>
          <li>Receive, rank, and compare offers</li>
          <li>Select the recommended offer and route the application</li>
          <li>Track status in the applications registry</li>
        </ol>
      </section>

      <section className="landing-section landing-section--faq" id="faq">
        <h2>FAQ</h2>
        <dl className="landing-faq">
          <div>
            <dt>Does CredRoute issue real loans?</dt>
            <dd>No. All lenders and outcomes are simulated for portfolio and interview use.</dd>
          </div>
          <div>
            <dt>What happens when a lender fails?</dt>
            <dd>Healthy lenders still return offers. Failures are retried and isolated via circuit breakers.</dd>
          </div>
          <div>
            <dt>What data should I enter?</dt>
            <dd>Use synthetic demo data only. Do not enter real PAN, Aadhaar, or bank account numbers.</dd>
          </div>
        </dl>
      </section>

      <footer className="landing-footer">
        <p>CredRoute · Portfolio demo · Mock lenders · Synthetic data only</p>
      </footer>
    </div>
  );
}
