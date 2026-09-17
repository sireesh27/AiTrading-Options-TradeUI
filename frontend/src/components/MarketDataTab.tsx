import React, { useEffect, useRef, useState, useCallback } from 'react';
import { TradeTicket } from './TradeTicket';

import { API_BASE_URL, apiFetch, wsUrl } from '../api';
interface StockQuote {
    symbol: string;
    price: number;
    bid: number;
    ask: number;
    broker?: string;
}

interface OptionContract {
    symbol: string;
    strike: number;
    expiration: string;
    type: 'call' | 'put';
    bid: number;
    ask: number;
    last: number;
    volume: number;
    openInterest: number;
    delta: number;
    gamma: number;
    theta: number;
    vega: number;
    rho: number;
    iv: number;
}

interface OptionChainData {
    broker?: string;
    underlying: string;
    underlyingPrice: number;
    expirations: string[];
    chain: {
        [expiration: string]: {
            calls: OptionContract[];
            puts: OptionContract[];
        };
    };
}

type BrokerSource = 'tastytrade' | 'ibkr' | 'massive';


// Derive the underlying ticker from a position symbol. Handles OCC option
// symbols (e.g. "AAPL  260605C00310000" or "O:SPY251219C00450000") by taking
// the leading root letters; plain stock symbols pass through unchanged.
const underlyingFromSymbol = (raw: string): string => {
    const s = (raw || '').replace(/^O:/, '').trim();
    const m = s.match(/^([A-Za-z]+)\s*[0-9]{6}[CP][0-9]{8}$/);
    return (m ? m[1] : s.split(/\s/)[0]).toUpperCase();
};

interface MarketDataTabProps {
    symbol?: string;        // external trigger (e.g. from a position "Details" click)
    symbolNonce?: number;   // bump to re-trigger even if symbol is unchanged
}

export const MarketDataTab: React.FC<MarketDataTabProps> = ({ symbol: externalSymbol, symbolNonce }) => {
    const [ticker, setTicker] = useState('AAPL');
    const [searchInput, setSearchInput] = useState('AAPL');
    const [numStrikes, setNumStrikes] = useState(20);
    const [broker, setBroker] = useState<BrokerSource>('ibkr');
    const [stockQuote, setStockQuote] = useState<StockQuote | null>(null);
    const [optionChain, setOptionChain] = useState<OptionChainData | null>(null);
    const [selectedExpiration, setSelectedExpiration] = useState<string>('');
    const [loadingQuote, setLoadingQuote] = useState(false);
    const [loadingChain, setLoadingChain] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [chainView, setChainView] = useState<'all' | 'calls' | 'puts'>('all');
    const [isLive, setIsLive] = useState(false);
    const wsRef = useRef<WebSocket | null>(null);

    // Symbol autocomplete
    interface SymbolSuggestion { symbol: string; name: string; secType: string; currency: string; hasOptions: boolean; }
    const [suggestions, setSuggestions] = useState<SymbolSuggestion[]>([]);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [searchingSymbols, setSearchingSymbols] = useState(false);
    const suppressSearchRef = useRef(false);

    // Trade ticket (Robinhood-style buy/sell)
    const [ticket, setTicket] = useState<{
        secType: 'stock' | 'option';
        symbol: string;
        displayName: string;
        referencePrice?: number;
        side: 'BUY' | 'SELL';
    } | null>(null);

    const openStockTicket = (side: 'BUY' | 'SELL') => {
        if (!stockQuote) return;
        setTicket({
            secType: 'stock',
            symbol: stockQuote.symbol,
            displayName: stockQuote.symbol,
            referencePrice: stockQuote.price,
            side,
        });
    };

    const openOptionTicket = (opt: { symbol: string; strike: number; bid: number; ask: number },
        kind: 'call' | 'put', side: 'BUY' | 'SELL') => {
        if (!opt?.symbol) return;
        const ref = side === 'BUY' ? (opt.ask || opt.bid) : (opt.bid || opt.ask);
        setTicket({
            secType: 'option',
            symbol: opt.symbol,
            displayName: `${ticker} ${selectedExpiration} ${opt.strike} ${kind === 'call' ? 'Call' : 'Put'}`,
            referencePrice: ref,
            side,
        });
    };

    const getStockPriceEndpoint = useCallback((symbol: string, brokerSource: BrokerSource) => {
        switch (brokerSource) {
            case 'tastytrade':
                return `${API_BASE_URL}/api/tastytrade/stock-price/${symbol}`;
            case 'ibkr':
                return `${API_BASE_URL}/api/ibkr/stock-price/${symbol}`;
            case 'massive':
            default:
                return `${API_BASE_URL}/api/stock-price/${symbol}`;
        }
    }, []);

    const getOptionChainEndpoint = useCallback(
        (symbol: string, brokerSource: BrokerSource, expiration?: string, strikes?: number) => {
            const base =
                brokerSource === 'tastytrade'
                    ? `${API_BASE_URL}/api/tastytrade/option-chain/${symbol}`
                    : brokerSource === 'ibkr'
                        ? `${API_BASE_URL}/api/ibkr/option-chain/${symbol}`
                        : `${API_BASE_URL}/api/option-chain/${symbol}`;
            const params = new URLSearchParams();
            if (expiration) params.set('expiration', expiration);
            if (strikes) params.set('strikes', String(strikes));
            const qs = params.toString();
            return qs ? `${base}?${qs}` : base;
        }, []);

    const fetchStockQuote = useCallback(async (symbol: string, brokerSource: BrokerSource) => {
        setLoadingQuote(true);
        try {
            const endpoint = getStockPriceEndpoint(symbol, brokerSource);
            const response = await apiFetch(endpoint);
            if (!response.ok) {
                // Try to get error detail from response
                let errorDetail = `Failed to fetch quote for ${symbol} from ${brokerSource}`;
                try {
                    const errorData = await response.json();
                    if (errorData.detail) {
                        errorDetail = errorData.detail;
                    }
                } catch {
                    // Ignore JSON parse errors
                }
                throw new Error(errorDetail);
            }
            const data = await response.json();
            setStockQuote(data);
            setError(null);
        } catch (err: any) {
            console.error(err);
            setStockQuote(null);
            setError(err.message || `Could not fetch quote for ${symbol} from ${brokerSource}`);
        } finally {
            setLoadingQuote(false);
        }
    }, [getStockPriceEndpoint]);

    const fetchOptionChain = useCallback(async (
        symbol: string, brokerSource: BrokerSource, expiration?: string, strikes?: number,
    ) => {
        setLoadingChain(true);
        try {
            const endpoint = getOptionChainEndpoint(symbol, brokerSource, expiration, strikes ?? numStrikes);
            const response = await apiFetch(endpoint);
            if (!response.ok) {
                // Try to get error detail from response
                let errorDetail = `Failed to fetch option chain for ${symbol} from ${brokerSource}`;
                try {
                    const errorData = await response.json();
                    if (errorData.detail) {
                        errorDetail = errorData.detail;
                    }
                } catch {
                    // Ignore JSON parse errors
                }
                throw new Error(errorDetail);
            }
            const data = await response.json();
            const loadedExp = data.selectedExpiration || (data.expirations && data.expirations[0]);

            if (expiration) {
                // Loading a specific expiration on demand: merge its strikes into
                // the existing chain so previously-loaded expirations stay cached.
                setOptionChain(prev => {
                    if (!prev) return data;
                    return {
                        ...prev,
                        underlyingPrice: data.underlyingPrice ?? prev.underlyingPrice,
                        expirations: data.expirations?.length ? data.expirations : prev.expirations,
                        chain: { ...prev.chain, ...data.chain },
                    };
                });
            } else {
                setOptionChain(data);
            }
            if (loadedExp) {
                setSelectedExpiration(loadedExp);
            }
            setError(null);
        } catch (err: any) {
            console.error(err);
            setOptionChain(null);
            setError(err.message || `Could not fetch option chain for ${symbol} from ${brokerSource}`);
        } finally {
            setLoadingChain(false);
        }
    }, [getOptionChainEndpoint, numStrikes]);

    // Switching expiration: load that expiration's strikes on demand (IBKR only
    // returns one expiration's data per call), reusing already-loaded ones.
    const handleExpirationChange = (exp: string) => {
        setSelectedExpiration(exp);
        if (exp && !optionChain?.chain?.[exp]) {
            fetchOptionChain(ticker, broker, exp);
        }
    };

    // Changing the number of strikes: reload the current expiration deeper.
    const handleStrikesChange = (n: number) => {
        setNumStrikes(n);
        if (ticker) {
            fetchOptionChain(ticker, broker, selectedExpiration || undefined, n);
        }
    };

    const handleSearch = () => {
        const symbol = searchInput.trim().toUpperCase();
        if (symbol) {
            setShowSuggestions(false);
            setTicker(symbol);
            fetchStockQuote(symbol, broker);
            fetchOptionChain(symbol, broker);
        }
    };

    const selectSuggestion = (sym: string) => {
        suppressSearchRef.current = true;     // don't re-open dropdown from the set
        setSearchInput(sym);
        setShowSuggestions(false);
        setSuggestions([]);
        setTicker(sym);
        fetchStockQuote(sym, broker);
        fetchOptionChain(sym, broker);
    };

    // Debounced symbol autocomplete (IBKR reqMatchingSymbols)
    useEffect(() => {
        if (suppressSearchRef.current) { suppressSearchRef.current = false; return; }
        const q = searchInput.trim();
        if (q.length < 1) { setSuggestions([]); setShowSuggestions(false); return; }
        const handle = setTimeout(async () => {
            try {
                setSearchingSymbols(true);
                const r = await apiFetch(`${API_BASE_URL}/api/ibkr/search/${encodeURIComponent(q)}`);
                if (r.ok) {
                    const d = await r.json();
                    setSuggestions(d.results || []);
                    setShowSuggestions((d.results || []).length > 0);
                }
            } catch {
                /* ignore search errors */
            } finally {
                setSearchingSymbols(false);
            }
        }, 250);
        return () => clearTimeout(handle);
    }, [searchInput]);

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleSearch();
        }
    };

    const handleBrokerChange = (newBroker: BrokerSource) => {
        setBroker(newBroker);
        // Refetch data with new broker
        if (ticker) {
            fetchStockQuote(ticker, newBroker);
            fetchOptionChain(ticker, newBroker);
        }
    };

    // Load AAPL data on mount
    useEffect(() => {
        fetchStockQuote('AAPL', broker);
        fetchOptionChain('AAPL', broker);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // React to an external symbol (e.g. a position "Details" click). Resolves the
    // underlying ticker and loads its market data.
    useEffect(() => {
        if (!externalSymbol) return;
        const sym = underlyingFromSymbol(externalSymbol);
        if (!sym) return;
        setSearchInput(sym);
        setTicker(sym);
        fetchStockQuote(sym, broker);
        fetchOptionChain(sym, broker);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [externalSymbol, symbolNonce]);

    // Live streaming via WebSocket for IBKR. Opens a socket for the current
    // ticker and updates the quote card on every tick; cleans up on change.
    useEffect(() => {
        // Close any existing socket first
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
        setIsLive(false);

        if (broker !== 'ibkr' || !ticker) {
            return;
        }

        const ws = new WebSocket(wsUrl(`/ws/ibkr/stock-price/${ticker}`));
        wsRef.current = ws;

        ws.onopen = () => setIsLive(true);
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.error) {
                    setError(data.error);
                    setIsLive(false);
                    return;
                }
                setStockQuote(data);
                setError(null);
            } catch {
                // ignore malformed frames
            }
        };
        ws.onerror = () => setIsLive(false);
        ws.onclose = () => setIsLive(false);

        return () => {
            ws.close();
            wsRef.current = null;
            setIsLive(false);
        };
    }, [ticker, broker]);

    const formatPrice = (price: number | undefined | null) => {
        if (price === undefined || price === null) return '-';
        return `$${price.toFixed(2)}`;
    };

    const formatGreek = (value: number | undefined | null, decimals: number = 4) => {
        if (value === undefined || value === null) return '-';
        return value.toFixed(decimals);
    };

    const formatPercent = (value: number | undefined | null) => {
        if (value === undefined || value === null) return '-';
        return `${(value * 100).toFixed(1)}%`;
    };

    const currentChainData = optionChain?.chain?.[selectedExpiration];

    return (
        <div className="flex flex-col gap-6">
            {/* Ticker Search */}
            <div className="bg-white dark:bg-gray-900 rounded-xl p-6 border border-gray-200 dark:border-gray-800">
                <div className="flex flex-col gap-4">
                    {/* Broker Selector */}
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-500 dark:text-gray-400">Data Source:</span>
                        <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg">
                            <button
                                onClick={() => handleBrokerChange('ibkr')}
                                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${broker === 'ibkr'
                                    ? 'bg-white dark:bg-gray-700 text-red-600 dark:text-red-400 shadow-sm'
                                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                                    }`}
                            >
                                IBKR
                            </button>
                            <button
                                onClick={() => handleBrokerChange('tastytrade')}
                                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${broker === 'tastytrade'
                                    ? 'bg-white dark:bg-gray-700 text-orange-600 dark:text-orange-400 shadow-sm'
                                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                                    }`}
                            >
                                Tastytrade
                            </button>
                            <button
                                onClick={() => handleBrokerChange('massive')}
                                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${broker === 'massive'
                                    ? 'bg-white dark:bg-gray-700 text-purple-600 dark:text-purple-400 shadow-sm'
                                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                                    }`}
                            >
                                Massive API
                            </button>
                        </div>
                    </div>

                    {/* Search Input */}
                    <div className="flex items-center gap-4">
                        <div className="flex-1 max-w-md">
                            <div className="relative">
                                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                                    search
                                </span>
                                <input
                                    type="text"
                                    value={searchInput}
                                    onChange={(e) => setSearchInput(e.target.value.toUpperCase())}
                                    onKeyDown={handleKeyDown}
                                    onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                                    onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
                                    placeholder="Search stock (e.g., AAPL, Apple, TSLA)"
                                    autoComplete="off"
                                    className="w-full pl-10 pr-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-[#111418] dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                />
                                {searchingSymbols && (
                                    <span className="material-symbols-outlined animate-spin absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 text-base">sync</span>
                                )}

                                {/* Autocomplete dropdown */}
                                {showSuggestions && suggestions.length > 0 && (
                                    <ul className="absolute z-20 mt-1 w-full max-h-72 overflow-y-auto bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg">
                                        {suggestions.map((s, i) => (
                                            <li key={`${s.symbol}-${s.currency}-${i}`}>
                                                <button
                                                    type="button"
                                                    onMouseDown={(e) => { e.preventDefault(); selectSuggestion(s.symbol); }}
                                                    className="w-full flex items-center justify-between gap-3 px-3 py-2 text-left hover:bg-gray-100 dark:hover:bg-gray-700/60 transition-colors"
                                                >
                                                    <span className="flex items-center gap-2 min-w-0">
                                                        <span className="font-bold text-[#111418] dark:text-white">{s.symbol}</span>
                                                        <span className="truncate text-sm text-gray-500 dark:text-gray-400">{s.name}</span>
                                                    </span>
                                                    <span className="flex items-center gap-2 shrink-0">
                                                        {s.hasOptions && (
                                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">OPT</span>
                                                        )}
                                                        <span className="text-xs text-gray-400">{s.currency}</span>
                                                    </span>
                                                </button>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        </div>
                        <button
                            onClick={handleSearch}
                            disabled={loadingQuote || loadingChain}
                            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                        >
                            {(loadingQuote || loadingChain) ? (
                                <>
                                    <span className="material-symbols-outlined animate-spin">sync</span>
                                    Loading...
                                </>
                            ) : (
                                <>
                                    <span className="material-symbols-outlined">trending_up</span>
                                    Get Data
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>

            {error && (
                <div className="p-4 bg-red-100 dark:bg-red-900/30 border border-red-400 dark:border-red-700 text-red-700 dark:text-red-300 rounded-lg">
                    <p className="font-medium">{error}</p>
                    {broker === 'ibkr' && error.includes('ibkr') && (
                        <p className="mt-2 text-sm">
                            To use IBKR, ensure TWS or IB Gateway is running on port 7496 (live) or 7497 (paper).
                        </p>
                    )}
                    {broker === 'tastytrade' && error.includes('tastytrade') && (
                        <p className="mt-2 text-sm">
                            Ensure your Tastytrade credentials are configured in the .env file.
                        </p>
                    )}
                </div>
            )}

            {/* Stock Quote Card */}
            {stockQuote && (
                <div className="bg-white dark:bg-gray-900 rounded-xl p-6 border border-gray-200 dark:border-gray-800">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                            <h3 className="text-2xl font-bold text-[#111418] dark:text-white">{stockQuote.symbol}</h3>
                            <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-sm">
                                Stock
                            </span>
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                                broker === 'tastytrade' ? 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300' :
                                broker === 'ibkr' ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300' :
                                'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300'
                            }`}>
                                {broker === 'tastytrade' ? 'Tastytrade' : broker === 'ibkr' ? 'IBKR' : 'Massive'}
                            </span>
                            {broker === 'ibkr' && isLive && (
                                <span className="flex items-center gap-1 px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded text-xs font-medium">
                                    <span className="relative flex h-2 w-2">
                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-500 opacity-75"></span>
                                        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                                    </span>
                                    LIVE
                                </span>
                            )}
                        </div>
                        <p className="text-3xl font-bold text-[#111418] dark:text-white">
                            {formatPrice(stockQuote.price)}
                        </p>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Last Price</p>
                            <p className="text-xl font-semibold text-[#111418] dark:text-white">{formatPrice(stockQuote.price)}</p>
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Bid</p>
                            <p className="text-xl font-semibold text-[#111418] dark:text-white">{formatPrice(stockQuote.bid)}</p>
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Ask</p>
                            <p className="text-xl font-semibold text-[#111418] dark:text-white">{formatPrice(stockQuote.ask)}</p>
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Spread</p>
                            <p className="text-xl font-semibold text-[#111418] dark:text-white">
                                {stockQuote.bid && stockQuote.ask ? formatPrice(stockQuote.ask - stockQuote.bid) : '-'}
                            </p>
                        </div>
                    </div>
                    {/* Buy / Sell */}
                    <div className="grid grid-cols-2 gap-3 mt-5">
                        <button
                            onClick={() => openStockTicket('BUY')}
                            className="py-3 rounded-lg font-bold text-white bg-green-600 hover:bg-green-700 transition-colors"
                        >
                            Buy
                        </button>
                        <button
                            onClick={() => openStockTicket('SELL')}
                            className="py-3 rounded-lg font-bold text-white bg-red-600 hover:bg-red-700 transition-colors"
                        >
                            Sell
                        </button>
                    </div>
                </div>
            )}

            {/* Option Chain Section */}
            {optionChain && (
                <div className="bg-white dark:bg-gray-900 rounded-xl p-6 border border-gray-200 dark:border-gray-800">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-bold text-[#111418] dark:text-white">Options Chain - {ticker}</h3>
                        <div className="flex items-center gap-4">
                            {/* Chain View Toggle */}
                            <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg">
                                <button
                                    onClick={() => setChainView('all')}
                                    className={`px-3 py-1 rounded text-sm font-medium transition-all ${chainView === 'all'
                                        ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm'
                                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                                        }`}
                                >
                                    All
                                </button>
                                <button
                                    onClick={() => setChainView('calls')}
                                    className={`px-3 py-1 rounded text-sm font-medium transition-all ${chainView === 'calls'
                                        ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-400 shadow-sm'
                                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                                        }`}
                                >
                                    Calls
                                </button>
                                <button
                                    onClick={() => setChainView('puts')}
                                    className={`px-3 py-1 rounded text-sm font-medium transition-all ${chainView === 'puts'
                                        ? 'bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-400 shadow-sm'
                                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                                        }`}
                                >
                                    Puts
                                </button>
                            </div>

                            {/* Strikes count selector */}
                            <select
                                value={numStrikes}
                                onChange={(e) => handleStrikesChange(Number(e.target.value))}
                                title="Number of strikes (centred on ATM)"
                                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-[#111418] dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                            >
                                {[10, 20, 40, 60, 100].map((n) => (
                                    <option key={n} value={n}>{n} strikes</option>
                                ))}
                            </select>

                            {/* Expiration Selector */}
                            <select
                                value={selectedExpiration}
                                onChange={(e) => handleExpirationChange(e.target.value)}
                                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-[#111418] dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                            >
                                {optionChain.expirations?.map((exp) => (
                                    <option key={exp} value={exp}>
                                        {exp}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>

                    {loadingChain ? (
                        <div className="text-center py-10 text-gray-500">Loading option chain...</div>
                    ) : currentChainData ? (
                        <div className="overflow-x-auto">
                            {chainView === 'all' ? (
                                // Combined Calls and Puts View
                                <table className="w-full text-sm">
                                    <thead className="text-xs text-gray-500 dark:text-gray-400 uppercase border-b dark:border-gray-800">
                                        <tr>
                                            <th colSpan={6} className="py-2 px-2 text-center bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400">
                                                CALLS
                                            </th>
                                            <th className="py-2 px-2 text-center bg-gray-100 dark:bg-gray-800">
                                                Strike
                                            </th>
                                            <th colSpan={6} className="py-2 px-2 text-center bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400">
                                                PUTS
                                            </th>
                                        </tr>
                                        <tr>
                                            <th className="py-2 px-1 text-right text-green-700 dark:text-green-400">IV</th>
                                            <th className="py-2 px-1 text-right text-green-700 dark:text-green-400">Delta</th>
                                            <th className="py-2 px-1 text-right text-green-700 dark:text-green-400">Bid</th>
                                            <th className="py-2 px-1 text-right text-green-700 dark:text-green-400">Ask</th>
                                            <th className="py-2 px-1 text-right text-green-700 dark:text-green-400">Vol</th>
                                            <th className="py-2 px-1 text-right text-green-700 dark:text-green-400">OI</th>
                                            <th className="py-2 px-2 text-center bg-gray-100 dark:bg-gray-800 font-bold">$</th>
                                            <th className="py-2 px-1 text-right text-red-700 dark:text-red-400">OI</th>
                                            <th className="py-2 px-1 text-right text-red-700 dark:text-red-400">Vol</th>
                                            <th className="py-2 px-1 text-right text-red-700 dark:text-red-400">Bid</th>
                                            <th className="py-2 px-1 text-right text-red-700 dark:text-red-400">Ask</th>
                                            <th className="py-2 px-1 text-right text-red-700 dark:text-red-400">Delta</th>
                                            <th className="py-2 px-1 text-right text-red-700 dark:text-red-400">IV</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {(() => {
                                            // Get all unique strikes from both calls and puts
                                            const allStrikes = new Set<number>();
                                            currentChainData.calls?.forEach(c => allStrikes.add(c.strike));
                                            currentChainData.puts?.forEach(p => allStrikes.add(p.strike));
                                            const strikes = Array.from(allStrikes).sort((a, b) => a - b);

                                            // Create lookup maps
                                            const callsMap = new Map(currentChainData.calls?.map(c => [c.strike, c]) || []);
                                            const putsMap = new Map(currentChainData.puts?.map(p => [p.strike, p]) || []);

                                            const underlyingPrice = optionChain.underlyingPrice || stockQuote?.price || 0;

                                            return strikes.map((strike, idx) => {
                                                const call = callsMap.get(strike);
                                                const put = putsMap.get(strike);
                                                const isITM = strike < underlyingPrice;
                                                const isATM = Math.abs(strike - underlyingPrice) < underlyingPrice * 0.01;

                                                return (
                                                    <tr
                                                        key={idx}
                                                        className={`border-b dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors ${isATM ? 'bg-yellow-50 dark:bg-yellow-900/20' : ''
                                                            }`}
                                                    >
                                                        {/* Call side */}
                                                        <td className={`py-2 px-1 text-right text-xs ${isITM ? 'bg-green-50 dark:bg-green-900/10' : ''}`}>
                                                            {formatPercent(call?.iv)}
                                                        </td>
                                                        <td className={`py-2 px-1 text-right text-xs ${isITM ? 'bg-green-50 dark:bg-green-900/10' : ''}`}>
                                                            {formatGreek(call?.delta, 2)}
                                                        </td>
                                                        <td
                                                            onClick={() => call && openOptionTicket(call, 'call', 'BUY')}
                                                            title={call ? 'Click to trade call' : ''}
                                                            className={`py-2 px-1 text-right font-medium ${call ? 'cursor-pointer hover:underline' : ''} ${isITM ? 'bg-green-50 dark:bg-green-900/10' : ''}`}>
                                                            {formatPrice(call?.bid)}
                                                        </td>
                                                        <td
                                                            onClick={() => call && openOptionTicket(call, 'call', 'BUY')}
                                                            title={call ? 'Click to trade call' : ''}
                                                            className={`py-2 px-1 text-right font-medium ${call ? 'cursor-pointer hover:underline' : ''} ${isITM ? 'bg-green-50 dark:bg-green-900/10' : ''}`}>
                                                            {formatPrice(call?.ask)}
                                                        </td>
                                                        <td className={`py-2 px-1 text-right text-xs ${isITM ? 'bg-green-50 dark:bg-green-900/10' : ''}`}>
                                                            {call?.volume?.toLocaleString() || '-'}
                                                        </td>
                                                        <td className={`py-2 px-1 text-right text-xs ${isITM ? 'bg-green-50 dark:bg-green-900/10' : ''}`}>
                                                            {call?.openInterest?.toLocaleString() || '-'}
                                                        </td>

                                                        {/* Strike */}
                                                        <td className={`py-2 px-2 text-center font-bold bg-gray-100 dark:bg-gray-800 ${isATM ? 'text-blue-600 dark:text-blue-400' : 'text-[#111418] dark:text-white'
                                                            }`}>
                                                            {strike.toFixed(2)}
                                                        </td>

                                                        {/* Put side */}
                                                        <td className={`py-2 px-1 text-right text-xs ${!isITM ? 'bg-red-50 dark:bg-red-900/10' : ''}`}>
                                                            {put?.openInterest?.toLocaleString() || '-'}
                                                        </td>
                                                        <td className={`py-2 px-1 text-right text-xs ${!isITM ? 'bg-red-50 dark:bg-red-900/10' : ''}`}>
                                                            {put?.volume?.toLocaleString() || '-'}
                                                        </td>
                                                        <td
                                                            onClick={() => put && openOptionTicket(put, 'put', 'BUY')}
                                                            title={put ? 'Click to trade put' : ''}
                                                            className={`py-2 px-1 text-right font-medium ${put ? 'cursor-pointer hover:underline' : ''} ${!isITM ? 'bg-red-50 dark:bg-red-900/10' : ''}`}>
                                                            {formatPrice(put?.bid)}
                                                        </td>
                                                        <td
                                                            onClick={() => put && openOptionTicket(put, 'put', 'BUY')}
                                                            title={put ? 'Click to trade put' : ''}
                                                            className={`py-2 px-1 text-right font-medium ${put ? 'cursor-pointer hover:underline' : ''} ${!isITM ? 'bg-red-50 dark:bg-red-900/10' : ''}`}>
                                                            {formatPrice(put?.ask)}
                                                        </td>
                                                        <td className={`py-2 px-1 text-right text-xs ${!isITM ? 'bg-red-50 dark:bg-red-900/10' : ''}`}>
                                                            {formatGreek(put?.delta, 2)}
                                                        </td>
                                                        <td className={`py-2 px-1 text-right text-xs ${!isITM ? 'bg-red-50 dark:bg-red-900/10' : ''}`}>
                                                            {formatPercent(put?.iv)}
                                                        </td>
                                                    </tr>
                                                );
                                            });
                                        })()}
                                    </tbody>
                                </table>
                            ) : (
                                // Single side view (Calls or Puts)
                                <table className="w-full text-sm">
                                    <thead className="text-xs text-gray-500 dark:text-gray-400 uppercase border-b dark:border-gray-800">
                                        <tr>
                                            <th className="py-3 px-2 text-left">Strike</th>
                                            <th className="py-3 px-2 text-right">Bid</th>
                                            <th className="py-3 px-2 text-right">Ask</th>
                                            <th className="py-3 px-2 text-right">Last</th>
                                            <th className="py-3 px-2 text-right">Volume</th>
                                            <th className="py-3 px-2 text-right">OI</th>
                                            <th className="py-3 px-2 text-right">Delta</th>
                                            <th className="py-3 px-2 text-right">Gamma</th>
                                            <th className="py-3 px-2 text-right">Theta</th>
                                            <th className="py-3 px-2 text-right">Vega</th>
                                            <th className="py-3 px-2 text-right">IV</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {(chainView === 'calls' ? currentChainData.calls : currentChainData.puts)?.map((option, idx) => {
                                            const underlyingPrice = optionChain.underlyingPrice || stockQuote?.price || 0;
                                            const isITM = chainView === 'calls'
                                                ? option.strike < underlyingPrice
                                                : option.strike > underlyingPrice;
                                            const isATM = Math.abs(option.strike - underlyingPrice) < underlyingPrice * 0.01;

                                            return (
                                                <tr
                                                    key={idx}
                                                    onClick={() => openOptionTicket(option, chainView === 'calls' ? 'call' : 'put', 'BUY')}
                                                    title="Click to trade"
                                                    className={`border-b dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors cursor-pointer ${isITM
                                                        ? chainView === 'calls'
                                                            ? 'bg-green-50 dark:bg-green-900/10'
                                                            : 'bg-red-50 dark:bg-red-900/10'
                                                        : ''
                                                        } ${isATM ? 'ring-2 ring-blue-400 ring-inset' : ''}`}
                                                >
                                                    <td className="py-2 px-2 font-bold text-[#111418] dark:text-white">
                                                        ${option.strike.toFixed(2)}
                                                    </td>
                                                    <td className="py-2 px-2 text-right font-medium">{formatPrice(option.bid)}</td>
                                                    <td className="py-2 px-2 text-right font-medium">{formatPrice(option.ask)}</td>
                                                    <td className="py-2 px-2 text-right">{formatPrice(option.last)}</td>
                                                    <td className="py-2 px-2 text-right text-gray-600 dark:text-gray-400">
                                                        {option.volume?.toLocaleString() || '-'}
                                                    </td>
                                                    <td className="py-2 px-2 text-right text-gray-600 dark:text-gray-400">
                                                        {option.openInterest?.toLocaleString() || '-'}
                                                    </td>
                                                    <td className="py-2 px-2 text-right">{formatGreek(option.delta, 4)}</td>
                                                    <td className="py-2 px-2 text-right">{formatGreek(option.gamma, 4)}</td>
                                                    <td className="py-2 px-2 text-right">{formatGreek(option.theta, 4)}</td>
                                                    <td className="py-2 px-2 text-right">{formatGreek(option.vega, 4)}</td>
                                                    <td className="py-2 px-2 text-right">{formatPercent(option.iv)}</td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    ) : (
                        <div className="text-center py-10 text-gray-500">
                            No option chain data available for {selectedExpiration}
                        </div>
                    )}
                </div>
            )}

            {/* No Data State */}
            {!stockQuote && !optionChain && !loadingQuote && !loadingChain && !error && (
                <div className="text-center py-10 text-gray-500 dark:text-gray-400">
                    Enter a ticker symbol and click "Get Data" to view market data
                </div>
            )}

            {/* Trade ticket (buy/sell) */}
            <TradeTicket
                isOpen={!!ticket}
                onClose={() => setTicket(null)}
                secType={ticket?.secType || 'stock'}
                symbol={ticket?.symbol || ''}
                displayName={ticket?.displayName || ''}
                referencePrice={ticket?.referencePrice}
                initialSide={ticket?.side || 'BUY'}
            />
        </div>
    );
};
