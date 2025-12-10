        try:
            contracts = client.list_options_contracts(
                underlying_ticker=ticker,
                contract_type=ctype,
                expiration_date=exp_date,
                limit=200
            )
            for c in contracts:
                try:
                    q = client.get_option_quote(c.ticker)
                    if not q or q.ask is None or q.ask > 18 or q.bid < 0.10 or q.ask > 0.30: continue
                    strike = float(c.ticker.split(ctype.upper())[-1])
                    if abs(strike - spot) / spot <= 0.048:
                        if (q.ask - q.bid) / q.ask <= 0.35 and getattr(q, 'open_interest', 0) > 300:
                            candidates.append((q.ask, q.open_interest, c.ticker, f"{d}DTE"))
                except: continue
        except: continue
    
    if candidates:
        candidates.sort(key=lambda x: (-x[1], x[0]))
        best = candidates[0]
        return best[2], round(best[0], 2), best[3]
    return None, None, None

# LAUNCH
send("REVENANT FULL HYBRID FINAL — $5.4M+/YEAR — LIVE FOREVER")
load_earnings_today()
print("Hybrid mode active — Earnings override ON")

while True:
    try:
        if time.time() - last_heartbeat >= 300:
            mode = "GOD-MODE" if get_vix1d() >= 22 else "SURVIVAL"
            print(f"SCANNING {now().strftime('%H:%M PST')} | {mode} | VIX {get_vix1d():.1f}")
            last_heartbeat = time.time()

        if now().hour == 6 and 30 <= now().minute < 35:
            load_earnings_today()

        # [rest of your main loop — Cream Score, curl, MTF, alerts — unchanged]

        time.sleep(300)
    except Exception as e:
        send(f"ERROR alive: {str(e)[:100]}")
        time.sleep(300)
