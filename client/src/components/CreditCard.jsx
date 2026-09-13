export default function CreditCard({
  amount,
  name,
  meta,
  footer,
}) {
  return (
    <article className="credit-card" aria-label="Credit line card">
      <div className="credit-card__top">
        <span className="credit-card__chip" aria-hidden="true" />
        <span className="credit-card__brand">credroute</span>
      </div>
      <p className="credit-card__amount">{amount}</p>
      {meta ? <p className="credit-card__meta">{meta}</p> : null}
      <div className="credit-card__bottom">
        <span>{name || "Your name"}</span>
        {footer ? <span>{footer}</span> : null}
      </div>
    </article>
  );
}
