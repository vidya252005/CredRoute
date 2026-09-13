export default function ErrorBanner({ message, onDismiss }) {
  if (!message) return null;

  return (
    <div className="error-banner" role="alert">
      <div>
        <p className="error-banner__title">This request failed</p>
        <p className="error-banner__body">{message}</p>
      </div>
      {onDismiss && (
        <button type="button" className="error-banner__dismiss" onClick={onDismiss} aria-label="Dismiss error">
          Dismiss
        </button>
      )}
    </div>
  );
}
