import { useEffect, useState } from "react";
import {
  fetchAdminApplications,
  fetchAdminEvents,
  fetchAdminLenders,
  fetchAdminMetrics,
  fetchAdminMlMetrics,
  getToken,
  toggleLender,
} from "../lib/api.js";
import { money, percent } from "../lib/format.js";
import AuthPanel from "./AuthPanel.jsx";
import Skeleton from "./Skeleton.jsx";

export default function AdminView({ onRefreshLenders }) {
  const [mlMetrics, setMlMetrics] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [applications, setApplications] = useState([]);
  const [events, setEvents] = useState([]);
  const [adminLenders, setAdminLenders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [signedIn, setSignedIn] = useState(Boolean(getToken()));

  const loadAdmin = async () => {
    if (!getToken()) return;
    setLoading(true);
    setError("");
    try {
      const [metricsData, mlData, appsData, eventsData, lendersData] = await Promise.all([
        fetchAdminMetrics(),
        fetchAdminMlMetrics(),
        fetchAdminApplications(),
        fetchAdminEvents(),
        fetchAdminLenders(),
      ]);
      setMetrics(metricsData);
      setMlMetrics(mlData);
      setApplications(appsData);
      setEvents(eventsData);
      setAdminLenders(lendersData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (signedIn) loadAdmin();
  }, [signedIn]);

  const handleToggleLender = async (lender) => {
    try {
      await toggleLender(lender.id, !lender.active);
      await onRefreshLenders?.();
      await loadAdmin();
    } catch (toggleError) {
      setError(toggleError.message);
    }
  };

  return (
    <section className="admin-layout">
      <header className="panel">
        <h1>Admin console</h1>
        <p className="panel__lede">
          Inspect applications, lender failures, circuit breakers, and partner configuration.
        </p>
      </header>

      <AuthPanel
        onAuthenticated={() => {
          setSignedIn(Boolean(getToken()));
        }}
      />

      {error && <p className="field-error">{error}</p>}

      {!signedIn && (
        <p className="panel__lede">Sign in with the demo admin account to load operational data.</p>
      )}

      {signedIn && loading && <Skeleton lines={8} />}

      {signedIn && !loading && metrics && (
        <>
          <section className="admin-metrics">
            <article className="panel">
              <p className="panel__eyebrow">Applications</p>
              <strong className="mono">{metrics.applications}</strong>
            </article>
            <article className="panel">
              <p className="panel__eyebrow">Offers</p>
              <strong className="mono">{metrics.offers}</strong>
            </article>
            <article className="panel">
              <p className="panel__eyebrow">Lender success</p>
              <strong className="mono">{percent(metrics.lenderSuccessRate)}</strong>
            </article>
            <article className="panel">
              <p className="panel__eyebrow">Users</p>
              <strong className="mono">{metrics.users}</strong>
            </article>
          </section>

          {mlMetrics && (
            <section className="panel">
              <h2>Model evaluation</h2>
              <p className="panel__lede">
                Active: <span className="mono">{mlMetrics.activeModel || "—"}</span>
                {mlMetrics.sourceDataset && (
                  <> · <span className="mono">{mlMetrics.sourceDataset}</span></>
                )}
              </p>
              <div className="admin-metrics">
                {Object.entries(mlMetrics.models || {}).map(([name, stats]) => (
                  <article className="panel" key={name}>
                    <p className="panel__eyebrow">{name}</p>
                    <ul className="admin-list admin-list--compact">
                      <li><span>ROC-AUC</span><span className="mono">{stats.rocAuc}</span></li>
                      {stats.gini != null && <li><span>Gini</span><span className="mono">{stats.gini}</span></li>}
                      {stats.ks != null && <li><span>KS</span><span className="mono">{stats.ks}</span></li>}
                      <li><span>Precision</span><span className="mono">{percent(stats.precision)}</span></li>
                      <li><span>Recall</span><span className="mono">{percent(stats.recall)}</span></li>
                      <li><span>F1</span><span className="mono">{percent(stats.f1)}</span></li>
                      {stats.accuracy != null && <li><span>Accuracy</span><span className="mono">{percent(stats.accuracy)}</span></li>}
                    </ul>
                  </article>
                ))}
              </div>
            </section>
          )}

          <section className="panel">
            <h2>Failed lender calls</h2>
            {metrics.failedLenderCalls?.length ? (
              <ul className="admin-list">
                {metrics.failedLenderCalls.map((item, index) => (
                  <li key={`${item.lenderCode}-${item.latencyMs}-${index}`}>
                    <span className="mono">{item.lenderCode}</span>
                    <span>{item.message}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="panel__lede">No failed lender calls recorded.</p>
            )}
          </section>

          <section className="panel">
            <h2>Circuit breakers</h2>
            <ul className="admin-list">
              {(metrics.circuitBreakers || []).map((breaker) => (
                <li key={breaker.lenderCode}>
                  <span className="mono">{breaker.lenderCode}</span>
                  <span>{breaker.state}</span>
                  <span className="mono">{breaker.failures} failures</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="panel">
            <h2>Lender partners</h2>
            {adminLenders.length ? (
              <ul className="admin-list">
                {adminLenders.map((lender) => (
                  <li key={lender.id}>
                    <span>{lender.name}</span>
                    <span className="mono">{lender.code}</span>
                    <button type="button" className="btn btn--secondary" onClick={() => handleToggleLender(lender)}>
                      {lender.active ? "Disable" : "Enable"}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="panel__lede">No lenders found.</p>
            )}
          </section>

          <section className="panel">
            <h2>Recent audit events</h2>
            <ul className="admin-list">
              {events.map((event) => (
                <li key={event.id}>
                  <span className="mono">{event.eventType}</span>
                  <span>App {event.applicationId}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="panel">
            <h2>Applications ({applications.length})</h2>
            {applications.length ? (
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Applicant</th>
                      <th>Amount</th>
                      <th>Decision</th>
                      <th>Default risk</th>
                      <th>Drift</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {applications.slice(0, 25).map((app) => (
                      <tr key={app.id}>
                        <td className="mono">{app.id}</td>
                        <td>{app.applicant?.name}</td>
                        <td className="mono">{money(app.amount)}</td>
                        <td>{app.decision?.decision || app.risk?.decision?.decision || "—"}</td>
                        <td className="mono">
                          {app.risk?.defaultProbability != null
                            ? `${Math.round(app.risk.defaultProbability * 100)}%`
                            : "—"}
                        </td>
                        <td>
                          {app.risk?.drift?.driftAlert ? (
                            <span className="badge badge--danger">Alert</span>
                          ) : (
                            <span className="badge badge--ok">OK</span>
                          )}
                        </td>
                        <td>{app.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="panel__lede">No applications evaluated yet.</p>
            )}
          </section>
        </>
      )}
    </section>
  );
}
