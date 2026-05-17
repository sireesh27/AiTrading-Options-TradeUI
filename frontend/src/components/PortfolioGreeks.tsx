import React, { useEffect, useState } from 'react';
import { MarketGreeksTable } from './MarketGreeksTable';
import { MarketDataTab } from './MarketDataTab';

interface PortfolioTotals {
    net_delta: number;
    net_gamma: number;
    net_theta: number;
    net_vega: number;
    total_positions: number;
    total_value: number;
    num_underlyings: number;
}

interface Position {
    symbol: string;
    type: string;
    qty: number;
    delta: number;
    delta_exposure: number;
    gamma: number;
    theta: number;
    vega: number;
    iv: number;
    value: number;
    broker: string;
    pl: number;
    avgPrice: number;
    currentPrice: number;
    plPercent: number;
    rho: number;
}

interface UnderlyingData {
    underlying: string;
    positions: Position[];
    net_delta: number;
    net_gamma: number;
    net_theta: number;
    net_vega: number;
    total_value: number;
}

interface PortfolioGreeksData {
    portfolio_totals: PortfolioTotals;
    by_underlying: Record<string, UnderlyingData>;
}

const API_BASE_URL = 'http://localhost:8000';

interface PortfolioGreeksProps {
    refreshTrigger?: number;
}

export const PortfolioGreeks: React.FC<PortfolioGreeksProps> = ({ refreshTrigger = 0 }) => {
    const [data, setData] = useState<PortfolioGreeksData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [expandedUnderlyings, setExpandedUnderlyings] = useState<Set<string>>(new Set());
    const [activeTab, setActiveTab] = useState<'open-positions' | 'market-greeks' | 'market-data'>('open-positions');

    const loadData = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(`${API_BASE_URL}/api/portfolio-greeks`);
            if (!response.ok) {
                throw new Error(`Error fetching portfolio Greeks: ${response.statusText}`);
            }
            const result = await response.json();
            setData(result);
        } catch (err: any) {
            console.error(err);
            setError('Failed to fetch portfolio Greeks. Ensure backend is running.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, [refreshTrigger]);

    const toggleExpand = (underlying: string) => {
        const newExpanded = new Set(expandedUnderlyings);
        if (newExpanded.has(underlying)) {
            newExpanded.delete(underlying);
        } else {
            newExpanded.add(underlying);
        }
        setExpandedUnderlyings(newExpanded);
    };

    // Helper function to calculate dollar-scaled Greeks for individual positions
    const calculatePositionGreeks = (position: Position) => {
        if (position.type === 'stock') {
            // Stock: qty × 1.0 delta per share
            return {
                delta: position.qty * 1.0,
                gamma: 0,
                theta: 0,
                vega: 0
            };
        } else {
            // Option: Greek × qty × 100
            return {
                delta: position.delta * position.qty * 100,
                gamma: position.gamma * position.qty * 100,
                theta: position.theta * position.qty * 100,
                vega: position.vega * position.qty * 100
            };
        }
    };

    if (loading) {
        return <div className="text-center py-10">Loading portfolio Greeks...</div>;
    }

    if (error) {
        return (
            <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg">
                {error}
            </div>
        );
    }

    if (!data) {
        return <div className="text-center py-10">No data available.</div>;
    }

    const totals = data.portfolio_totals;

    return (
        <div className="flex flex-col gap-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-[#111418] dark:text-white">Portfolio Greeks</h2>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-white dark:bg-gray-900 rounded-xl p-6 border border-gray-200 dark:border-gray-800">
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Net Delta</p>
                    <p className={`text-3xl font-bold ${totals.net_delta >= 0 ? 'text-green-600 dark:text-green-500' : 'text-red-600 dark:text-red-500'}`}>
                        {totals.net_delta >= 0 ? '+$' : '-$'}{Math.abs(totals.net_delta).toFixed(2)}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {totals.net_delta > 0 ? 'Bullish' : totals.net_delta < 0 ? 'Bearish' : 'Neutral'}
                    </p>
                </div>

                <div className="bg-white dark:bg-gray-900 rounded-xl p-6 border border-gray-200 dark:border-gray-800">
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Net Theta (Daily)</p>
                    <p className={`text-3xl font-bold ${totals.net_theta >= 0 ? 'text-green-600 dark:text-green-500' : 'text-red-600 dark:text-red-500'}`}>
                        {totals.net_theta >= 0 ? '+$' : '-$'}{Math.abs(totals.net_theta).toFixed(2)}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {totals.net_theta > 0 ? 'Positive time decay' : 'Losing to time decay'}
                    </p>
                </div>

                <div className="bg-white dark:bg-gray-900 rounded-xl p-6 border border-gray-200 dark:border-gray-800">
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Net Gamma</p>
                    <p className="text-3xl font-bold text-[#111418] dark:text-white">
                        {totals.net_gamma.toFixed(4)}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Delta sensitivity</p>
                </div>

                <div className="bg-white dark:bg-gray-900 rounded-xl p-6 border border-gray-200 dark:border-gray-800">
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Net Vega</p>
                    <p className={`text-3xl font-bold ${totals.net_vega >= 0 ? 'text-green-600 dark:text-green-500' : 'text-red-600 dark:text-red-500'}`}>
                        {totals.net_vega >= 0 ? '+$' : '-$'}{Math.abs(totals.net_vega).toFixed(2)}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">IV sensitivity</p>
                </div>
            </div>

            {/* Portfolio Stats */}
            <div className="bg-white dark:bg-gray-900 rounded-xl p-6 border border-gray-200 dark:border-gray-800">
                <h3 className="text-lg font-bold text-[#111418] dark:text-white mb-4">Portfolio Summary</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                        <p className="text-sm text-gray-500 dark:text-gray-400">Total Positions</p>
                        <p className="text-xl font-semibold text-[#111418] dark:text-white">{totals.total_positions}</p>
                    </div>
                    <div>
                        <p className="text-sm text-gray-500 dark:text-gray-400">Underlyings</p>
                        <p className="text-xl font-semibold text-[#111418] dark:text-white">{totals.num_underlyings}</p>
                    </div>
                    <div>
                        <p className="text-sm text-gray-500 dark:text-gray-400">Total Value</p>
                        <p className="text-xl font-semibold text-[#111418] dark:text-white">
                            ${totals.total_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </p>
                    </div>
                    <div>
                        <p className="text-sm text-gray-500 dark:text-gray-400">Delta per $1000</p>
                        <p className="text-xl font-semibold text-[#111418] dark:text-white">
                            {((totals.net_delta / totals.total_value) * 1000).toFixed(2)}
                        </p>
                    </div>
                </div>
            </div>

            {/* Data Tabs */}
            <div>
                <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg w-fit mb-4">
                    <button
                        onClick={() => setActiveTab('open-positions')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${activeTab === 'open-positions'
                            ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm'
                            : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                            }`}
                    >
                        Open Positions
                    </button>
                    <button
                        onClick={() => setActiveTab('market-greeks')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${activeTab === 'market-greeks'
                            ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm'
                            : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                            }`}
                    >
                        Market Greeks
                    </button>
                    <button
                        onClick={() => setActiveTab('market-data')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${activeTab === 'market-data'
                            ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm'
                            : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                            }`}
                    >
                        Market Data
                    </button>
                </div>

                {activeTab === 'market-data' ? (
                    <MarketDataTab />
                ) : activeTab === 'open-positions' ? (
                    <>
                        <div className="bg-white dark:bg-gray-900 rounded-xl p-6 border border-gray-200 dark:border-gray-800">
                            <h3 className="text-lg font-bold text-[#111418] dark:text-white mb-4">Open Positions</h3>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead className="text-xs text-gray-500 dark:text-gray-400 uppercase border-b dark:border-gray-800">
                                        <tr>
                                            <th className="py-3 px-2 text-left">Symbol</th>
                                            <th className="py-3 px-2 text-left">Source</th>
                                            <th className="py-3 px-2 text-right">Positions</th>
                                            <th className="py-3 px-2 text-right">Qty</th>
                                            <th className="py-3 px-2 text-right">Value</th>
                                            <th className="py-3 px-2 text-right">Net Delta</th>
                                            <th className="py-3 px-2 text-right">Net Theta</th>
                                            <th className="py-3 px-2 text-right">Net Gamma</th>
                                            <th className="py-3 px-2 text-right">Net Vega</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {Object.values(data.by_underlying)
                                            .sort((a, b) => Math.abs(b.net_delta) - Math.abs(a.net_delta))
                                            .map((underlying, idx) => {
                                                const isExpanded = expandedUnderlyings.has(underlying.underlying);
                                                const hasMultiplePositions = underlying.positions.length > 1;
                                                const uniqueBrokers = Array.from(new Set(underlying.positions.map(p => p.broker)));
                                                const sourceText = uniqueBrokers.length > 1 ? 'Multiple' : uniqueBrokers[0];

                                                return (
                                                    <React.Fragment key={idx}>
                                                        {/* Main row - Aggregated Greeks */}
                                                        <tr className="border-b dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                                                            <td className="py-3 px-2 font-medium text-[#111418] dark:text-white">
                                                                <div className="flex items-center gap-2">
                                                                    {hasMultiplePositions && (
                                                                        <button
                                                                            onClick={() => toggleExpand(underlying.underlying)}
                                                                            className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                                                                        >
                                                                            <span className="material-symbols-outlined text-base">
                                                                                {isExpanded ? 'remove' : 'add'}
                                                                            </span>
                                                                        </button>
                                                                    )}
                                                                    <span>{underlying.underlying}</span>
                                                                </div>
                                                            </td>
                                                            <td className="py-3 px-2 text-left text-gray-600 dark:text-gray-300">
                                                                {sourceText}
                                                            </td>
                                                            <td className="py-3 px-2 text-right text-gray-600 dark:text-gray-300">
                                                                {underlying.positions.length}
                                                            </td>
                                                            <td className="py-3 px-2 text-right text-gray-600 dark:text-gray-300">
                                                                {underlying.positions.reduce((sum, p) => sum + Math.abs(p.qty), 0).toFixed(0)}
                                                            </td>
                                                            <td className="py-3 px-2 text-right text-gray-600 dark:text-gray-300">
                                                                ${underlying.total_value.toFixed(2)}
                                                            </td>
                                                            <td className={`py-3 px-2 text-right font-semibold ${underlying.net_delta >= 0 ? 'text-green-600 dark:text-green-500' : 'text-red-600 dark:text-red-500'}`}>
                                                                {underlying.net_delta >= 0 ? '+$' : '-$'}{Math.abs(underlying.net_delta).toFixed(2)}
                                                            </td>
                                                            <td className={`py-3 px-2 text-right ${underlying.net_theta >= 0 ? 'text-green-600 dark:text-green-500' : 'text-red-600 dark:text-red-500'}`}>
                                                                {underlying.net_theta >= 0 ? '+$' : '-$'}{Math.abs(underlying.net_theta).toFixed(2)}
                                                            </td>
                                                            <td className="py-3 px-2 text-right text-gray-600 dark:text-gray-300">
                                                                {underlying.net_gamma.toFixed(4)}
                                                            </td>
                                                            <td className="py-3 px-2 text-right text-gray-600 dark:text-gray-300">
                                                                ${Math.abs(underlying.net_vega).toFixed(2)}
                                                            </td>
                                                        </tr>

                                                        {/* Expanded rows - Individual positions */}
                                                        {isExpanded && hasMultiplePositions && underlying.positions.map((position, posIdx) => {
                                                            const scaledGreeks = calculatePositionGreeks(position);
                                                            return (
                                                                <tr
                                                                    key={`${idx}-${posIdx}`}
                                                                    className="border-b dark:border-gray-800 bg-gray-50 dark:bg-gray-800/30 hover:bg-gray-100 dark:hover:bg-gray-800/50 transition-colors"
                                                                >
                                                                    <td className="py-2 px-2 pl-8 text-sm text-gray-600 dark:text-gray-400">
                                                                        <div className="flex items-center gap-2">
                                                                            <span>{position.symbol}</span>
                                                                            <span className="text-xs text-gray-500">
                                                                                ({position.type.toUpperCase()})
                                                                            </span>
                                                                        </div>
                                                                    </td>
                                                                    <td className="py-2 px-2 text-left text-xs text-gray-500 dark:text-gray-400">
                                                                        {position.broker}
                                                                    </td>
                                                                    <td className="py-2 px-2 text-right text-xs text-gray-500 dark:text-gray-400">
                                                                        -
                                                                    </td>
                                                                    <td className="py-2 px-2 text-right text-sm text-gray-600 dark:text-gray-400">
                                                                        <span className={`font-semibold ${position.qty >= 0 ? 'text-green-600 dark:text-green-500' : 'text-red-600 dark:text-red-500'}`}>
                                                                            {position.qty >= 0 ? '+' : '-'}{Math.abs(position.qty).toFixed(position.type === 'stock' ? 2 : 0)}
                                                                        </span>
                                                                    </td>
                                                                    <td className="py-2 px-2 text-right text-sm text-gray-600 dark:text-gray-400">
                                                                        ${position.value.toFixed(2)}
                                                                    </td>
                                                                    <td className="py-2 px-2 text-right text-sm text-gray-600 dark:text-gray-400">
                                                                        <div className="flex flex-col">
                                                                            <span>{scaledGreeks.delta >= 0 ? '+$' : '-$'}{Math.abs(scaledGreeks.delta).toFixed(2)}</span>
                                                                            <span className="text-xs text-gray-500">({position.delta.toFixed(4)})</span>
                                                                        </div>
                                                                    </td>
                                                                    <td className="py-2 px-2 text-right text-sm text-gray-600 dark:text-gray-400">
                                                                        <div className="flex flex-col">
                                                                            <span>{scaledGreeks.theta >= 0 ? '+$' : '-$'}{Math.abs(scaledGreeks.theta).toFixed(2)}</span>
                                                                            <span className="text-xs text-gray-500">({position.theta.toFixed(4)})</span>
                                                                        </div>
                                                                    </td>
                                                                    <td className="py-2 px-2 text-right text-sm text-gray-600 dark:text-gray-400">
                                                                        <div className="flex flex-col">
                                                                            <span>{scaledGreeks.gamma.toFixed(4)}</span>
                                                                            <span className="text-xs text-gray-500">({position.gamma.toFixed(4)})</span>
                                                                        </div>
                                                                    </td>
                                                                    <td className="py-2 px-2 text-right text-sm text-gray-600 dark:text-gray-400">
                                                                        <div className="flex flex-col">
                                                                            <span>${Math.abs(scaledGreeks.vega).toFixed(2)}</span>
                                                                            <span className="text-xs text-gray-500">({position.vega.toFixed(4)})</span>
                                                                        </div>
                                                                    </td>
                                                                </tr>
                                                            );
                                                        })}
                                                    </React.Fragment>
                                                );
                                            })}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Interpretation Guide - Only show for Open Positions tab if desired, or keep global */}
                        <div className="bg-blue-50 dark:bg-blue-900/20 rounded-xl p-6 border border-blue-200 dark:border-blue-800 mt-6">
                            <h3 className="text-lg font-bold text-blue-900 dark:text-blue-100 mb-3">Understanding Your Greeks</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                                <div>
                                    <p className="font-semibold text-blue-800 dark:text-blue-200 mb-1">Delta ({totals.net_delta.toFixed(2)})</p>
                                    <p className="text-blue-700 dark:text-blue-300">
                                        Your portfolio moves ${Math.abs(totals.net_delta).toFixed(2)} for every $1 move in the underlyings.
                                        {totals.net_delta > 0 ? ' You profit if markets go UP.' : ' You profit if markets go DOWN.'}
                                    </p>
                                </div>
                                <div>
                                    <p className="font-semibold text-blue-800 dark:text-blue-200 mb-1">Theta ({totals.net_theta >= 0 ? '+$' : '-$'}{Math.abs(totals.net_theta).toFixed(2)}/day)</p>
                                    <p className="text-blue-700 dark:text-blue-300">
                                        {totals.net_theta > 0
                                            ? `Time decay works FOR you. You gain $${Math.abs(totals.net_theta).toFixed(2)} per day.`
                                            : `Time decay works AGAINST you. You lose $${Math.abs(totals.net_theta).toFixed(2)} per day.`
                                        }
                                    </p>
                                </div>
                                <div>
                                    <p className="font-semibold text-blue-800 dark:text-blue-200 mb-1">Gamma ({totals.net_gamma.toFixed(4)})</p>
                                    <p className="text-blue-700 dark:text-blue-300">
                                        {totals.net_gamma > 0
                                            ? 'Your delta increases as markets move. More profit potential.'
                                            : 'Your delta decreases as markets move. Profit potential shrinks.'}
                                    </p>
                                </div>
                                <div>
                                    <p className="font-semibold text-blue-800 dark:text-blue-200 mb-1">Vega ({totals.net_vega.toFixed(2)})</p>
                                    <p className="text-blue-700 dark:text-blue-300">
                                        {totals.net_vega > 0
                                            ? 'You profit from increasing volatility (IV).'
                                            : 'You profit from decreasing volatility (IV).'}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </>
                ) : (
                    <div className="bg-white dark:bg-gray-900 rounded-xl p-6 border border-gray-200 dark:border-gray-800">
                        <h3 className="text-lg font-bold text-[#111418] dark:text-white mb-4">Market Greeks</h3>
                        {(() => {
                            // Transform data for MarketGreeksTable
                            const flatPositions: any[] = [];
                            const greeksData: Record<string, any> = {};
                            const symbols: string[] = [];

                            Object.values(data.by_underlying).forEach(underlying => {
                                underlying.positions.forEach(pos => {
                                    symbols.push(pos.symbol);
                                    flatPositions.push({
                                        symbol: pos.symbol,
                                        qty: pos.qty,
                                        value: pos.value,
                                        pl: pos.pl,
                                        avgPrice: pos.avgPrice,
                                        currentPrice: pos.currentPrice,
                                        plPercent: pos.plPercent,
                                        source: pos.broker
                                    });

                                    if (pos.type === 'option') {
                                        greeksData[pos.symbol] = {
                                            delta: pos.delta,
                                            gamma: pos.gamma,
                                            theta: pos.theta,
                                            vega: pos.vega,
                                            rho: pos.rho,
                                            iv: pos.iv
                                        };
                                    }
                                });
                            });

                            return (
                                <MarketGreeksTable
                                    data={greeksData}
                                    symbols={symbols}
                                    positions={flatPositions}
                                />
                            );
                        })()}
                    </div>
                )}
            </div>
        </div>
    );
};
