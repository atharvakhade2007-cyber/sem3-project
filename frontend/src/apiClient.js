// apiClient.js
// Thin authenticated fetch wrapper for the Django backend.
//
// - Access tokens are kept in memory only (never localStorage) and injected as
//   `Authorization: Bearer <token>` on every request.
// - On a 401, the wrapper silently calls POST /api/auth/refresh/ (which reads
//   the httpOnly refresh cookie), stores the new access token, and retries the
//   original request exactly once.
// - Refreshes are deduplicated so concurrent 401s trigger a single refresh.

let accessToken = null;
let refreshInFlight = null;

export function setAccessToken(token) {
  accessToken = token || null;
}

export function getAccessToken() {
  return accessToken;
}

export function isAuthenticated() {
  return !!accessToken;
}

/** Refresh the access token via the httpOnly cookie. Throws if expired. */
export async function refreshAccessToken() {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    const res = await fetch('/api/auth/refresh/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    if (!res.ok) {
      setAccessToken(null);
      throw new Error('Your session has expired. Please sign in again.');
    }
    const data = await res.json();
    setAccessToken(data.access);
    return data.access;
  })().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

/** fetch() with Bearer injection + single 401 auto-refresh retry. */
export async function apiFetch(endpoint, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  const opts = {
    ...options,
    headers,
    credentials: 'same-origin',
  };

  let res = await fetch(endpoint, opts);

  if (res.status === 401 && accessToken) {
    try {
      await refreshAccessToken();
      headers['Authorization'] = `Bearer ${accessToken}`;
      res = await fetch(endpoint, { ...opts, headers });
    } catch {
      // Refresh failed — session is gone; leave res as the original 401.
    }
  }

  return res;
}

/**
 * fetch() + JSON parse + error normalization.
 * Throws an Error whose `.data` carries the parsed body (DRF field errors
 * are `{ field: [messages] }`) so forms can render inline errors.
 */
export async function apiJson(endpoint, options = {}) {
  const opts = { ...options };
  if (
    opts.body &&
    !(opts.body instanceof FormData) &&
    !opts.headers?.['Content-Type']
  ) {
    opts.headers = { ...(opts.headers || {}), 'Content-Type': 'application/json' };
  }

  const res = await apiFetch(endpoint, opts);

  const contentType = res.headers.get('content-type') || '';
  const data = contentType.includes('application/json')
    ? await res.json().catch(() => null)
    : null;

  if (!res.ok) {
    const err = new Error(extractErrorMessage(data, res.status));
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function extractErrorMessage(data, status) {
  if (data && typeof data === 'object') {
    if (typeof data.error === 'string') return data.error;
    if (typeof data.detail === 'string') return data.detail;
    // DRF field errors: { "username": ["already taken"], ... }
    const first = Object.values(data).find(v => Array.isArray(v) && v.length > 0);
    if (Array.isArray(first) && typeof first[0] === 'string') return first[0];
  }
  return `Request failed (${status})`;
}