import React, { useCallback, useEffect, useState } from 'react';


import { API_BASE_URL, apiFetch } from '../api';
type Account = 'paper' | 'live';
type Side = 'BUY' | 'SELL';
type OrderType = 'MKT' | 'LMT' | 'STP' | 'STP LMT';

interface TradeTicketProps {
    isOpen: boolean;
    onClose: () => void;
    secType: 'stock' | 'option';
    symbol: string;        // ticker (stock) or OCC symbol (option)
    displayName: string;   // human label shown in the ticket
    referencePrice?: number;
    initialSide?: Side;
    onSubmitted?: () => void;
}

const ORDER_TYPES: { value: OrderType; label: string }[] = [
    { value: 'MKT', label: 'Market' },
    { value: 'LMT', label: 'Limit' },
    { value: 'STP', label: 'Stop' },
    { value: 'STP LMT', label: 'Stop Limit' },
];

export const TradeTicket: React.FC<TradeTicketProps> = ({
    isOpen, onClose, secType, symbol, displayName, referencePrice, initialSide = 'BUY', onSubmitted,
}) => {
    const [account, setAccount] = useState<Account>('paper');
    const [side, setSide] = useState<Side>(initialSide);
    const [orderType, setOrderType] = useState<OrderType>('MKT');
    const [quantity, setQuantity] = useState<number>(1);
    const [limitPrice, setLimitPrice] = useState<string>('');
    const [stopPrice, setStopPrice] = useState<string>('');
    const [heldQty, setHeldQty] = useState<number>(0);
    const [step, setStep] = useState<'form' | 'confirm' | 'result'>('form');
    const [submitting, setSubmitting] = useState(false);
    const [result, setResult] = useState<any | null>(null);
    const [error, setError] = useState<string | null>(null);

    const multiplier = secType === 'option' ? 100 : 1;

    // Reset + seed defaults whenever the ticket opens for a (new) instrument
    useEffect(() => {
        if (!isOpen) return;
        setSide(initialSide);
        setOrderType('MKT');
        setQuantity(1);
        setLimitPrice(referencePrice ? referencePrice.toFixed(2) : '');
        setStopPrice('');
        setStep('form');
        setResult(null);
        setError(null);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen, symbol, secType]);

    // Fetch currently-held quantity (drives whether SELL is allowed)
    const refreshHeldQty = useCallback(async () => {
        try {
            const url = `${API_BASE_URL}/api/ibkr/position/${encodeURIComponent(symbol)}?sec_type=${secType}&account=${account}`;
            const r = await apiFetch(url);
            if (r.ok) {
                const d = await r.json();
                setHeldQty(d.quantity || 0);
            } else {
                setHeldQty(0);
            }
        } catch {
            setHeldQty(0);
        }
    }, [symbol, secType, account]);

    useEffect(() => {
        if (isOpen) refreshHeldQty();
    }, [isOpen, refreshHeldQty]);

    const canSell = heldQty > 0;
    // If we can't sell but SELL is selected, snap back to BUY
    useEffect(() => {
        if (side === 'SELL' && !canSell) setSide('BUY');
    }, [canSell, side]);

    if (!isOpen) return null;

    const needsLimit = orderType === 'LMT' || orderType === 'STP LMT';
    const needsStop = orderType === 'STP' || orderType === 'STP LMT';

    const estPrice = needsLimit
        ? parseFloat(limitPrice) || 0
        : (referencePrice || 0);
    const estCost = estPrice * quantity * multiplier;

    const validate = (): string | null => {
        if (!quantity || quantity <= 0) return 'Quantity must be greater than 0';
        if (side === 'SELL' && quantity > heldQty)
            return `You only hold ${heldQty}; cannot sell ${quantity}`;
        if (needsLimit && !(parseFloat(limitPrice) > 0)) return 'Enter a valid limit price';
        if (needsStop && !(parseFloat(stopPrice) > 0)) return 'Enter a valid stop price';
        return null;
    };

    const goConfirm = () => {
        const v = validate();
        if (v) { setError(v); return; }
        setError(null);
        setStep('confirm');
    };

    const submit = async () => {
        setSubmitting(true);
        setError(null);
        try {
            const body = {
                account, secType, symbol, action: side, quantity, orderType,
                limitPrice: needsLimit ? parseFloat(limitPrice) : null,
                stopPrice: needsStop ? parseFloat(stopPrice) : null,
            };
            const r = await apiFetch(`${API_BASE_URL}/api/ibkr/order`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'Order failed');
            setResult(d);
            setStep('result');
            onSubmitted?.();
        } catch (e: any) {
            setError(e.message || 'Order failed');
            setStep('form');
        } finally {
            setSubmitting(false);
        }
    };

    const isLive = account === 'live';

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
            onClick={onClose}
        >
            <div
                className="w-full max-w-md bg-white dark:bg-gray-900 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-800 overflow-hidden"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-800">
                    <div>
                        <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                            {secType === 'option' ? 'Option' : 'Stock'}
                        </p>
                        <h3 className="text-lg font-bold text-[#111418] dark:text-white">{displayName}</h3>
                    </div>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                        <span className="material-symbols-outlined">close</span>
                    </button>
                </div>

                {step === 'form' && (
                    <div className="p-5 flex flex-col gap-4">
                        {/* Account toggle */}
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-gray-500 dark:text-gray-400">Account</span>
                            <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg">
                                <button
                                    onClick={() => setAccount('paper')}
                                    className={`px-3 py-1 rounded text-sm font-medium ${account === 'paper' ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500'}`}
                                >Paper</button>
                                <button
                                    onClick={() => setAccount('live')}
                                    className={`px-3 py-1 rounded text-sm font-medium ${account === 'live' ? 'bg-white dark:bg-gray-700 text-red-600 dark:text-red-400 shadow-sm' : 'text-gray-500'}`}
                                >Live</button>
                            </div>
                        </div>
                        {isLive && (
                            <div className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-md px-3 py-2">
                                ⚠ Live account — orders use real money.
                            </div>
                        )}

                        {/* Buy / Sell toggle */}
                        <div className="grid grid-cols-2 gap-2">
                            <button
                                onClick={() => setSide('BUY')}
                                className={`py-2 rounded-lg font-bold text-sm ${side === 'BUY' ? 'bg-green-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300'}`}
                            >Buy</button>
                            <button
                                onClick={() => canSell && setSide('SELL')}
                                disabled={!canSell}
                                title={canSell ? '' : 'No position to sell'}
                                className={`py-2 rounded-lg font-bold text-sm ${side === 'SELL' ? 'bg-red-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300'} ${!canSell ? 'opacity-40 cursor-not-allowed' : ''}`}
                            >Sell</button>
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400 -mt-2">
                            Position held: <span className="font-medium">{heldQty}</span>
                            {secType === 'option' ? ' contract(s)' : ' share(s)'}
                        </p>

                        {/* Order type */}
                        <label className="flex flex-col gap-1">
                            <span className="text-sm text-gray-500 dark:text-gray-400">Order Type</span>
                            <select
                                value={orderType}
                                onChange={(e) => setOrderType(e.target.value as OrderType)}
                                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-[#111418] dark:text-white"
                            >
                                {ORDER_TYPES.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                            </select>
                        </label>

                        {/* Quantity */}
                        <label className="flex flex-col gap-1">
                            <span className="text-sm text-gray-500 dark:text-gray-400">
                                Quantity {secType === 'option' ? '(contracts ×100)' : '(shares)'}
                            </span>
                            <input
                                type="number" min={1} step={1} value={quantity}
                                onChange={(e) => setQuantity(Math.max(0, Number(e.target.value)))}
                                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-[#111418] dark:text-white"
                            />
                        </label>

                        {needsLimit && (
                            <label className="flex flex-col gap-1">
                                <span className="text-sm text-gray-500 dark:text-gray-400">Limit Price</span>
                                <input
                                    type="number" min={0} step="0.01" value={limitPrice}
                                    onChange={(e) => setLimitPrice(e.target.value)}
                                    className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-[#111418] dark:text-white"
                                />
                            </label>
                        )}
                        {needsStop && (
                            <label className="flex flex-col gap-1">
                                <span className="text-sm text-gray-500 dark:text-gray-400">Stop Price</span>
                                <input
                                    type="number" min={0} step="0.01" value={stopPrice}
                                    onChange={(e) => setStopPrice(e.target.value)}
                                    className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-[#111418] dark:text-white"
                                />
                            </label>
                        )}

                        {/* Estimated cost */}
                        <div className="flex items-center justify-between text-sm border-t border-gray-100 dark:border-gray-800 pt-3">
                            <span className="text-gray-500 dark:text-gray-400">
                                Est. {side === 'BUY' ? 'cost' : 'credit'}
                            </span>
                            <span className="font-semibold text-[#111418] dark:text-white">
                                {orderType === 'MKT' && !referencePrice ? '—' : `$${estCost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                            </span>
                        </div>

                        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

                        <button
                            onClick={goConfirm}
                            className={`mt-1 py-3 rounded-lg font-bold text-white ${side === 'BUY' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'}`}
                        >
                            Review {side === 'BUY' ? 'Buy' : 'Sell'} Order
                        </button>
                    </div>
                )}

                {step === 'confirm' && (
                    <div className="p-5 flex flex-col gap-4">
                        <div className={`rounded-lg px-4 py-3 text-sm ${isLive ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300' : 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'}`}>
                            {isLive ? '⚠ Confirm LIVE order (real money)' : 'Confirm paper order'}
                        </div>
                        <dl className="text-sm divide-y divide-gray-100 dark:divide-gray-800">
                            {[
                                ['Account', account.toUpperCase()],
                                ['Action', side],
                                ['Instrument', displayName],
                                ['Quantity', `${quantity}${secType === 'option' ? ' contract(s)' : ' share(s)'}`],
                                ['Order type', ORDER_TYPES.find(o => o.value === orderType)?.label],
                                ...(needsLimit ? [['Limit', `$${parseFloat(limitPrice).toFixed(2)}`]] : []),
                                ...(needsStop ? [['Stop', `$${parseFloat(stopPrice).toFixed(2)}`]] : []),
                                ['Est. ' + (side === 'BUY' ? 'cost' : 'credit'),
                                    orderType === 'MKT' && !referencePrice ? '—' : `$${estCost.toFixed(2)}`],
                            ].map(([k, v]) => (
                                <div key={k as string} className="flex justify-between py-2">
                                    <dt className="text-gray-500 dark:text-gray-400">{k}</dt>
                                    <dd className="font-medium text-[#111418] dark:text-white">{v}</dd>
                                </div>
                            ))}
                        </dl>
                        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
                        <div className="grid grid-cols-2 gap-2">
                            <button onClick={() => setStep('form')} className="py-3 rounded-lg font-bold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200">
                                Back
                            </button>
                            <button
                                onClick={submit}
                                disabled={submitting}
                                className={`py-3 rounded-lg font-bold text-white ${isLive ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'} disabled:opacity-50`}
                            >
                                {submitting ? 'Submitting…' : `Place ${side}`}
                            </button>
                        </div>
                    </div>
                )}

                {step === 'result' && result && (
                    <div className="p-5 flex flex-col gap-4 items-center text-center">
                        <span className="material-symbols-outlined text-5xl text-green-500">check_circle</span>
                        <div>
                            <p className="font-bold text-[#111418] dark:text-white">Order {result.status}</p>
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                                {result.action} {result.quantity} {displayName} · #{result.orderId} · {result.account.toUpperCase()}
                            </p>
                            {result.filled > 0 && (
                                <p className="text-sm text-gray-500 dark:text-gray-400">
                                    Filled {result.filled} @ ${result.avgFillPrice}
                                </p>
                            )}
                        </div>
                        <button onClick={onClose} className="w-full py-3 rounded-lg font-bold bg-blue-600 text-white hover:bg-blue-700">
                            Done
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};
