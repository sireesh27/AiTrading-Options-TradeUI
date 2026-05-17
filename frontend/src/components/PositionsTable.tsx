import React from 'react';
import type { Position } from '../types';

interface PositionsTableProps {
    positions: Position[];
}

export const PositionsTable: React.FC<PositionsTableProps> = ({ positions }) => {
    return (
        <div className="overflow-x-auto">
            <table className="w-full min-w-[600px] text-sm text-left">
                <thead className="text-xs text-gray-500 dark:text-gray-400 uppercase">
                    <tr>
                        <th className="py-2 pr-2">Symbol</th>
                        <th className="py-2 pr-2">Qty</th>
                        <th className="py-2 pr-2">Value</th>
                        <th className="py-2 pr-2">P/L</th>
                        <th className="py-2 pr-2">News</th>
                        <th className="py-2 pr-2">TA</th>
                        <th className="py-2">Link</th>
                    </tr>
                </thead>
                <tbody>
                    {positions.map((pos, idx) => (
                        <tr key={idx} className="border-b dark:border-gray-800">
                            <td className="py-3 pr-2 font-medium text-[#111418] dark:text-white">{pos.symbol}</td>
                            <td className="py-3 pr-2 text-gray-600 dark:text-gray-300">{pos.qty}</td>
                            <td className="py-3 pr-2 text-gray-600 dark:text-gray-300">${pos.value.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                            <td className={`py-3 pr-2 ${pos.pl >= 0 ? 'text-green-600 dark:text-green-500' : 'text-red-600 dark:text-red-500'}`}>
                                {pos.pl >= 0 ? '+' : '-'}${Math.abs(pos.pl).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </td>
                            <td className="py-3 pr-2"><div className={`w-3 h-3 rounded-full ${pos.pl >= 0 ? 'bg-green-500' : 'bg-red-500'}`}></div></td>
                            <td className="py-3 pr-2"><div className={`w-3 h-3 rounded-full ${pos.pl >= 0 ? 'bg-blue-500' : 'bg-red-500'}`}></div></td>
                            <td className="py-3"><a className="text-primary hover:underline" href="#">Details</a></td>
                        </tr>
                    ))}
                    {positions.length === 0 && (
                        <tr>
                            <td colSpan={7} className="py-4 text-center text-gray-500">No positions found.</td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
};
