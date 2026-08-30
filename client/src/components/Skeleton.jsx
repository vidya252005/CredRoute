export default function Skeleton({ lines = 3 }) {
  return (
    <div className="skeleton" aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <span key={index} className="skeleton__line" style={{ width: `${88 - index * 12}%` }} />
      ))}
    </div>
  );
}
