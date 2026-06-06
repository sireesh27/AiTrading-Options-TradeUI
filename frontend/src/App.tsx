import { useEffect, useState } from 'react';
import './index.css';
import { Header } from './components/Header';
import { SummaryCards } from './components/SummaryCards';
import { BrokerSection } from './components/BrokerSection';
import { PortfolioGreeks } from './components/PortfolioGreeks';
import { fetchPositions } from './api';
import type { DashboardData } from './types';

function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [greeksRefreshTrigger, setGreeksRefreshTrigger] = useState(0);
  const [marketDataSymbol, setMarketDataSymbol] = useState<string | undefined>(undefined);
  const [marketDataNonce, setMarketDataNonce] = useState(0);

  const showMarketData = (symbol: string) => {
    setMarketDataSymbol(symbol);
    setMarketDataNonce(n => n + 1);
    // Scroll the Portfolio Greeks / Market Data section into view
    requestAnimationFrame(() => {
      document.getElementById('portfolio-greeks-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchPositions();
      setData(result);
      setGreeksRefreshTrigger(prev => prev + 1);
    } catch (err: any) {
      console.error(err);
      setError('Failed to fetch data. Ensure backend is running.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Calculate totals across all brokers
  const totalValue = data ?
    (data.tastytrade.totalValue + data.alpaca_live.totalValue + data.ibkr_live.totalValue) : 0;

  // Note: Paper trading accounts typically excluded from main "Total" summary, or should be optional.
  // Based on HTML mockup, it seems to sum up shown values. 
  // Let's sum everything for now or just live? Mockup showed $1M, likely including paper?
  // Let's just sum all for now as per mockup logic usually.

  const totalDayPL = data ?
    (data.tastytrade.dayPL + data.alpaca_live.dayPL + data.ibkr_live.dayPL) : 0;


  return (
    <div className="relative min-h-screen w-full bg-background-light dark:bg-background-dark group/design-root text-[#111418] dark:text-white font-display">
      <div className="flex flex-col">
        <Header />

        <main className="flex-1 flex flex-col overflow-y-auto">
          <div className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-background-dark px-4 sm:px-6 md:px-10 py-4">
            <h1 className="text-xl sm:text-2xl lg:text-3xl font-black leading-tight tracking-[-0.033em]">Broker Accounts Overview</h1>
          </div>

          <div className="p-4 sm:p-6 md:p-8 lg:p-10">
            <div className="flex flex-col sm:flex-row flex-wrap items-start sm:items-center justify-between gap-4 mb-8">
              <div className="flex flex-col gap-2">
                <p className="text-gray-500 dark:text-gray-400 text-sm font-normal leading-normal">Last updated: {new Date().toLocaleTimeString()}</p>
              </div>
              <button
                className="w-full sm:w-auto flex items-center gap-2 min-w-[84px] max-w-[480px] cursor-pointer justify-center overflow-hidden rounded-lg h-10 px-4 bg-primary text-white text-sm font-bold leading-normal tracking-[0.015em] hover:bg-blue-600 transition-colors"
                onClick={loadData}
                disabled={loading}
              >
                <span className="material-symbols-outlined text-base">refresh</span>
                <span className="truncate">{loading ? 'Refreshing...' : 'Refresh'}</span>
              </button>
            </div>

            {error && (
              <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg">
                {error}
              </div>
            )}

            {data && (
              <>
                <SummaryCards totalValue={totalValue} totalDayPL={totalDayPL} />

                <div className="mb-8" id="portfolio-greeks-section">
                  <PortfolioGreeks
                    refreshTrigger={greeksRefreshTrigger}
                    marketDataSymbol={marketDataSymbol}
                    marketDataNonce={marketDataNonce}
                  />
                </div>

                <div className="flex flex-col gap-8">
                  <BrokerSection title="IBKR" id="ibkr" data={data.ibkr_live} onShowDetails={showMarketData} />
                  <BrokerSection title="IBKR Paper Trading" id="ibkr_paper" data={data.ibkr_paper} onShowDetails={showMarketData} />
                  <BrokerSection title="Tasty Trade" id="tastytrade" data={data.tastytrade} onShowDetails={showMarketData} />
                  <BrokerSection title="Alpaca" id="alpaca" data={data.alpaca_live} onShowDetails={showMarketData} />
                  <BrokerSection title="Alpaca Paper Trading" id="alpaca_paper" data={data.alpaca_paper} onShowDetails={showMarketData} />
                </div>
              </>
            )}
            {!data && !loading && !error && (
              <div className="text-center py-10">No data available.</div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
