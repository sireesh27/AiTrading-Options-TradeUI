import type { DashboardData } from './types';

const API_BASE_URL = 'http://localhost:8000';

export async function fetchPositions(): Promise<DashboardData> {
    const response = await fetch(`${API_BASE_URL}/api/positions`);
    if (!response.ok) {
        throw new Error(`Error fetching positions: ${response.statusText}`);
    }
    return response.json();
}

export async function fetchGreeksBatch(symbols: string[]): Promise<Record<string, any>> {
    const response = await fetch(`${API_BASE_URL}/api/greeks-batch`, {
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
    const response = await fetch(`${API_BASE_URL}/api/ibkr/reauth`, {
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
