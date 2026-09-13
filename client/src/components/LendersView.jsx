import { money, percent } from "../lib/format.js";
import { categoryLabels } from "../lib/presets.js";

export default function LendersView({ lenders }) {
  return (
    <section className="lenders-layout">
      <header className="hero hero--compact">
        <h2>Partners on this demo</h2>
        <p className="hero__lede">
          Each mock lender serves a different Indian segment: prime salaried, near-prime, thin-file,
          or tier-2/3 co-lending.
        </p>
      </header>

      <div className="lender-grid">
        {lenders.map((lender) => (
          <article key={lender.code} className="lender-card">
            <header>
              <p className="lender-card__category">{categoryLabels[lender.category] || lender.category}</p>
              <h3>{lender.name}</h3>
              <p className="mono lender-card__code">{lender.code}</p>
            </header>

            <p className="lender-card__description">{lender.description}</p>

            <ul className="lender-card__segments">
              {lender.servesPrime && <li>Prime</li>}
              {lender.servesNearPrime && <li>Near-prime</li>}
              {lender.servesThinFile && <li>Thin-file</li>}
            </ul>

            <dl className="lender-card__stats">
              <div>
                <dt>Min income</dt>
                <dd className="mono">{money(lender.minIncome)}</dd>
              </div>
              <div>
                <dt>Max FOIR</dt>
                <dd className="mono">{percent(lender.maxFoir)}</dd>
              </div>
              <div>
                <dt>Max ticket</dt>
                <dd className="mono">{money(lender.maxAmount)}</dd>
              </div>
              <div>
                <dt>Base rate</dt>
                <dd className="mono">{lender.baseInterestRate}%</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}
