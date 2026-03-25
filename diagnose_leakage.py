import sqlite3

conn = sqlite3.connect('ai_research_desk.sqlite3')
conn.row_factory = sqlite3.Row

print('=== SOURCE DISTRIBUTION ===')
rows = conn.execute('SELECT source, COUNT(*) as cnt FROM training_examples GROUP BY source ORDER BY cnt DESC').fetchall()
for r in rows:
    print(f'  {r["source"]:25s} {r["cnt"]}')

print()
print('=== LEAKAGE TEST SUBSET ===')
rows = conn.execute(
    "SELECT source, COUNT(*) as cnt FROM training_examples "
    "WHERE source IN ('blinded_win', 'blinded_loss', 'outcome_win', 'outcome_loss') "
    "GROUP BY source"
).fetchall()
for r in rows:
    print(f'  {dict(r)}')

print()
print('=== SAMPLE WIN OUTPUT (first 500 chars) ===')
row = conn.execute(
    "SELECT ticker, output_text FROM training_examples WHERE source = 'blinded_win' LIMIT 1"
).fetchone()
if row:
    print(f'  Ticker: {row["ticker"]}')
    print(row["output_text"][:500])

print()
print('=== SAMPLE LOSS OUTPUT (first 500 chars) ===')
row = conn.execute(
    "SELECT ticker, output_text FROM training_examples WHERE source = 'blinded_loss' LIMIT 1"
).fetchone()
if row:
    print(f'  Ticker: {row["ticker"]}')
    print(row["output_text"][:500])

print()
print('=== WIN/LOSS BALANCE ===')
wins = conn.execute(
    "SELECT COUNT(*) FROM training_examples WHERE source IN ('blinded_win', 'outcome_win')"
).fetchone()[0]
losses = conn.execute(
    "SELECT COUNT(*) FROM training_examples WHERE source IN ('blinded_loss', 'outcome_loss')"
).fetchone()[0]
print(f'  Wins: {wins}, Losses: {losses}, Ratio: {wins/(wins+losses)*100:.1f}% win')

print()
print('=== TICKER DISTRIBUTION IN LEAKAGE SUBSET (top 10) ===')
rows = conn.execute(
    "SELECT ticker, source, COUNT(*) as cnt FROM training_examples "
    "WHERE source IN ('blinded_win', 'blinded_loss', 'outcome_win', 'outcome_loss') "
    "GROUP BY ticker, source ORDER BY ticker"
).fetchall()
ticker_data = {}
for r in rows:
    t = r["ticker"]
    if t not in ticker_data:
        ticker_data[t] = {"win": 0, "loss": 0}
    if "win" in r["source"]:
        ticker_data[t]["win"] = r["cnt"]
    else:
        ticker_data[t]["loss"] = r["cnt"]

# Show tickers with most skewed win/loss ratios
for t, d in sorted(ticker_data.items(), key=lambda x: abs(x[1]["win"] - x[1]["loss"]), reverse=True)[:15]:
    total = d["win"] + d["loss"]
    wr = d["win"] / total * 100 if total > 0 else 0
    print(f'  {t:6s}  wins={d["win"]:2d}  losses={d["loss"]:2d}  total={total:2d}  WR={wr:.0f}%')
