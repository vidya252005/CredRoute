import { numericFields } from "../lib/presets.js";

export default function ApplicationForm({
  form,
  fieldErrors,
  loading,
  busy,
  onChange,
  onSubmit,
  onPreset,
}) {
  return (
    <section className="panel panel--form">
      <header className="panel__header">
        <h2>Loan request</h2>
      </header>

      <div className="preset-row">
        <button type="button" className="chip" onClick={() => onPreset("prime")}>
          Prime salaried
        </button>
        <button type="button" className="chip" onClick={() => onPreset("nearPrime")}>
          Near-prime self-employed
        </button>
        <button type="button" className="chip" onClick={() => onPreset("thinFile")}>
          Thin-file gig worker
        </button>
      </div>

      <form className="intake-form" onSubmit={onSubmit} noValidate>
        <div className="field-grid">
          <label className={`field${fieldErrors.name ? " field--error" : ""}`}>
            <span>Full name</span>
            <input name="name" value={form.name} onChange={onChange} autoComplete="name" required />
            {fieldErrors.name && <em>{fieldErrors.name}</em>}
          </label>

          <label className={`field${fieldErrors.pan ? " field--error" : ""}`}>
            <span>PAN</span>
            <input
              name="pan"
              value={form.pan}
              onChange={onChange}
              className="mono"
              autoComplete="off"
              spellCheck="false"
              required
            />
            {fieldErrors.pan && <em>{fieldErrors.pan}</em>}
          </label>

          <label className={`field${fieldErrors.age ? " field--error" : ""}`}>
            <span>Age</span>
            <input name="age" type="number" min="21" max="60" value={form.age} onChange={onChange} required />
            {fieldErrors.age && <em>{fieldErrors.age}</em>}
          </label>

          <label className={`field${fieldErrors.incomeType ? " field--error" : ""}`}>
            <span>Income type</span>
            <select name="incomeType" value={form.incomeType} onChange={onChange}>
              <option value="salaried">Salaried</option>
              <option value="self_employed">Self-employed</option>
              <option value="msme">MSME</option>
              <option value="gig">Gig worker</option>
            </select>
            {fieldErrors.incomeType && <em>{fieldErrors.incomeType}</em>}
          </label>

          <label className={`field${fieldErrors.monthlyIncome ? " field--error" : ""}`}>
            <span>Monthly income</span>
            <input
              name="monthlyIncome"
              type="number"
              min="15000"
              value={form.monthlyIncome}
              onChange={onChange}
              required
            />
            {fieldErrors.monthlyIncome && <em>{fieldErrors.monthlyIncome}</em>}
          </label>

          <label className={`field${fieldErrors.cibilScore ? " field--error" : ""}`}>
            <span>CIBIL score</span>
            <input
              name="cibilScore"
              type="number"
              min="300"
              max="900"
              value={form.cibilScore}
              onChange={onChange}
              placeholder="Leave blank for thin-file"
            />
            {fieldErrors.cibilScore && <em>{fieldErrors.cibilScore}</em>}
          </label>

          <label className={`field${fieldErrors.existingEmis ? " field--error" : ""}`}>
            <span>Existing EMIs</span>
            <input
              name="existingEmis"
              type="number"
              min="0"
              value={form.existingEmis}
              onChange={onChange}
              required
            />
            {fieldErrors.existingEmis && <em>{fieldErrors.existingEmis}</em>}
          </label>

          <label className={`field${fieldErrors.bankStatementAvgBalance ? " field--error" : ""}`}>
            <span>Avg bank balance</span>
            <input
              name="bankStatementAvgBalance"
              type="number"
              min="0"
              value={form.bankStatementAvgBalance}
              onChange={onChange}
              required
            />
            <small>Alternate data signal for thin-file routing</small>
            {fieldErrors.bankStatementAvgBalance && <em>{fieldErrors.bankStatementAvgBalance}</em>}
          </label>

          <label className={`field${fieldErrors.cityTier ? " field--error" : ""}`}>
            <span>City tier</span>
            <select name="cityTier" value={form.cityTier} onChange={onChange}>
              <option value={1}>Tier 1 — metro</option>
              <option value={2}>Tier 2</option>
              <option value={3}>Tier 3</option>
            </select>
            {fieldErrors.cityTier && <em>{fieldErrors.cityTier}</em>}
          </label>

          <label className={`field${fieldErrors.amount ? " field--error" : ""}`}>
            <span>Loan amount</span>
            <input name="amount" type="number" min="10000" value={form.amount} onChange={onChange} required />
            {fieldErrors.amount && <em>{fieldErrors.amount}</em>}
          </label>

          <label className={`field field--wide${fieldErrors.tenureMonths ? " field--error" : ""}`}>
            <span>Tenure</span>
            <select name="tenureMonths" value={form.tenureMonths} onChange={onChange}>
              {[6, 9, 12, 18, 24, 36].map((months) => (
                <option value={months} key={months}>
                  {months} months
                </option>
              ))}
            </select>
            {fieldErrors.tenureMonths && <em>{fieldErrors.tenureMonths}</em>}
          </label>
          <label className="field field--wide">
            <span>Financial notes (optional)</span>
            <textarea
              name="financialNotes"
              rows={3}
              value={form.financialNotes || ""}
              onChange={onChange}
              placeholder="Example: Borrower has recently experienced inconsistent income from gig work."
            />
            <small>Used only as an auxiliary FinBERT text signal, not a credit decision.</small>
          </label>
        </div>

        <label className={`consent-row${fieldErrors.consentAltData ? " field--error" : ""}`}>
          <input
            type="checkbox"
            name="consentAltData"
            checked={Boolean(form.consentAltData)}
            onChange={onChange}
          />
          <span>
            I consent to CredRoute using my declared CIBIL, bank-balance cash-flow, repayment history,
            and a <strong>synthetic device/SIM proxy</strong> (not SMS, contacts, or live handset data)
            to underwrite this request.
          </span>
          {fieldErrors.consentAltData && <em>{fieldErrors.consentAltData}</em>}
        </label>

        <button type="submit" className="btn btn--primary btn--wide" disabled={loading}>
          {busy === "evaluating"
            ? "Evaluating eligibility…"
            : busy === "routing"
              ? "Routing application…"
              : busy === "repaying"
                ? "Recording repayment…"
                : "Get decision"}
        </button>
      </form>
    </section>
  );
}

export { numericFields };
