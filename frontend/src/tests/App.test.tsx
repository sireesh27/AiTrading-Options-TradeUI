import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import App from '../App';
import * as api from '../api';


// Mock the API module
vi.mock('../api');

const mockData = {
    tastytrade: { totalValue: 1000, equity: 1000, buyingPower: 500, dayPL: 10, dayTrades: "0/3", positions: [] },
    alpaca_live: { totalValue: 2000, equity: 2000, buyingPower: 1000, dayPL: 20, dayTrades: "0/3", positions: [] },
    alpaca_paper: { totalValue: 0, equity: 0, buyingPower: 0, dayPL: 0, dayTrades: "0/3", positions: [] },
    ibkr_live: { totalValue: 3000, equity: 3000, buyingPower: 1500, dayPL: 30, dayTrades: "N/A", positions: [] },
    ibkr_paper: { totalValue: 0, equity: 0, buyingPower: 0, dayPL: 0, dayTrades: "N/A", positions: [] }
};

describe('App', () => {
    it('renders loading state initially', () => {
        // @ts-ignore
        api.fetchPositions.mockReturnValue(new Promise(() => { }));
        render(<App />);
        expect(screen.getByText(/refreshing/i)).toBeInTheDocument();
    });

    it('renders dashboard with data', async () => {
        // @ts-ignore
        api.fetchPositions.mockResolvedValue(mockData);
        render(<App />);

        await waitFor(() => {
            expect(screen.getByText('Tasty Trade')).toBeInTheDocument();
            expect(screen.getByText('$6,000.00')).toBeInTheDocument(); // Total value sum
        });
    });

    it('renders error message on fetch failure', async () => {
        // @ts-ignore
        api.fetchPositions.mockRejectedValue(new Error('Network error'));
        render(<App />);

        await waitFor(() => {
            expect(screen.getByText(/Failed to fetch data/i)).toBeInTheDocument();
        });
    });
});
