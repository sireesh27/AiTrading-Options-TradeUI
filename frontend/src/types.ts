export interface Position {
    symbol: string;
    qty: number;
    avgPrice: number;
    currentPrice: number;
    value: number;
    pl: number;
    plPercent: number;
    source: string;
    // Optional fields from HTML mockup
    news?: string;
    ta?: string;
}

export interface BrokerData {
    totalValue: number;
    equity: number;
    buyingPower: number;
    dayPL: number;
    dayTrades: string;
    positions: Position[];
    isConnected: boolean;
}

export interface DashboardData {
    tastytrade: BrokerData;
    alpaca_live: BrokerData;
    alpaca_paper: BrokerData;
    ibkr_live: BrokerData;
    ibkr_paper: BrokerData;
}
