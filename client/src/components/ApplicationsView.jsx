import { formatDate, money } from "../lib/format.js";
import SegmentBadge from "./SegmentBadge.jsx";
import StatusBadge from "./StatusBadge.jsx";

export default function ApplicationsView({ applications, onSelect, selectedId }) {
  if (applications.length === 0) {
    return (
      <section className="panel panel--wide panel--empty">
        <header className="panel__header">
          <p className="panel__eyebrow">Application registry</p>
          <h2>No applications yet</h2>
        </header>
        <p className="panel__lede">
          Run an evaluation from the workspace to populate this ledger with routed applications.
        </p>
      </section>
    );
  }

  const selected = applications.find((app) => app.id === selectedId);

  return (
    <section className="applications-layout">
      <div className="panel panel--table">
        <header className="panel__header">
          <p className="panel__eyebrow">Application registry</p>
          <h2>Recent evaluations</h2>
        </header>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Applicant</th>
                <th>Segment</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Offers</th>
              </tr>
            </thead>
            <tbody>
              {applications.map((application) => (
                <tr
                  key={application.id}
                  className={application.id === selectedId ? "is-selected" : ""}
                  aria-selected={application.id === selectedId}
                  onClick={() => onSelect(application.id)}
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelect(application.id);
                    }
                  }}
                >
                  <td>
                    <strong>{application.applicant?.name || "Unknown"}</strong>
                    <span className="mono table-sub">{application.applicant?.pan}</span>
                  </td>
                  <td>
                    <SegmentBadge segment={application.eligibility?.profile?.segment} />
                  </td>
                  <td className="mono">{money(application.amount)}</td>
                  <td>
                    <StatusBadge status={application.status} />
                  </td>
                  <td className="mono">{application.offers?.length ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <aside className="panel panel--detail">
          <header className="panel__header">
            <p className="panel__eyebrow">Selected application</p>
            <h2>{selected.applicant?.name}</h2>
            <p className="panel__meta mono">{formatDate(selected.createdAt)}</p>
          </header>

          <dl className="detail-list">
            <div>
              <dt>FOIR</dt>
              <dd className="mono">
                {selected.eligibility?.foir?.foirPercent != null
                  ? `${selected.eligibility.foir.foirPercent}%`
                  : "—"}
              </dd>
            </div>
            <div>
              <dt>Default risk</dt>
              <dd className="mono">{Math.round((selected.risk?.defaultProbability || 0) * 100)}%</dd>
            </div>
            <div>
              <dt>Routed to</dt>
              <dd className="mono">{selected.routedLenderCode || "Not routed"}</dd>
            </div>
          </dl>

          {selected.offers?.length > 0 && (
            <div className="mini-offers">
              <h3>Top offer</h3>
              <p>
                {selected.offers[0].lenderName} · {selected.offers[0].interestRate}% · EMI{" "}
                {money(selected.offers[0].monthlyPayment)}
              </p>
            </div>
          )}
        </aside>
      )}
    </section>
  );
}
