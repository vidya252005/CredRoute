import { money, percent } from "../lib/format.js";
import SegmentBadge from "./SegmentBadge.jsx";
import StatusBadge from "./StatusBadge.jsx";

export default function ResultPanel({ result, loading, busy, onRoute, onRepay }) {
  if (!result) {
    return (
      <section className="panel panel--result panel--empty" aria-live="polite">
        <header className="panel__header">
          <p className="panel__eyebrow">Decision ledger</p>
          <h2>Your routing outcome appears here</h2>
        </header>
        <p className="panel__lede">
          Submit a loan request to see eligibility checks, default and fraud risk scores,
          lender mesh responses, and ranked offers.
        </p>
        <ul className="ledger-hints">
          <li>Default and fraud probabilities from the credit risk engine</li>
          <li>Per-lender approve/ineligible/failed responses with reasons</li>
          <li>Offers ranked by profile fit, not rate alone</li>
        </ul>
      </section>
    );
  }

  const recommended = result.offers?.find((offer) => offer.rank === 1);
  const segment = result.eligibility?.profile?.segment;

  return (
    <section className="panel panel--result" aria-live="polite">
      <header className="panel__header panel__header--split">
        <div>
          <p className="panel__eyebrow">Decision ledger</p>
          <h2>{result.applicant?.name || "Applicant"}</h2>
        </div>
        <StatusBadge status={result.status} />
      </header>

      <div className="ledger-grid">
        {result.decision && (
          <article className="ledger-card ledger-card--decision">
            <p className="ledger-card__label">Credit decision</p>
            <p className="ledger-card__value mono">{result.decision.decision?.toUpperCase()}</p>
            <p className="ledger-card__detail">{result.decision.reasons?.[0]}</p>
          </article>
        )}

        <article className="ledger-card">
          <p className="ledger-card__label">Profile segment</p>
          <SegmentBadge segment={segment} />
          <p className="ledger-card__detail">{result.eligibility?.profile?.detail}</p>
        </article>

        <article className="ledger-card">
          <p className="ledger-card__label">FOIR</p>
          <p className="ledger-card__value mono">
            {result.eligibility?.foir?.foirPercent != null ? `${result.eligibility.foir.foirPercent}%` : "—"}
          </p>
          <p className="ledger-card__detail">
            Proposed EMI {money(result.eligibility?.foir?.proposedEmi)} · total obligations{" "}
            {money(result.eligibility?.foir?.totalEmi)}
          </p>
        </article>

        <article className="ledger-card">
          <p className="ledger-card__label">Default risk</p>
          <p className="ledger-card__value mono">{percent(result.risk?.defaultProbability)}</p>
          <p className="ledger-card__detail">
            Model: {result.risk?.modelSource || "unknown"}
            {result.risk?.modelAuc ? ` · AUC ${result.risk.modelAuc}` : ""}
          </p>
        </article>

        <article className="ledger-card">
          <p className="ledger-card__label">Fraud risk</p>
          <p className="ledger-card__value mono">
            {percent(result.risk?.fraudProbability ?? result.fraud?.fraudProbability)}
          </p>
          <p className="ledger-card__detail">
            {(result.fraud?.signals || result.risk?.fraud?.signals || []).join(" · ") ||
              "No fraud signals flagged"}
          </p>
        </article>

        <article className="ledger-card">
          <p className="ledger-card__label">Risk band</p>
          <p className="ledger-card__value mono">{result.risk?.riskBand || "—"}</p>
          <p className="ledger-card__detail">
            Structured: {percent(result.risk?.structuredProbability ?? result.risk?.defaultProbability)}
            {result.risk?.finbertSignal?.stressScore != null &&
              ` · Text stress ${Math.round(result.risk.finbertSignal.stressScore * 100)}%`}
          </p>
        </article>

        {result.personalizedOffer && (
          <article className="ledger-card ledger-card--offer">
            <p className="ledger-card__label">Personalized offer</p>
            <p className="ledger-card__value mono">{money(result.personalizedOffer.offeredAmount)}</p>
            <p className="ledger-card__detail">
              {result.personalizedOffer.apr}% APR · {result.personalizedOffer.tenureMonths} mo · EMI{" "}
              {money(result.personalizedOffer.monthlyPayment)}
              {result.scoredInMs != null ? ` · scored in ${result.scoredInMs}ms` : ""}
            </p>
          </article>
        )}

        {result.altData && (
          <article className="ledger-card">
            <p className="ledger-card__label">Alt-data score</p>
            <p className="ledger-card__value mono">
              {result.altData.used ? percent(result.altData.altDataScore) : "Not used"}
            </p>
            <p className="ledger-card__detail">
              {result.altData.used
                ? result.altData.thinFileEligible
                  ? "Thin-file path — bureau PD is advisory"
                  : "Thin-file signals below cutoff"
                : "Bureau path — CIBIL at or above 650"}
            </p>
          </article>
        )}
      </div>

      {result.creditLine && (
        <div className="credit-line">
          <h3>Credit line</h3>
          <p className="panel__lede">
            Current limit {money(result.creditLine.currentLimit)}
            {result.creditLine.firstLoan ? " · first loan (starter cap)" : ""}
            {" · "}
            next limit after on-time repayment {money(result.creditLine.nextLimit)} ·{" "}
            {result.creditLine.onTimeRepayments} on-time repayment(s)
          </p>
        </div>
      )}

      {result.adverseAction?.reasons?.length > 0 && (
        <div className="adverse-action">
          <h3>Adverse-action reasons</h3>
          <ul>
            {result.adverseAction.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <p className="panel__meta">{result.adverseAction.notice}</p>
        </div>
      )}

      {result.consent && (
        <div className="consent-ledger">
          <h3>Consent ledger</h3>
          <ul>
            {result.consent.purposes?.map((purpose) => (
              <li key={purpose.id}>{purpose.label}</li>
            ))}
          </ul>
          <p className="panel__meta">
            Not collected: {(result.consent.notCollected || []).join(", ")}
          </p>
        </div>
      )}

      {result.altData?.reasons?.length > 0 && result.altData.used && (
        <div className="checks-list">
          <h3>Alternative-data signals</h3>
          <ul>
            {result.altData.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <p className="panel__meta">{result.altData.disclaimer}</p>
        </div>
      )}

      {(result.risk?.riskFactors?.length > 0 || result.risk?.shapFactors?.length > 0) && (
        <div className="checks-list">
          <h3>Risk explainability</h3>
          {result.risk.riskFactors?.length > 0 && (
            <>
              <p className="panel__meta">Risk factors</p>
              <ul>
                {result.risk.riskFactors.map((factor) => (
                  <li key={factor}>{factor}</li>
                ))}
              </ul>
            </>
          )}
          {result.risk.shapFactors?.length > 0 && (
            <>
              <p className="panel__meta">Top SHAP contributors</p>
              <ul>
                {result.risk.shapFactors.map((factor) => (
                  <li key={factor.feature}>
                    {factor.feature}: {factor.direction}
                    {factor.impact != null ? ` (${factor.impact})` : ""}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {result.eligibility?.checks?.length > 0 && (
        <div className="checks-list">
          <h3>Eligibility checks</h3>
          <ul>
            {result.eligibility.checks.map((check) => (
              <li key={check.label} className={check.passed ? "pass" : "fail"}>
                <span>{check.label}</span>
                <span>{check.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.lenderAttempts?.length > 0 && (
        <div className="lender-responses">
          <h3>Lender mesh responses</h3>
          <ul>
            {result.lenderAttempts.map((attempt) => (
              <li key={attempt.lenderCode} className={`response response--${attempt.status}`}>
                <span className="mono">{attempt.lenderCode}</span>
                <span>{attempt.status}</span>
                {attempt.latencyMs != null && <span className="mono">{attempt.latencyMs}ms</span>}
                {attempt.message && <span className="response__message">{attempt.message}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.offers?.length > 0 && (
        <div className="offers-stack">
          <h3>Ranked offers</h3>
          {result.offers.map((offer) => (
            <article
              key={offer.id}
              className={`offer-card${offer.rank === 1 ? " offer-card--recommended" : ""}`}
            >
              <header>
                <p className="offer-card__rank">
                  {offer.rank === 1 ? "Recommended route" : `Alternative ${offer.rank}`}
                </p>
                <h4>{offer.lenderName}</h4>
              </header>
              <dl className="offer-card__stats">
                <div>
                  <dt>Rate</dt>
                  <dd className="mono">{offer.interestRate}%</dd>
                </div>
                <div>
                  <dt>EMI</dt>
                  <dd className="mono">{money(offer.monthlyPayment)}</dd>
                </div>
                <div>
                  <dt>Fee</dt>
                  <dd className="mono">{money(offer.processingFee)}</dd>
                </div>
                <div>
                  <dt>Approval</dt>
                  <dd className="mono">{percent(offer.approvalProbability)}</dd>
                </div>
              </dl>
              {offer.routingReason && <p className="offer-card__reason">{offer.routingReason}</p>}
            </article>
          ))}
        </div>
      )}

      {recommended && ["offers_ready", "under_review"].includes(result.status) && (
        <button type="button" className="btn btn--primary btn--wide" onClick={onRoute} disabled={loading}>
          {busy === "routing" || loading ? "Routing application…" : `Route to ${recommended.lenderName}`}
        </button>
      )}

      {result.status === "routed" && (
        <>
          <p className="routed-confirmation">
            Application confirmed with <span className="mono">{result.routedLenderCode}</span>
          </p>
          <button type="button" className="btn btn--secondary btn--wide" onClick={onRepay} disabled={loading}>
            {busy === "repaying" || loading ? "Recording repayment…" : "Simulate on-time repayment (raise limit)"}
          </button>
        </>
      )}
    </section>
  );
}
