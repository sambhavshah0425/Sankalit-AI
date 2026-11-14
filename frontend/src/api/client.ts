const API_BASE = '';

const TOKEN_KEY = 'skl_access_token';
const REFRESH_KEY = 'skl_refresh_token';

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setStoredTokens(accessToken: string, refreshToken?: string): void {
  localStorage.setItem(TOKEN_KEY, accessToken);
  if (refreshToken) {
    localStorage.setItem(REFRESH_KEY, refreshToken);
  }
}

export function clearStoredTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

let isRefreshing = false;
let refreshSubscribers: Array<(token: string) => void> = [];

function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(options.headers || {});

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Set default JSON Content-Type if not sending FormData
  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle Token Expiry (401)
  if (response.status === 401 && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/refresh')) {
    const refreshToken = getStoredRefreshToken();
    if (!refreshToken) {
      clearStoredTokens();
      throw new Error('Authentication required. Please log in.');
    }

    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (!refreshRes.ok) {
          clearStoredTokens();
          throw new Error('Session expired. Please log in again.');
        }

        const data = await refreshRes.json();
        setStoredTokens(data.access_token, data.refresh_token);
        isRefreshing = false;
        onRefreshed(data.access_token);

        // Retry original request with fresh token
        headers.set('Authorization', `Bearer ${data.access_token}`);
        const retryRes = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
        if (!retryRes.ok) {
          const err = await retryRes.json().catch(() => ({ detail: 'Request failed' }));
          throw new Error(err.detail || `HTTP Error ${retryRes.status}`);
        }
        return retryRes.json();
      } catch (err) {
        isRefreshing = false;
        clearStoredTokens();
        throw err;
      }
    } else {
      // Wait for ongoing refresh
      return new Promise<T>((resolve, reject) => {
        refreshSubscribers.push(async (newToken) => {
          headers.set('Authorization', `Bearer ${newToken}`);
          try {
            const retryRes = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
            if (!retryRes.ok) {
              const err = await retryRes.json().catch(() => ({ detail: 'Request failed' }));
              reject(new Error(err.detail || `HTTP Error ${retryRes.status}`));
            } else {
              resolve(retryRes.json());
            }
          } catch (e) {
            reject(e);
          }
        });
      });
    }
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorBody.detail || `HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

