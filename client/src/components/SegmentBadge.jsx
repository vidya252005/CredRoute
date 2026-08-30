export default function SegmentBadge({ segment }) {
  if (!segment) return <span className="badge badge--muted">Unclassified</span>;

  const label =
    segment === "prime"
      ? "Prime"
      : segment === "near_prime"
        ? "Near-prime"
        : segment === "thin_file"
          ? "Thin-file"
          : segment;

  return <span className={`badge badge--${segment}`}>{label}</span>;
}
