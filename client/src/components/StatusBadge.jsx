const statusMap = {
  offers_ready: { label: "Offers ready", tone: "ready" },
  under_review: { label: "Under review", tone: "review" },
  rejected: { label: "Rejected", tone: "declined" },
  ineligible: { label: "Ineligible", tone: "declined" },
  routed: { label: "Routed", tone: "routed" },
};

export default function StatusBadge({ status }) {
  const config = statusMap[status] || { label: status, tone: "muted" };
  return <span className={`status status--${config.tone}`}>{config.label}</span>;
}
