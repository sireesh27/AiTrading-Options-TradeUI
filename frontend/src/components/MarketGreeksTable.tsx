import React, { useState } from 'react';

interface GreeksData {
    delta: number;
    gamma: number;
    theta: number;
    vega: number;
    rho: number;
    iv: number;
}

interface Position {
    symbol: string;
    qty: number;
    value: number;
    pl: number;
    avgPrice: number;
    currentPrice: number;
    plPercent: number;
    source: string;
}

interface MarketGreeksTableProps {
    data: Record<string, GreeksData | null>;
    symbols: string[];
    positions: Position[];
}

interface GroupedData {
    underlying: string;
    stockSymbol: string | null;
    stockGreeks: GreeksData | null;
    options: Array<{
        symbol: string;
        greeks: GreeksData;
        qty: number;
    }>;
    aggregatedGreeks: {
        greeks: GreeksData;
        dollarAmounts: {
            delta: number;
            theta: number;
            gamma: number;
            vega: number;
        };
    } | null;
}

// Extract underlying symbol from option symbol
const extractUnderlying = (symbol: string): string => {
    const clean = symbol.replace(/\s/g, '');
    const match = clean.match(/^([A-Z]+)(\d{6})([CP])(\d{8})$/);
    if (match) {
        return match[1];
    }
    return symbol;
};

// Check if symbol is an option
const isOption = (symbol: string): boolean => {
    const clean = symbol.replace(/\s/g, '');
    return /^[A-Z]+\d{6}[CP]\d{8}$/.test(clean);
};

// Calculate dollar amount from Greeks
const calculateDollarAmount = (greek: number, qty: number): number => {
    // For options: 1 contract = 100 shares
    // Greek values are per share, so multiply by 100 to get per contract
    return greek * Math.abs(qty) * 100;
};

// Aggregate Greeks from multiple options
const aggregateGreeks = (optionsList: Array<{ symbol: string; greeks: GreeksData; qty: number }>): {
    greeks: GreeksData;
    dollarAmounts: {
        delta: number;
        theta: number;
        gamma: number;
        vega: number;
    };
} | null => {
    if (optionsList.length === 0) return null;

    const totals = {
        delta: 0,
        gamma: 0,
        theta: 0,
        vega: 0,
        rho: 0,
        iv: 0
    };

    const dollarTotals = {
        delta: 0,
        theta: 0,
        gamma: 0,
        vega: 0
    };

    optionsList.forEach(opt => {
        // Sum Greeks
        totals.delta += opt.greeks.delta;
        totals.gamma += opt.greeks.gamma;
        totals.theta += opt.greeks.theta;
        totals.vega += opt.greeks.vega;
        totals.rho += opt.greeks.rho;
        totals.iv += opt.greeks.iv;

        // Calculate dollar amounts considering position sign
        const sign = opt.qty >= 0 ? 1 : -1;
        dollarTotals.delta += sign * calculateDollarAmount(opt.greeks.delta, opt.qty);
        dollarTotals.theta += sign * calculateDollarAmount(opt.greeks.theta, opt.qty);
        dollarTotals.gamma += sign * calculateDollarAmount(opt.greeks.gamma, opt.qty);
        dollarTotals.vega += sign * calculateDollarAmount(opt.greeks.vega, opt.qty);
    });

    // Average IV instead of sum
    totals.iv = totals.iv / optionsList.length;

    return {
        greeks: totals,
        dollarAmounts: dollarTotals
    };
};

const formatDollar = (value: number): string => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}$${Math.abs(value).toFixed(2)}`;
};

export const MarketGreeksTable: React.FC<MarketGreeksTableProps> = ({ data, symbols, positions }) => {
    const [expandedUnderlyings, setExpandedUnderlyings] = useState<Set<string>>(new Set());

    // Create a map of symbol -> position for quick lookup
    const positionMap = new Map<string, Position>();
    positions.forEach(pos => positionMap.set(pos.symbol, pos));

    // Group symbols by underlying
    const groupedData: GroupedData[] = [];
    const processedUnderlyings = new Set<string>();

    symbols.forEach(symbol => {
        const underlying = extractUnderlying(symbol);

        if (processedUnderlyings.has(underlying)) {
            return;
        }

        processedUnderlyings.add(underlying);

        const relatedSymbols = symbols.filter(s => extractUnderlying(s) === underlying);
        const stockSymbol = relatedSymbols.find(s => !isOption(s)) || null;
        const optionSymbols = relatedSymbols.filter(s => isOption(s));

        const optionsWithGreeks = optionSymbols
            .map(sym => {
                const greeks = data[sym];
                const position = positionMap.get(sym);
                if (!greeks || !position) return null;
                return {
                    symbol: sym,
                    greeks,
                    qty: position.qty
                };
            })
            .filter(opt => opt !== null) as Array<{ symbol: string; greeks: GreeksData; qty: number }>;

        const aggregatedGreeks = aggregateGreeks(optionsWithGreeks);

        groupedData.push({
            underlying,
            stockSymbol,
            stockGreeks: stockSymbol ? data[stockSymbol] : null,
            options: optionsWithGreeks,
            aggregatedGreeks
        });
    });

    groupedData.sort((a, b) => a.underlying.localeCompare(b.underlying));

    const toggleExpand = (underlying: string) => {
        const newExpanded = new Set(expandedUnderlyings);
        if (newExpanded.has(underlying)) {
            newExpanded.delete(underlying);
        } else {
            newExpanded.add(underlying);
        }
        setExpandedUnderlyings(newExpanded);
    };

    return (
        <div className="overflow-x-auto">
            <table className="w-full min-w-[800px] text-sm text-left">
                <thead className="text-xs text-gray-500 dark:text-gray-400 uppercase">
                    <tr>
                        <th className="py-2 pr-2">Symbol</th>
                        <th className="py-2 pr-2">Delta</th>
                        <th className="py-2 pr-2">Gamma</th>
                        <th className="py-2 pr-2">Theta</th>
                        <th className="py-2 pr-2">Vega</th>
                        <th className="py-2 pr-2">Rho</th>
                        <th className="py-2 pr-2">IV</th>
                    </tr>
                </thead>
                <tbody>
                    {groupedData.map((group, idx) => {
                        const isExpanded = expandedUnderlyings.has(group.underlying);
                        const hasOptions = group.options.length > 0;

                        return (
                            <React.Fragment key={idx}>
                                {/* Main row - Stock with aggregated Greeks */}
                                <tr className="border-b dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                                    <td className="py-3 pr-2 font-medium text-[#111418] dark:text-white">
                                        <div className="flex items-center gap-2">
                                            {hasOptions && (
                                                <button
                                                    onClick={() => toggleExpand(group.underlying)}
                                                    className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                                                >
                                                    <span className="material-symbols-outlined text-base">
                                                        {isExpanded ? 'remove' : 'add'}
                                                    </span>
                                                </button>
                                            )}
                                            <span>{group.underlying}</span>
                                            {hasOptions && (
                                                <span className="text-xs text-gray-400">
                                                    ({group.options.length} options)
                                                </span>
                                            )}
                                        </div>
                                    </td>
                                    {hasOptions && group.aggregatedGreeks ? (
                                        <>
                                            <td className="py-3 pr-2 text-gray-600 dark:text-gray-300 font-semibold">
                                                <div className="flex flex-col">
                                                    <span className="text-sm">{formatDollar(group.aggregatedGreeks.dollarAmounts.delta)}</span>
                                                    <span className="text-xs text-gray-400">({group.aggregatedGreeks.greeks.delta.toFixed(4)})</span>
                                                </div>
                                            </td>
                                            <td className="py-3 pr-2 text-gray-600 dark:text-gray-300 font-semibold">
                                                <div className="flex flex-col">
                                                    <span className="text-sm">{formatDollar(group.aggregatedGreeks.dollarAmounts.gamma)}</span>
                                                    <span className="text-xs text-gray-400">({group.aggregatedGreeks.greeks.gamma.toFixed(4)})</span>
                                                </div>
                                            </td>
                                            <td className="py-3 pr-2 text-gray-600 dark:text-gray-300 font-semibold">
                                                <div className="flex flex-col">
                                                    <span className="text-sm">{formatDollar(group.aggregatedGreeks.dollarAmounts.theta)}</span>
                                                    <span className="text-xs text-gray-400">({group.aggregatedGreeks.greeks.theta.toFixed(4)})</span>
                                                </div>
                                            </td>
                                            <td className="py-3 pr-2 text-gray-600 dark:text-gray-300 font-semibold">
                                                <div className="flex flex-col">
                                                    <span className="text-sm">{formatDollar(group.aggregatedGreeks.dollarAmounts.vega)}</span>
                                                    <span className="text-xs text-gray-400">({group.aggregatedGreeks.greeks.vega.toFixed(4)})</span>
                                                </div>
                                            </td>
                                            <td className="py-3 pr-2 text-gray-600 dark:text-gray-300 font-semibold">
                                                <span className="text-sm">{group.aggregatedGreeks.greeks.rho.toFixed(4)}</span>
                                            </td>
                                            <td className="py-3 pr-2 text-gray-600 dark:text-gray-300 font-semibold">
                                                <span className="text-sm">{(group.aggregatedGreeks.greeks.iv * 100).toFixed(2)}%</span>
                                            </td>
                                        </>
                                    ) : (
                                        <td colSpan={6} className="py-3 pr-2 text-gray-400 italic">
                                            No Data / Stock
                                        </td>
                                    )}
                                </tr>

                                {/* Expanded rows - Individual options */}
                                {isExpanded && hasOptions && group.options.map((option, optIdx) => {
                                    const sign = option.qty >= 0 ? 1 : -1;
                                    return (
                                        <tr
                                            key={`${idx}-${optIdx}`}
                                            className="border-b dark:border-gray-800 bg-gray-50 dark:bg-gray-800/30 hover:bg-gray-100 dark:hover:bg-gray-800/50 transition-colors"
                                        >
                                            <td className="py-2 pr-2 pl-8 text-sm text-gray-600 dark:text-gray-400">
                                                <div className="flex items-center gap-2">
                                                    <span>{option.symbol}</span>
                                                    <span className={`text-xs ${option.qty >= 0 ? 'text-green-600 dark:text-green-500' : 'text-red-600 dark:text-red-500'}`}>
                                                        {option.qty >= 0 ? 'LONG' : 'SHORT'} {Math.abs(option.qty)}
                                                    </span>
                                                </div>
                                            </td>
                                            <td className="py-2 pr-2 text-sm text-gray-600 dark:text-gray-400">
                                                <div className="flex flex-col">
                                                    <span>{formatDollar(sign * calculateDollarAmount(option.greeks.delta, option.qty))}</span>
                                                    <span className="text-xs text-gray-500">({option.greeks.delta.toFixed(4)})</span>
                                                </div>
                                            </td>
                                            <td className="py-2 pr-2 text-sm text-gray-600 dark:text-gray-400">
                                                <div className="flex flex-col">
                                                    <span>{formatDollar(sign * calculateDollarAmount(option.greeks.gamma, option.qty))}</span>
                                                    <span className="text-xs text-gray-500">({option.greeks.gamma.toFixed(4)})</span>
                                                </div>
                                            </td>
                                            <td className="py-2 pr-2 text-sm text-gray-600 dark:text-gray-400">
                                                <div className="flex flex-col">
                                                    <span>{formatDollar(sign * calculateDollarAmount(option.greeks.theta, option.qty))}</span>
                                                    <span className="text-xs text-gray-500">({option.greeks.theta.toFixed(4)})</span>
                                                </div>
                                            </td>
                                            <td className="py-2 pr-2 text-sm text-gray-600 dark:text-gray-400">
                                                <div className="flex flex-col">
                                                    <span>{formatDollar(sign * calculateDollarAmount(option.greeks.vega, option.qty))}</span>
                                                    <span className="text-xs text-gray-500">({option.greeks.vega.toFixed(4)})</span>
                                                </div>
                                            </td>
                                            <td className="py-2 pr-2 text-sm text-gray-600 dark:text-gray-400">
                                                {option.greeks.rho.toFixed(4)}
                                            </td>
                                            <td className="py-2 pr-2 text-sm text-gray-600 dark:text-gray-400">
                                                {(option.greeks.iv * 100).toFixed(2)}%
                                            </td>
                                        </tr>
                                    );
                                })}
                            </React.Fragment>
                        );
                    })}
                    {symbols.length === 0 && (
                        <tr>
                            <td colSpan={7} className="py-4 text-center text-gray-500">No positions found.</td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
};
