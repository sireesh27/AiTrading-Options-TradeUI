import type { DashboardData } from './types';

export const API_BASE_URL = 'http://localhost:8000';
export const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');

// Shared secret the backend requires on every /api and /ws route (BACKEND_API_KEY).
// Set VITE_API_KEY in frontend/.env.local. Note: anything bundled into the
// frontend is visible to whoever can load the page -- this keeps strangers off
// the backend, it is not a secret from the dashboard's own users.
const API_KEY: string = (import.meta as any).env?.VITE_API_KEY ?? '';

/** apiFetch() with the X-API-Key header attached. Use for every backend call. */
export function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers ?? {});
    if (API_KEY) headers.set('X-API-Key', API_KEY);
    return fetch(input, { ...init, headers });
}

/** Full WebSocket URL for a backend path, with the key as a query param
 *  (browsers can't set custom headers on WebSocket handshakes). */
export function wsUrl(path: string): string {
    const sep = path.includes('?') ? '&' : '?';
    return `${WS_BASE_URL}${path}` + (API_KEY ? `${sep}api_key=${encodeURIComponent(API_KEY)}` : '');
}

export async function fetchPositions(): Promise<DashboardData> {
    const response = await apiFetch(`${API_BASE_URL}/api/positions`);
    if (!response.ok) {
        throw new Error(`Error fetching positions: ${response.statusText}`);
    }
    return response.json();
}

export async function fetchGreeksBatch(symbols: string[]): Promise<Record<string, any>> {
    const response = await apiFetch(`${API_BASE_URL}/api/greeks-batch`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ symbols }),
    });
    if (!response.ok) {
        throw new Error(`Error fetching greeks: ${response.statusText}`);
    }
    return response.json();
}

export interface ReauthResult {
    ok: boolean;
    account: 'live' | 'paper';
    container: string;
    message: string;
}

/** Restart the IB Gateway container for an account so IBC runs a fresh login. */
export async function reauthIbkr(account: 'live' | 'paper'): Promise<ReauthResult> {
    const response = await apiFetch(`${API_BASE_URL}/api/ibkr/reauth`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account }),
    });
    if (!response.ok) {
        let detail = response.statusText;
        try { detail = (await response.json()).detail ?? detail; } catch { /* non-JSON error body */ }
        throw new Error(`Re-authentication failed: ${detail}`);
    }
    return response.json();
}
