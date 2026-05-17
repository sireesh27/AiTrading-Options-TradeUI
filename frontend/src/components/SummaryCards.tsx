import React from 'react';

interface SummaryCardsProps {
    totalValue: number;
    totalDayPL: number;
}

export const SummaryCards: React.FC<SummaryCardsProps> = ({ totalValue, totalDayPL }) => {
    const plPercent = totalValue !== 0 ? (totalDayPL / (totalValue - totalDayPL)) * 100 : 0;
    const isPositive = totalDayPL >= 0;

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
            <div className="flex flex-col gap-2 rounded-xl p-6 bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800">
                <p className="text-gray-600 dark:text-gray-400 text-base font-medium leading-normal">Total Portfolio Value</p>
                <p className="text-[#111418] dark:text-white tracking-tight text-3xl sm:text-4xl font-bold leading-tight">
                    ${totalValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
            </div>
            <div className="flex flex-col gap-2 rounded-xl p-6 bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800">
                <p className="text-gray-600 dark:text-gray-400 text-base font-medium leading-normal">Total Day's P/L</p>
                <div className="flex items-center gap-3">
                    <p className="text-[#111418] dark:text-white tracking-tight text-3xl sm:text-4xl font-bold leading-tight">
                        ${Math.abs(totalDayPL).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </p>
                    <p className={`text-lg font-medium leading-normal ${isPositive ? 'text-green-600 dark:text-green-500' : 'text-red-600 dark:text-red-500'}`}>
                        {isPositive ? '+' : '-'}{Math.abs(plPercent).toFixed(2)}%
                    </p>
                </div>
            </div>
        </div>
    );
};
