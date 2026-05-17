import { test, expect } from '@playwright/test';

test('Shows error when fetching Greeks fails', async ({ page }) => {
    // Mock positions to ensure we have something to show in the UI
    await page.route('**/api/positions', async route => {
        const json = {
            tastytrade: {
                totalValue: 1000, equity: 1000, buyingPower: 500, dayPL: 10, dayTrades: "0/3",
                positions: [{
                    symbol: "O:SPY251219C00650000", qty: 1, avgPrice: 5.0, currentPrice: 6.0, value: 600, pl: 100, plPercent: 20, source: "Tastytrade"
                }]
            },
            alpaca_live: { totalValue: 0, equity: 0, buyingPower: 0, dayPL: 0, dayTrades: "0/3", positions: [] },
            alpaca_paper: { totalValue: 0, equity: 0, buyingPower: 0, dayPL: 0, dayTrades: "0/3", positions: [] },
            ibkr_live: { totalValue: 0, equity: 0, buyingPower: 0, dayPL: 0, dayTrades: "N/A", positions: [] },
            ibkr_paper: { totalValue: 0, equity: 0, buyingPower: 0, dayPL: 0, dayTrades: "N/A", positions: [] }
        };
        await route.fulfill({ json });
    });

    // Mock Greeks failure
    await page.route('**/api/greeks-batch', async route => {
        // Simulate a server error
        await route.fulfill({ status: 500, body: 'Internal Server Error' });
    });

    // Navigate to app
    // Note: This expects the app to be running on localhost:5173
    await page.goto('http://localhost:5173');

    // Wait for positions to load and "Tasty Trade" section to appear
    await expect(page.getByText('Tasty Trade')).toBeVisible();

    // Find the broker section for Tasty Trade (assuming it's the first one or finding by text context)
    // We can look for the tab specifically within a section that contains "Tasty Trade"
    // Or just click the first "MarketGreeks" tab if there's only one with data.
    // The app renders all brokers. Only Tastytrade has positions in our mock.

    // Click MarketGreeks tab
    // Use a locator that is specific enough. 
    // All brokers show the tabs. But only TastyTrade has positions.
    // The other brokers have 0 positions, so "MarketGreeks" might show "No open positions".
    // We want to verify the one that actually tries to fetch.

    // Let's filter by the broker section that has text "Tasty Trade"
    const brokerSection = page.locator('.bg-white', { hasText: 'Tasty Trade' }).first();
    await brokerSection.getByText('MarketGreeks').click();

    // Expect error message
    await expect(brokerSection.getByText('Failed to load Greeks.')).toBeVisible();
});
