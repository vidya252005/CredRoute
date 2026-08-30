import { useEffect, useRef, useState } from "react";
import AdminView from "./components/AdminView.jsx";
import ApplicationForm, { numericFields } from "./components/ApplicationForm.jsx";
import ApplicationsView from "./components/ApplicationsView.jsx";
import ErrorBanner from "./components/ErrorBanner.jsx";
import LandingPage from "./components/LandingPage.jsx";
import LendersView from "./components/LendersView.jsx";
import ResultPanel from "./components/ResultPanel.jsx";
import Skeleton from "./components/Skeleton.jsx";
import SiteHeader, { MetricsFooter, WorkspaceIntro } from "./components/SiteHeader.jsx";
import StatusStepper from "./components/StatusStepper.jsx";
import { evaluateApplication, fetchOverview, repayApplication, resetIdempotencyKey, routeApplication } from "./lib/api.js";
import { initialForm, presets } from "./lib/presets.js";
import { buildPayload, validateForm } from "./lib/validation.js";

function App() {
  const workspaceRef = useRef(null);
  const [view, setView] = useState("home");
  const [form, setForm] = useState(initialForm);
  const [fieldErrors, setFieldErrors] = useState({});
  const [result, setResult] = useState(null);
  const [corridorPhase, setCorridorPhase] = useState("idle");
  const [applications, setApplications] = useState([]);
  const [lenders, setLenders] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [selectedApplicationId, setSelectedApplicationId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [bootLoading, setBootLoading] = useState(true);
  const [error, setError] = useState("");

  const loadOverview = async () => {
    const data = await fetchOverview();
    setApplications(data.applications);
    setLenders(data.lenders);
    setMetrics(data.metrics);
    setSelectedApplicationId((current) => {
      if (current && data.applications.some((item) => item.id === current)) return current;
      return data.applications[0]?.id ?? null;
    });
  };

  useEffect(() => {
    loadOverview()
      .catch((loadError) => setError(loadError.message))
      .finally(() => setBootLoading(false));
  }, []);

  useEffect(() => {
    if (view === "workspace") {
      workspaceRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [view]);

  useEffect(() => {
    if (view === "applications" || view === "lenders" || view === "workspace") {
      loadOverview().catch((loadError) => setError(loadError.message));
    }
  }, [view]);

  const navigate = (nextView) => {
    setView(nextView);
    setError("");
  };

  const updateField = (event) => {
    const { name, type, checked, value } = event.target;
    setForm((current) => ({
      ...current,
      [name]:
        type === "checkbox"
          ? checked
          : name === "pan"
            ? String(value).toUpperCase()
            : numericFields.includes(name)
              ? value === ""
                ? ""
                : Number(value)
              : value,
    }));
    setFieldErrors((current) => {
      if (!current[name]) return current;
      const next = { ...current };
      delete next[name];
      return next;
    });
  };

  const applyPreset = (presetKey) => {
    resetIdempotencyKey();
    setForm(presets[presetKey]);
    setResult(null);
    setCorridorPhase("idle");
    setFieldErrors({});
    setError("");
  };

  const submitApplication = async (event) => {
    event.preventDefault();
    const errors = validateForm(form);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      setError("Fix the highlighted fields before submitting.");
      return;
    }

    setLoading(true);
    setBusy("evaluating");
    setResult(null);
    setError("");
    setCorridorPhase("evaluating");

    try {
      const evaluation = await evaluateApplication(buildPayload(form));
      setResult(evaluation);
      setCorridorPhase(evaluation.status === "routed" ? "routed" : "complete");
      await loadOverview();
    } catch (submitError) {
      setCorridorPhase("idle");
      setError(submitError.message);
    } finally {
      setLoading(false);
      setBusy("");
    }
  };

  const handleRoute = async () => {
    if (!result?.id) return;
    setLoading(true);
    setBusy("routing");
    setError("");
    try {
      const routed = await routeApplication(result.id);
      setResult(routed.application);
      setCorridorPhase("routed");
      await loadOverview();
    } catch (routeError) {
      setError(routeError.message);
    } finally {
      setLoading(false);
      setBusy("");
    }
  };

  const handleRepay = async () => {
    if (!result?.id) return;
    setLoading(true);
    setBusy("repaying");
    setError("");
    try {
      const repaid = await repayApplication(result.id);
      setResult(repaid.application);
      await loadOverview();
    } catch (repayError) {
      setError(repayError.message);
    } finally {
      setLoading(false);
      setBusy("");
    }
  };

  const segmentLabel = result?.eligibility?.profile?.label;
  const routedLender = result?.routedLenderCode || result?.offers?.find((o) => o.rank === 1)?.lenderCode;

  if (view === "home") {
    if (bootLoading) {
      return (
        <div className="landing landing--loading">
          <Skeleton lines={5} />
        </div>
      );
    }
    return (
      <>
        <ErrorBanner message={error} onDismiss={() => setError("")} />
        <LandingPage onNavigate={navigate} lenders={lenders} metrics={metrics} />
      </>
    );
  }

  return (
    <div className="app-shell">
      <SiteHeader view={view} onNavigate={navigate} />
      <ErrorBanner message={error} onDismiss={() => setError("")} />

      {view === "workspace" && (
        <>
          <WorkspaceIntro />
          <StatusStepper phase={corridorPhase} segment={segmentLabel} routedLender={routedLender} />
          <section className="workspace" ref={workspaceRef} id="workspace">
            <ApplicationForm
              form={form}
              fieldErrors={fieldErrors}
              loading={loading}
              busy={busy}
              onChange={updateField}
              onSubmit={submitApplication}
              onPreset={applyPreset}
            />
            {loading && !result ? (
              <section className="panel panel--result">
                <Skeleton lines={6} />
              </section>
            ) : (
              <ResultPanel result={result} loading={loading} busy={busy} onRoute={handleRoute} onRepay={handleRepay} />
            )}
          </section>
        </>
      )}

      {view === "applications" && (
        bootLoading ? (
          <Skeleton lines={8} />
        ) : (
          <ApplicationsView
            applications={applications}
            selectedId={selectedApplicationId}
            onSelect={setSelectedApplicationId}
          />
        )
      )}

      {view === "lenders" && (bootLoading ? <Skeleton lines={6} /> : <LendersView lenders={lenders} />)}

      {view === "admin" && (
        <AdminView onRefreshLenders={loadOverview} />
      )}

      <MetricsFooter metrics={metrics} />

      <p className="demo-disclaimer">
        CredRoute is a portfolio demo. Mock lenders only. Synthetic data. No real credit decisions.
      </p>
    </div>
  );
}

export default App;
