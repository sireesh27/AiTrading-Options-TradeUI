import React, { useState } from 'react';
import type { BrokerData } from '../types';
import { PositionsTable } from './PositionsTable';
import { MarketGreeksTable } from './MarketGreeksTable';
import { fetchGreeksBatch } from '../api';

interface BrokerSectionProps {
    title: string;
    id: string;
    data: BrokerData;
}

export const BrokerSection: React.FC<BrokerSectionProps> = ({ title, id, data }) => {
    const [isOpen, setIsOpen] = useState(true);
    const [activeTab, setActiveTab] = useState<'positions' | 'greeks'>('positions');
    const [greeksData, setGreeksData] = useState<Record<string, any> | null>(null);
    const [loadingGreeks, setLoadingGreeks] = useState(false);

    const toggleOpen = () => setIsOpen(!isOpen);

    const handleTabChange = async (tab: 'positions' | 'greeks') => {
        setActiveTab(tab);
        // Fetch if switching to greeks OR if retrying (tab is already greeks but no data)
        const shouldFetch = (tab === 'greeks' && data.positions.length > 0) && (!greeksData);

        if (shouldFetch) {
            setLoadingGreeks(true);
            try {
                const symbols = data.positions.map(p => p.symbol);
                const result = await fetchGreeksBatch(symbols);
                setGreeksData(result);
            } catch (error) {
                console.error("Failed to fetch greeks", error);
                setGreeksData(null); // Ensure it's null to show retry state
            } finally {
                setLoadingGreeks(false);
            }
        }
    };

    return (
        <div className="flex flex-col gap-6 rounded-xl p-4 sm:p-6 bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 group">
                    <span className="material-symbols-outlined text-gray-400 dark:text-gray-500 cursor-grab group-hover:text-gray-600 dark:group-hover:text-gray-300 transition-colors">drag_indicator</span>
                    <h2 className="text-[#111418] dark:text-white text-lg sm:text-xl font-bold leading-tight tracking-[-0.015em]">{title}</h2>
                    <div className={`w-3 h-3 rounded-full ${data.isConnected ? 'bg-green-500' : 'bg-red-500'}`} title={data.isConnected ? "Connected" : "Disconnected"}></div>
                </div>
                <button
                    className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                    onClick={toggleOpen}
                >
                    <span className="material-symbols-outlined">{isOpen ? 'expand_less' : 'expand_more'}</span>
                </button>
            </div>

            {isOpen && (
                <>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                        <div>
                            <p className="text-gray-500 dark:text-gray-400 mb-1">Total Balance</p>
                            <p className="font-semibold text-base text-[#111418] dark:text-white">${data.totalValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
                        </div>
                        <div>
                            <p className="text-gray-500 dark:text-gray-400 mb-1">Day's P/L</p>
                            <p className={`font-semibold text-base ${data.dayPL >= 0 ? 'text-green-600 dark:text-green-500' : 'text-red-600 dark:text-red-500'}`}>
                                {data.dayPL >= 0 ? '+' : '-'}${Math.abs(data.dayPL).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </p>
                        </div>
                        <div>
                            <p className="text-gray-500 dark:text-gray-400 mb-1">Equity</p>
                            <p className="font-semibold text-base text-[#111418] dark:text-white">${data.equity.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
                        </div>
                        <div className="col-span-2 lg:col-span-1 flex flex-row lg:flex-col justify-between items-start lg:items-stretch gap-2">
                            <div>
                                <p className="text-gray-500 dark:text-gray-400 mb-1">Buying Power</p>
                                <p className="font-semibold text-base text-[#111418] dark:text-white">${data.buyingPower.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <p className="text-gray-500 dark:text-gray-400">Include in total</p>
                                <label className="relative inline-flex cursor-pointer items-center">
                                    <input defaultChecked className="sr-only peer" type="checkbox" />
                                    <div className="peer h-6 w-11 rounded-full bg-gray-200 after:absolute after:start-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all after:content-[''] peer-checked:bg-primary peer-checked:after:translate-x-full peer-checked:after:border-white dark:border-gray-600 dark:bg-gray-700"></div>
                                </label>
                            </div>
                        </div>
                    </div>

                    <div id={`positions-${id}`}>
                        <div className="border-t border-gray-200 dark:border-gray-800 my-6"></div>

                        <div className="flex items-center gap-4 mb-4 border-b border-gray-200 dark:border-gray-800">
                            <button
                                className={`pb-2 text-sm font-bold border-b-2 transition-colors ${activeTab === 'positions' ? 'text-primary border-primary' : 'text-gray-500 border-transparent hover:text-gray-700 dark:hover:text-gray-300'}`}
                                onClick={() => handleTabChange('positions')}
                            >
                                Open Positions
                            </button>
                            <button
                                className={`pb-2 text-sm font-bold border-b-2 transition-colors ${activeTab === 'greeks' ? 'text-primary border-primary' : 'text-gray-500 border-transparent hover:text-gray-700 dark:hover:text-gray-300'}`}
                                onClick={() => handleTabChange('greeks')}
                            >
                                MarketGreeks
                            </button>
                        </div>

                        {activeTab === 'positions' ? (
                            <>
                                <PositionsTable positions={data.positions} />
                                <a className="text-primary text-sm font-bold text-center mt-4 block" href="#">View All</a>
                            </>
                        ) : (
                            <>
                                {data.positions.length === 0 ? (
                                    <div className="text-center py-4 text-gray-500">No open positions to display Greeks for.</div>
                                ) : (
                                    <>
                                        {loadingGreeks && <div className="text-center py-4 text-gray-500">Loading Greeks...</div>}
                                        {!loadingGreeks && greeksData && (
                                            <MarketGreeksTable
                                                data={greeksData}
                                                symbols={data.positions.map(p => p.symbol)}
                                                positions={data.positions}
                                            />
                                        )}
                                        {!loadingGreeks && !greeksData && (
                                            <div className="flex flex-col items-center justify-center py-4 gap-2">
                                                <p className="text-red-500">Failed to load Greeks.</p>
                                                <button
                                                    className="px-4 py-2 bg-primary text-white rounded-md text-sm font-bold hover:bg-blue-600 transition-colors"
                                                    onClick={() => handleTabChange('greeks')}
                                                >
                                                    Retry Loading
                                                </button>
                                            </div>
                                        )}
                                    </>
                                )}
                            </>
                        )}
                    </div>
                </>
            )}
        </div>
    );
};
