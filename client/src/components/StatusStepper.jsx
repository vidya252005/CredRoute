const STEPS = [
  { id: "intake", label: "Intake" },
  { id: "foir", label: "FOIR" },
  { id: "segment", label: "Segment" },
  { id: "lenders", label: "Lenders" },
  { id: "offer", label: "Offer" },
];

export default function StatusStepper({ phase = "idle", segment, routedLender }) {
  const activeIndex =
    phase === "evaluating" ? 2 : phase === "complete" || phase === "routed" ? 4 : 0;

  return (
    <section className="status-stepper" aria-label="Application processing status">
      <ol className="status-stepper__list">
        {STEPS.map((step, index) => (
          <li
            key={step.id}
            className={`status-stepper__item${index <= activeIndex ? " is-complete" : ""}${index === activeIndex && phase !== "idle" ? " is-current" : ""}`}
          >
            <span className="status-stepper__label">{step.label}</span>
          </li>
        ))}
      </ol>
      <p className="status-stepper__message">
        {phase === "idle" && "Waiting for application submission."}
        {phase === "evaluating" && "Evaluating eligibility, risk, and lender responses."}
        {phase === "complete" && segment && `Classified as ${segment}. Offers ranked.`}
        {phase === "routed" && routedLender && `Routed to ${routedLender}.`}
      </p>
    </section>
  );
}
