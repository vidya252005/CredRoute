const states = new Map();

const defaultState = () => ({
  failures: 0,
  successes: 0,
  openUntil: 0,
  state: "closed",
});

export const getCircuitState = (lenderCode) => states.get(lenderCode) || defaultState();

export const recordSuccess = (lenderCode) => {
  const current = { ...getCircuitState(lenderCode) };
  current.successes += 1;
  current.failures = 0;
  current.state = "closed";
  current.openUntil = 0;
  states.set(lenderCode, current);
};

export const recordFailure = (lenderCode, { failureThreshold = 3, cooldownMs = 30000 } = {}) => {
  const current = { ...getCircuitState(lenderCode) };
  current.failures += 1;
  current.successes = 0;

  if (current.failures >= failureThreshold) {
    current.state = "open";
    current.openUntil = Date.now() + cooldownMs;
  }

  states.set(lenderCode, current);
  return current;
};

export const isCircuitOpen = (lenderCode) => {
  const current = getCircuitState(lenderCode);
  if (current.state !== "open") return false;

  if (Date.now() >= current.openUntil) {
    states.set(lenderCode, { ...current, state: "half_open" });
    return false;
  }

  return true;
};

export const getCircuitSnapshot = () =>
  [...states.entries()].map(([lenderCode, value]) => ({
    lenderCode,
    ...value,
  }));
