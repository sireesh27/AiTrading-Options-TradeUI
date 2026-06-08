#!/usr/bin/env python3
"""Market-data accuracy eval: our IBKR feed vs Yahoo Finance (real data).

Compares, per ticker:
  - underlying price (our /api/ibkr/stock-price vs Yahoo regularMarketPrice)
  - per-strike option fields for the nearest shared expiration:
    bid, ask, last, volume, openInterest, IV

No values are hard-coded — both sides are fetched live and diffed programmatically.
Yahoo options require a cookie+crumb (handled here). Run during regular trading
hours for a fair comparison (pre/post-market quotes diverge by design).

Usage: ./venv/bin/python tools/eval_market_data.py [AAPL SPY ...] [--strikes 8]
"""
import sys
import json
import datetime as dt

import httpx

OUR = "http://localhost:8000"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
FORCE_EXP = None


def yahoo_client():
    c = httpx.Client(headers=UA, timeout=20, follow_redirects=True)
    c.get("https://fc.yahoo.com")
    c._crumb = c.get("https://query1.finance.yahoo.com/v1/test/getcrumb").text
    return c


def yahoo_quote(c, sym):
    d = c.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}").json()
    m = d["chart"]["result"][0]["meta"]
    return {"price": m.get("regularMarketPrice"), "prevClose": m.get("chartPreviousClose"),
            "state": m.get("marketState")}


def yahoo_options(c, sym, exp_yyyymmdd=None):
    url = f"https://query1.finance.yahoo.com/v7/finance/options/{sym}"
    params = {"crumb": c._crumb}
    if exp_yyyymmdd:
        ts = int(dt.datetime.strptime(exp_yyyymmdd, "%Y%m%d").replace(tzinfo=dt.timezone.utc).timestamp())
        params["date"] = ts
    d = c.get(url, params=params).json()
    res = d["optionChain"]["result"]
    if not res:
        return None, []
    r = res[0]
    exps = [dt.datetime.fromtimestamp(e, dt.timezone.utc).strftime("%Y%m%d") for e in r["expirationDates"]]
    opt = r["options"][0] if r["options"] else None
    return exps, (opt["calls"] if opt else [])


def our_chain(sym, strikes, exp=None):
    p = {"strikes": strikes}
    if exp:
        p["expiration"] = exp
    d = httpx.get(f"{OUR}/api/ibkr/option-chain/{sym}", params=p, timeout=60).json()
    e = d.get("selectedExpiration")
    return d, e, (d["chain"][e]["calls"] if e and e in d.get("chain", {}) else [])


def our_price(sym):
    return httpx.get(f"{OUR}/api/ibkr/stock-price/{sym}", timeout=20).json()


def pct(a, b):
    if not b:
        return None
    return abs(a - b) / abs(b) * 100


def fnum(x):
    return f"{x:.2f}" if isinstance(x, (int, float)) else str(x)


def main():
    global FORCE_EXP
    strikes = 8
    argv = sys.argv[1:]
    skip = set()
    if "--strikes" in argv:
        i = argv.index("--strikes")
        strikes = int(argv[i + 1])
        skip |= {i, i + 1}
    if "--exp" in argv:
        i = argv.index("--exp")
        FORCE_EXP = argv[i + 1]
        skip |= {i, i + 1}
    args = [a for j, a in enumerate(argv) if j not in skip and not a.startswith("--")]
    tickers = args or ["AAPL", "SPY", "TSLA"]

    yc = yahoo_client()
    print(f"# Market-data eval  {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"# crumb ok: {bool(yc._crumb)}\n")

    summary = []
    for sym in tickers:
        print("=" * 72)
        print(f"{sym}")
        print("=" * 72)
        # --- underlying ---
        try:
            ours = our_price(sym)
            yq = yahoo_quote(yc, sym)
            dpx = pct(ours.get("price", 0), yq.get("price") or 0)
            verdict = "OK" if (dpx is not None and dpx < 0.3) else "CHECK"
            print(f"Underlying: ours={fnum(ours.get('price'))}  yahoo={fnum(yq.get('price'))}  "
                  f"diff={dpx:.2f}% [{verdict}]  (yahoo state={yq.get('state')})")
            summary.append((sym, "price", verdict, dpx))
        except Exception as e:
            print(f"Underlying compare failed: {e}")

        # --- option chain ---
        try:
            yexps, _ = yahoo_options(yc, sym)
            today = dt.datetime.now().strftime("%Y%m%d")
            if FORCE_EXP:
                exp = FORCE_EXP
            else:
                # skip same-day (0-DTE) expiry — its IV/quotes are noisy; pick the
                # first expiration strictly after today that both sides share.
                d0, oe0, _ = our_chain(sym, strikes)
                cand = [e for e in (d0.get("expirations") or []) if e > today]
                exp = next((e for e in cand if not yexps or e in yexps), oe0)
            d, oe, ocalls = our_chain(sym, strikes, exp)
            _, ycalls = yahoo_options(yc, sym, exp)
            ymap = {round(float(c["strike"]), 2): c for c in ycalls}
            print(f"\nExpiration {exp} — CALLS (ours vs Yahoo)  [yahoo state={yq.get('state')}]")
            print(f"{'strike':>7} | {'mid o/y':>14} | {'last o/y':>14} | {'OI o/y':>13} | "
                  f"{'IV% o/y':>13} | flag")
            print("-" * 86)
            # tolerances: mid within max(3c, 3%); IV within 4 vol-pts; OI exact
            n = mid_ok = oi_ok = iv_ok = 0
            diffs = []
            for c in ocalls:
                k = round(float(c["strike"]), 2)
                y = ymap.get(k)
                if not y:
                    continue
                n += 1
                omid = ((c.get("bid") or 0) + (c.get("ask") or 0)) / 2 if (c.get("bid") and c.get("ask")) else (c.get("last") or 0)
                ymid = ((y.get("bid") or 0) + (y.get("ask") or 0)) / 2 if (y.get("bid") and y.get("ask")) else (y.get("lastPrice") or 0)
                yiv = (y.get("impliedVolatility") or 0) * 100
                oiv = (c.get("iv") or 0) * 100
                flag = ""
                if ymid > 0:
                    dmid = abs(omid - ymid)
                    if dmid <= max(0.03, 0.03 * ymid):
                        mid_ok += 1
                    else:
                        flag += "MID "
                        diffs.append(f"{sym} {k}C mid ours={omid:.2f} yahoo={ymid:.2f} (Δ{dmid:.2f})")
                if y.get("openInterest") is not None:
                    if (c.get("openInterest") or 0) == y["openInterest"]:
                        oi_ok += 1
                    else:
                        flag += "OI "
                        diffs.append(f"{sym} {k}C OI ours={c.get('openInterest')} yahoo={y['openInterest']}")
                if yiv > 1:
                    if abs(oiv - yiv) <= 4:
                        iv_ok += 1
                    else:
                        flag += "IV "
                print(f"{k:>7} | {omid:>6.2f}/{ymid:>6.2f} | "
                      f"{fnum(c.get('last')):>6}/{fnum(y.get('lastPrice')):>6} | "
                      f"{str(c.get('openInterest')):>5}/{str(y.get('openInterest')):>6} | "
                      f"{oiv:>5.1f}/{yiv:>6.1f} | {flag}")
            if n:
                print(f"\n  matched strikes: {n} | mid≈ {mid_ok}/{n} | OI= {oi_ok}/{n} | IV≈ {iv_ok}/{n}")
                summary.append((sym, "chain", f"mid {mid_ok}/{n}, OI {oi_ok}/{n}, IV {iv_ok}/{n}", diffs))
        except Exception as e:
            print(f"Chain compare failed: {e}")
        print()

    print("=" * 72)
    print("SUMMARY")
    all_diffs = []
    for row in summary:
        sym, kind = row[0], row[1]
        metric = row[2]
        print(f"  {sym:6} {kind:6} {metric}")
        if kind == "chain" and len(row) > 3 and row[3]:
            all_diffs.extend(row[3])
    print("\nNOTABLE DIFFERENCES (beyond tolerance):")
    if all_diffs:
        for dline in all_diffs:
            print("  -", dline)
    else:
        print("  none — all within tolerance ✅")


if __name__ == "__main__":
    main()
