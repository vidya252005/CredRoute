const TOKEN_KEY = "credroute_token";
let pendingIdempotencyKey = null;

export function resetIdempotencyKey() {
  pendingIdempotencyKey = null;
}

function getIdempotencyKey() {
  if (!pendingIdempotencyKey) {
    pendingIdempotencyKey = crypto.randomUUID();
  }
  return pendingIdempotencyKey;
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export async function request(url, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (options.auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error("Server returned an unreadable response.");
  }

  if (!response.ok) {
    const message =
      payload?.error?.message ||
      (typeof payload?.error === "string" ? payload.error : null) ||
      (typeof payload?.detail === "string" ? payload.detail : null) ||
      payload?.detail?.[0]?.msg ||
      "Request failed.";
    throw new Error(message);
  }

  return payload;
}

export async function login(email, password) {
  const payload = await request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(payload.access_token);
  return payload;
}

export async function evaluateApplication(payload) {
  const response = await request("/api/applications/evaluate", {
    method: "POST",
    headers: { "Idempotency-Key": getIdempotencyKey() },
    body: JSON.stringify(payload),
  });
  resetIdempotencyKey();
  return response;
}

export async function routeApplication(applicationId) {
  return request(`/api/applications/${applicationId}/route`, { method: "POST" });
}

export async function repayApplication(applicationId) {
  return request(`/api/applications/${applicationId}/repay`, { method: "POST" });
}

export async function fetchOverview() {
  const [applications, lenders, metrics] = await Promise.all([
    request("/api/applications"),
    request("/api/lenders"),
    request("/api/metrics"),
  ]);
  return { applications, lenders, metrics };
}

export async function fetchAdminMetrics() {
  return request("/api/admin/metrics", { auth: true });
}

export async function fetchAdminApplications() {
  return request("/api/admin/applications", { auth: true });
}

export async function fetchAdminEvents() {
  return request("/api/admin/events", { auth: true });
}

export async function fetchAdminLenders() {
  return request("/api/admin/lenders", { auth: true });
}

export async function fetchAdminMlMetrics() {
  return request("/api/admin/ml/metrics", { auth: true });
}

export async function predictRisk(payload) {
  return request("/api/risk/predict", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function toggleLender(lenderId, active) {
  return request(`/api/admin/lenders/${lenderId}`, {
    method: "PATCH",
    auth: true,
    body: JSON.stringify({ active }),
  });
}
