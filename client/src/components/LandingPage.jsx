import CreditCard from "./CreditCard.jsx";
import { money } from "../lib/format.js";

const flow = [
  "Tell us income, CIBIL, and the amount you want.",
  "We score risk and check FOIR against platform rules.",
  "Mock lenders reply in parallel. Failures stay isolated.",
  "You pick a ranked offer and we route the application.",
];

export default function LandingPage({ onNavigate, lenders, metrics }) {
  const maxOffer = lenders.reduce((max, lender) => Math.max(max, lender.maxAmount || 0), 0);

  return (
    <div className="landing">
      <header className="landing-header">
        <button type="button" className="wordmark" onClick={() => onNavigate("home")}>
          credroute
        </button>
        <nav className="landing-nav" aria-label="Landing">
          <a href="#how">How it works</a>
          <a href="#faq">FAQ</a>
        </nav>
        <button type="button" className="btn btn--primary" onClick={() => onNavigate("workspace")}>
          Apply
        </button>
      </header>

      <section className="landing-hero">
        <div className="landing-hero__copy">
          <h1>Unlock your credit line.</h1>
          <p className="landing-hero__lede">
            CredRoute decides whether you qualify, then asks mock Indian lenders at the same time
            and ranks what they offer. No real money moves.
          </p>
          <div className="landing-hero__actions">
            <button type="button" className="btn btn--primary" onClick={() => onNavigate("workspace")}>
              Apply
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => onNavigate("lenders")}>
              See partners
            </button>
          </div>
        </div>

        <CreditCard
          amount={maxOffer ? money(maxOffer) : "—"}
          name="Member card"
          meta={maxOffer ? "Largest ticket among live partners" : "Partner catalog loading"}
          footer={lenders.length ? `${lenders.length} partners` : null}
        />
      </section>

      <section className="landing-how" id="how">
        <h2>How a request moves</h2>
        <ol>
          {flow.map((step, index) => (
            <li key={step}>
              <span>{index + 1}</span>
              {step}
            </li>
          ))}
        </ol>
      </section>

      <section className="landing-faq" id="faq">
        <h2>FAQ</h2>
        <dl>
          <div>
            <dt>Does CredRoute issue real loans?</dt>
            <dd>No. Lenders and outcomes are simulated for this portfolio demo.</dd>
          </div>
          <div>
            <dt>What happens if a lender times out?</dt>
            <dd>The others still return. We retry and open a circuit if one partner keeps failing.</dd>
          </div>
          <div>
            <dt>What should I type in?</dt>
            <dd>Use the demo presets. Do not enter a real PAN or bank account.</dd>
          </div>
        </dl>
      </section>

      <footer className="landing-footer">
        <p>
          {metrics
            ? `${metrics.applications} applications on this machine`
            : "Metrics load from the API"}
          . Mock lenders. Synthetic data.
        </p>
      </footer>
    </div>
  );
}
