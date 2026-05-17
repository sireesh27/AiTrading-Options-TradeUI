import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrokerSection } from '../components/BrokerSection';
import * as api from '../api';

// Mock the API module
vi.mock('../api');

const mockPositions = [
    {
        symbol: "O:SPY251219C00650000",
        qty: 1,
        avgPrice: 5.0,
        currentPrice: 6.0,
        value: 600,
        pl: 100,
        plPercent: 20,
        source: "Tastytrade"
    }
];

const mockBrokerData = {
    totalValue: 10000,
    equity: 10000,
    buyingPower: 5000,
    dayPL: 100,
    dayTrades: "0/3",
    positions: mockPositions,
    isConnected: true
};

const mockGreeksData = {
    "O:SPY251219C00650000": {
        delta: 0.5,
        gamma: 0.05,
        theta: -0.1,
        vega: 0.2,
        rho: 0.01,
        iv: 0.15
    }
};

describe('MarketGreeks Feature', () => {
    it('fetches and displays Greeks when tab is clicked', async () => {
        // @ts-ignore
        api.fetchGreeksBatch.mockResolvedValue(mockGreeksData);

        render(<BrokerSection title="Test Broker" id="test-broker" data={mockBrokerData} />);

        // 1. Initial state: Positions table should be visible
        expect(screen.getByText('Open Positions')).toBeInTheDocument();
        expect(screen.getByText('O:SPY251219C00650000')).toBeInTheDocument();

        // 2. Click "MarketGreeks" tab
        const greeksTab = screen.getByText('MarketGreeks');
        fireEvent.click(greeksTab);

        // 3. Verify loading state
        await waitFor(() => {
            // @ts-ignore
            expect(api.fetchGreeksBatch).toHaveBeenCalledWith(["O:SPY251219C00650000"]);
        });

        // 4. Verify Greeks are displayed
        await waitFor(() => {
            expect(screen.getByText('0.5000')).toBeInTheDocument(); // Delta
            expect(screen.getByText('0.0500')).toBeInTheDocument(); // Gamma
            expect(screen.getByText('15.00%')).toBeInTheDocument(); // IV
        });
    });

    it('displays error/retry when fetch fails', async () => {
        // @ts-ignore
        api.fetchGreeksBatch.mockRejectedValue(new Error('Network Error'));

        render(<BrokerSection title="Test Broker" id="test-broker" data={mockBrokerData} />);

        const greeksTab = screen.getByText('MarketGreeks');
        fireEvent.click(greeksTab);

        await waitFor(() => {
            expect(screen.getByText('Failed to load Greeks.')).toBeInTheDocument();
        });

        // Verify retry button exists
        const retryBtn = screen.getByText('Retry Loading');
        expect(retryBtn).toBeInTheDocument();

        // Click retry
        // @ts-ignore
        api.fetchGreeksBatch.mockResolvedValue(mockGreeksData);
        fireEvent.click(retryBtn);

        await waitFor(() => {
            expect(screen.getByText('0.5000')).toBeInTheDocument();
        });
    });

    it('shows message when no positions exist', async () => {
        const emptyData = { ...mockBrokerData, positions: [] };
        render(<BrokerSection title="Test Broker" id="test-broker" data={emptyData} />);

        const greeksTab = screen.getByText('MarketGreeks');
        fireEvent.click(greeksTab);

        expect(screen.getByText('No open positions to display Greeks for.')).toBeInTheDocument();
    });
});
