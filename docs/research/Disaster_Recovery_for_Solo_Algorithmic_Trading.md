# Disaster recovery for a solo-operated algorithmic trading system

**Your bracket orders are your lifeline — but only if they're GTC.** The single most critical finding from this research is that Alpaca bracket order child legs (stop-loss and take-profit) inherit the parent order's time-in-force. If you submit bracket orders with `time_in_force=DAY`, your protective stops **expire at 4:00 PM ET** and won't carry over. With `time_in_force=GTC`, they persist on Alpaca's servers for up to 90 days regardless of whether your machine is alive. This means a full machine death during market hours with GTC brackets leaves your positions protected — the worst case is missed entry signals, not catastrophic losses. With a disciplined **$300–500 infrastructure investment**, you can build layered resilience covering power, internet, hardware, and cloud failover that reduces your recovery time objective to under 5 minutes for most scenarios.

---

## 1. Alpaca bracket orders survive client death — with a critical caveat

Alpaca bracket orders execute entirely server-side. Once submitted, the take-profit (limit order) and stop-loss (stop or stop-limit order) live on Alpaca's infrastructure and execute regardless of your connection status. When one leg fills, Alpaca cancels the other — all without any client involvement. Your machine can be powered off, disconnected from the internet, or completely destroyed, and these orders continue working.

**The critical caveat is time-in-force.** Bracket order child legs inherit the parent's TIF setting. With `TimeInForce.DAY`, protective stops expire at market close and do not carry over to the next trading day. **Always use `TimeInForce.GTC`** for bracket orders on an unattended system. GTC orders remain active for **90 days** before Alpaca auto-cancels them (at 4:15 PM ET on the expiration date). Alpaca's own documentation warns that conditional orders are "Not Held" orders executed on a best-efforts basis, and in extremely volatile conditions, both bracket legs could theoretically fill before cancellation occurs — though this is rare.

**Risk exposure with GTC bracket orders during full machine death:**

| Scenario | Risk level | Explanation |
|---|---|---|
| Machine dies at 9:31 AM, restored at 4:00 PM | **Low** | All stops and take-profits execute normally server-side |
| Machine dies for multiple days | **Low** | GTC brackets persist up to 90 days |
| Flash crash / trading halt | **Medium** | Stop-loss may execute at significantly worse price (gap risk) |
| New entry signals missed | **Opportunity cost only** | No new positions opened, but no losses either |
| Dynamic stop adjustment needed | **Medium** | Cannot trail stops or tighten brackets while offline |

**Emergency management from a phone**: The Alpaca Dashboard mobile app allows you to view all positions and orders, cancel all open orders, liquidate all positions, and enable/disable API access (a kill switch for the algorithm). These are accessible from any browser at app.alpaca.markets. You can also implement a Telegram bot `/kill` command that calls `TradingClient.close_all_positions(cancel_orders=True)` for one-tap emergency liquidation.

---

## 2. A $200 UPS buys 15 minutes of graceful shutdown time

The total system power draw for a trading PC with an RTX 3060 running inference (not gaming) sits at **300–350W sustained** at the wall (GPU ~130W inference, CPU ~50–65W, peripherals ~70–100W). Peak bursts during heavy GPU use may hit 400–450W. A **1500VA pure sine wave UPS** is the right choice, providing **12–18 minutes of runtime** at typical trading loads — enough for graceful shutdown with margin.

**Top recommendation: CyberPower CP1500PFCLCD (~$200–260)**. This delivers 1500VA/1000W pure sine wave output with USB HID connectivity, LCD display, and AVR. The pure sine wave output is essential — simulated sine wave UPS units can cause Active PFC power supplies (all modern 80+ certified PSUs) to shut down instantly on battery switchover, defeating the entire purpose. The APC BR1500MS2 (~$220–260) is an equivalent alternative.

**Graceful shutdown sequence** should be triggered by CyberPower PowerPanel software (free) when battery drops below 30% or after 120 seconds on battery:

1. Send Telegram alert: "⚡ POWER FAILURE: Initiating shutdown"
2. Stop Python trading processes gracefully (send SIGTERM, wait 10 seconds)
3. Checkpoint SQLite database: `PRAGMA wal_checkpoint(TRUNCATE)` and run backup
4. Write shutdown marker file for recovery detection
5. Initiate `Stop-Computer -Force`

**BIOS auto-power-on** must be enabled: navigate to your motherboard's BIOS (Del/F2 during POST), find "Restore on AC Power Loss" (ASUS: Advanced → APM Configuration; MSI: Settings → Advanced → Power Management; Gigabyte: Power Management → AC Back Function) and set to **Power On** — not "Last State," which will leave the PC off after a UPS-initiated shutdown. Test this by unplugging the UPS from the wall, waiting 30 seconds, and plugging back in.

**Recovery time objective from power restoration to fully operational: ~2.5–5 minutes.** This breaks down to BIOS POST (15–30s) → Windows boot from SSD (20–40s) → auto-login via Sysinternals Autologon (3–5s) → network connectivity (5–15s) → NSSM services start in dependency order (20–40s) → Ollama model loads into VRAM (5–15s) → trading bot initializes and checks positions (10–30s). To minimize this, enable Fast Boot in BIOS, set first boot device to NVMe SSD only, and set `OLLAMA_KEEP_ALIVE=-1` so the model stays loaded permanently.

---

## 3. Run all 12 collectors and the trading bot as Windows services via NSSM

**NSSM (Non-Sucking Service Manager)** is the right tool for converting Python scripts into proper Windows services that auto-start on boot, auto-restart on crash, and run before user login. Install via `choco install nssm` or download the single executable from nssm.cc.

```cmd
nssm install TradingBot "C:\TradingSystem\venv\Scripts\python.exe" "C:\TradingSystem\main.py"
nssm set TradingBot AppDirectory "C:\TradingSystem"
nssm set TradingBot Start SERVICE_AUTO_START
nssm set TradingBot DependOnService OllamaService
nssm set TradingBot AppRestartDelay 30000
```

**Service dependency chain** ensures correct startup order: Network → OllamaService → TradingBot → DataCollector1 through DataCollector12. NSSM's `DependOnService` setting makes Windows enforce this ordering. For Task Scheduler overnight tasks, enable **"Run task as soon as possible after a scheduled start is missed"** (PowerShell: `-StartWhenAvailable` flag) so missed collections execute immediately after reboot.

Create a master `recovery_startup.ps1` script registered as a Scheduled Task triggered at startup that: waits for network (up to 60 seconds), sends Telegram recovery notification, checks SQLite integrity via `PRAGMA integrity_check`, waits for Ollama API to respond at `http://localhost:11434/api/tags`, pre-loads the Qwen3 model with a warm-up request, and sends a final "✅ System operational" notification.

---

## 4. Ollama falls back to CPU automatically, but expect 10× slower inference

**Ollama automatically falls back to CPU** when no compatible GPU is detected. It selects the best available backend library (cpu_avx2, cpu_avx, or cpu) at startup. If the GPU fails mid-session, Ollama needs a **restart** to re-detect hardware — it caches GPU enumeration at launch but doesn't re-scan dynamically. The watchdog script (below) handles this automatically.

**Performance comparison for Qwen3 8B Q4_K_M:**

| Platform | Tokens/sec | Time for 500-token analysis | Viability |
|---|---|---|---|
| RTX 3060 12GB (GPU) | **~40–45 t/s** | ~12 seconds | Excellent |
| Modern desktop CPU (Ryzen 7 / i7-12th gen) | **~3–5 t/s** | ~100–170 seconds | Emergency-only |
| Budget cloud VM (2 vCPU) | **~2–4 t/s** | ~125–250 seconds | Impractical |

CPU fallback is viable as an **emergency measure** for reduced-frequency trading. At 2–3 minutes per analysis, it works for position/swing trades but not for anything requiring rapid decisions. During CPU-only mode, simplify prompts and reduce output token limits. You can force CPU mode explicitly with `$env:CUDA_VISIBLE_DEVICES = "-1"` or `$env:OLLAMA_LLM_LIBRARY = "cpu_avx2"` before starting Ollama.

**VRAM leaks are a recurring known issue** across Ollama versions. GitHub issues document RAM growing from 1GB to 30–64GB over hours of continuous use, VRAM not being freed after model unload, and out-of-memory errors after stress testing. Mitigation requires a comprehensive watchdog:

```powershell
# Core watchdog loop (runs every 30 seconds)
# 1. Check Ollama health via GET http://localhost:11434/api/tags
# 2. Check VRAM via nvidia-smi --query-gpu=memory.used
# 3. If Ollama unresponsive for 2 consecutive checks → kill all ollama* processes → restart
# 4. If VRAM exceeds 11,500MB (of 12,288MB) → restart Ollama
# 5. If nvidia-smi fails entirely → GPU is dead, send critical alert
# 6. Check GPU temperature → alert if >85°C
```

Register this as a Windows Scheduled Task at startup running as SYSTEM. Also schedule a **daily preventive Ollama restart** (e.g., 4:30 AM ET) via Task Scheduler to reset any accumulated memory leaks before the trading day.

**RTX 3060 hardware reliability** is excellent — consumer GPU failure rates are **1–2% over 24 months** across major brands. Common warning signs include nvlddmkm.sys TDR errors in Windows Event Viewer, visual artifacts, and thermal throttling above 83°C. Monitor with `nvidia-smi --query-gpu=temperature.gpu,memory.used,power.draw --format=csv -l 10` logged to CSV. Current replacement cost is **$150–200 used, $250–350 new** with 1–3 day Amazon delivery. Consider keeping a spare if scaling to $25K+ capital.

---

## 5. A $60–100 cellular failover handles the 3–8 annual ISP outages that overlap with market hours

US residential internet averages **99–99.5% uptime**, translating to roughly **6–12 noticeable outages per year** with an average duration of 30 minutes to 4 hours. Given 252 trading days and 6.5-hour market windows, expect **3–8 outages overlapping market hours annually**.

With GTC bracket orders protecting all positions server-side, the actual risk from internet outages is low. Existing positions remain protected. The primary impact is missed entry signals (opportunity cost, not financial loss). The system can safely be offline for the **entire trading day** without catastrophic consequences.

**Budget-friendly cellular backup tiers:**

- **$0 — Phone USB tethering + Speedify Free**: Keep an old Android phone plugged into the PC via USB with tethering enabled. Speedify (free tier, 2GB/month) bonds your primary connection with the USB tether and provides near-instant sub-second failover. The 2GB free allowance easily covers trading API calls during emergencies.

- **$85–100 one-time + $5–12/month — TP-Link ER605 V2 + USB 4G dongle**: The ER605 ($60) is a dual-WAN router with automatic failover. Add a generic USB 4G LTE dongle ($25–40) with a Tello Mobile plan ($5/month for 1GB). Hardware-level failover works independently of the trading PC. Detection time is ~2 minutes.

- **$200–250 one-time — Peplink B One**: Enterprise-grade failover with SpeedFusion providing sub-second seamless switching. Overkill for most trading systems, but "set and forget" reliability. As one financial user noted: "Our small business engages in failure-is-not-an-option financial activities... this little router does that beautifully."

A trading system uses surprisingly little bandwidth — **100–300MB/day** during active trading (API calls, streaming quotes, Telegram alerts). In failover mode with just position monitoring, usage drops to **under 50MB/day**. A 1GB cellular plan provides weeks of backup capacity. Starlink ($349 equipment + $80–120/month) is overkill as a backup for this use case.

---

## 6. Windows updates are the silent killer of 24/7 trading systems

Windows automatic restarts during market hours represent a real and preventable risk. The defense requires layered configuration:

**Layer 1 — Active Hours (all editions):** Set active hours to 5:00 AM–11:00 PM ET (maximum 18-hour range) via Registry:
```powershell
Set-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' -Name 'SetActiveHours' -Value 1
Set-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' -Name 'ActiveHoursStart' -Value 5
Set-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' -Name 'ActiveHoursEnd' -Value 23
```

**Layer 2 — Block auto-restart with logged-on users:**
```powershell
New-Item -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -Force
Set-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -Name 'AuOptions' -Value 4
Set-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -Name 'NoAutoRebootWithLoggedOnUsers' -Value 1
```
Microsoft's documentation notes this policy "can result in no quality update reboots at all if users never log off" — which is exactly what you want for a 24/7 system.

**Layer 3 — Defer updates (Pro only):** Defer feature updates 180 days and quality updates 30 days via Group Policy or Registry. **Upgrading from Windows Home to Pro ($199.99) is strongly recommended** for a system trading real money. Pro provides Group Policy Editor access, Windows Update for Business controls, and update deferral capabilities that Home lacks entirely.

**Layer 4 — Scheduled service blocking:** A PowerShell script running every 30 minutes via Task Scheduler stops the Windows Update service (`wuauserv`, `bits`, `dosvc`) during weekday market hours and re-enables them on weekends. Note that Windows Update Medic Service (`WaaSMedicSvc`) may re-enable `wuauserv` on newer Windows versions, making the layered approach essential.

---

## 7. SQLite with WAL mode and synchronous=FULL survives power failures without data loss

SQLite in WAL (Write-Ahead Logging) mode with `PRAGMA synchronous=FULL` provides **full ACID durability** — no committed transactions are lost on power failure, and the database cannot become corrupted. With `synchronous=NORMAL`, the database stays intact but recently committed transactions in the WAL that weren't yet fsync'd may roll back. With `synchronous=OFF`, corruption is possible — **never use this for trading data**.

**Required PRAGMA configuration for every connection:**
```python
conn = sqlite3.connect('trading.db', timeout=10)
conn.execute("PRAGMA journal_mode=WAL")        # Set once, persists
conn.execute("PRAGMA synchronous=FULL")         # Full durability — set per connection
conn.execute("PRAGMA busy_timeout=5000")        # 5-second busy timeout
conn.execute("PRAGMA wal_autocheckpoint=1000")  # Checkpoint at ~4MB WAL size
conn.execute("PRAGMA cache_size=-32768")        # 32MB cache
```

WAL mode provides a key advantage for trading: **readers never block writers and writers never block readers**. Your monitoring dashboard can query the database while the trading engine writes without contention.

**Backup strategy** uses Python's `connection.backup()` API, which is safe to call during active writes and correctly handles WAL mode. Run backups every **15 minutes during market hours** and keep 24 hours of rotating backups (96 files). After market close, run `PRAGMA wal_checkpoint(TRUNCATE)` to reset the WAL file and `PRAGMA integrity_check` to verify database health. Never copy a WAL-mode SQLite file directly — use the backup API or `VACUUM INTO 'backup.db'`.

For point-in-time recovery, **Litestream** (open-source, free) is purpose-built for SQLite. It takes over the checkpoint process, continuously streams WAL pages to local or S3 storage, and can restore to any point in time within your retention window. It runs as a background process with negligible performance impact and requires zero code changes.

---

## 8. An $8.70/month cloud VM provides meaningful failover capability

A **Hetzner CPX22** in Ashburn, VA ($8.70/month) delivers 2 AMD EPYC vCPUs, 4GB RAM, and 80GB NVMe SSD — sufficient to run a reduced-capability Python trading system. Running Ollama with Qwen3 8B on this VM is impractical (too slow, insufficient RAM), but **Groq's free API tier** provides 14,400 requests/day and 500,000 tokens/day on Llama 3.1 8B at **840 tokens/second** — more than enough for emergency trade analysis at zero cost.

**The failover architecture:**

The home PC sends a heartbeat every 2 minutes to the cloud VM, including positions, orders, account equity, and system health metrics. The cloud VM runs a watchdog that detects staleness after 5 minutes (2.5 missed heartbeats). After 7 minutes of confirmed absence (with cross-verification via Alpaca API to check for recent orders), the cloud VM activates failover mode.

**The cloud failover instance skips** local LLM inference, model training, heavy data collection, and complex analysis. **It keeps** position monitoring via Alpaca API, bracket order verification, emergency liquidation capability, basic rule-based risk management, Groq API for lightweight AI decisions, and Telegram alerts.

**Split-brain prevention is non-negotiable.** The simplest reliable approach: prefix all order `client_order_id` values with the instance name (`HOME-{uuid}` vs `CLOUD-{uuid}`). Before placing any order, the active instance checks Alpaca for recent orders from the other instance. The cloud VM defaults to "always passive unless promoted," and when the home PC recovers, it enters standby mode and requires manual handoff — automatic handoff is too dangerous for a solo system.

**Database sync** uses `sqlite3_rsync` (built by the SQLite team, released 2025) over SSH every 5 minutes during market hours. It handles live databases correctly and only transfers changed pages, making it bandwidth-efficient.

| Component | Monthly cost |
|---|---|
| Hetzner CPX22 VM (always-on) | $8.70 |
| Groq API (free tier) | $0 |
| Healthchecks.io (free tier) | $0 |
| Telegram alerts | $0 |
| **Total** | **$8.70** |

---

## 9. Three-layer monitoring costs nothing and catches failures within 5 minutes

**Layer 1 — Internal heartbeat via Telegram**: The trading system sends a rich health report every 2 minutes to a Telegram bot, including CPU/RAM/VRAM usage, GPU temperature, open positions, unrealized P&L, last trade time, last scan time, Ollama status, and SQLite backup status. Implement two-way commands: `/status`, `/positions`, `/pnl`, `/kill` (emergency liquidate). The Telegram Bot API is completely free with generous rate limits (30 messages/second).

**Layer 2 — External dead man's switch via Healthchecks.io**: The system pings `https://hc-ping.com/YOUR-UUID` every 2 minutes. If Healthchecks.io doesn't receive a ping within the configured grace period (5 minutes), it fires alerts via Telegram, email, or webhook. This catches scenarios where the entire machine is dead and can't send Telegram alerts. The free tier provides 20 checks — more than enough.

**Layer 3 — Dashboard uptime via UptimeRobot**: Monitor your Render-deployed dashboard's HTTP endpoint from outside. If it goes down, UptimeRobot (free tier, 50 monitors) alerts you separately. This is your external canary.

**The "check from work" protocol** for a 60-second bathroom-break verification:

1. **Open Telegram** (5 seconds) → Read latest alerts. All green? Stop here.
2. **If yellow/red**: Send `/status` to the bot → Get instant health summary
3. **If system is DOWN**: Open Alpaca app → View positions → Verify stops are in place → If needed, tap "Liquidate All Positions"

Your Render dashboard should display **traffic-light indicators** (large green/yellow/red circles) visible in 2 seconds on a phone screen, with key numbers (open positions, daily P&L, last heartbeat "X minutes ago") readable without scrolling. Use 16px+ fonts and dark mode for discreet checking.

---

## 10. The dead man's switch is your most important safety mechanism as a solo operator

The biggest operational risk for a solo algorithmic trader isn't technical failure — it's **key person risk**. Academic research on algorithmic trading operational risk (Beunza et al., drawing on 189 interviews with market participants) confirms that automated trading systems exhibit "tight coupling and complex interactions" prone to cascading failures. Knight Capital's **$440 million loss in 45 minutes** from a deployment error illustrates the stakes.

**Essential safety mechanisms:**

- **Automated circuit breakers** (hard-coded, not runtime-configurable): maximum daily loss limit (e.g., 3% of capital → halt all trading), maximum single position size, maximum total position count. These should be enforced in code with no override capability during market hours.

- **Dead man's switch**: The operator must check in via Telegram `/alive` command at least every 4 hours on market days. If no check-in by noon ET, send warnings to operator and trusted contact. If no check-in by 1:00 PM ET, auto-close all positions via `close_all_positions(cancel_orders=True)`. Implement this via Healthchecks.io with a webhook trigger.

- **Durable limited Power of Attorney**: Execute a durable POA granting a trusted person trading authority on your Alpaca account. A "durable" POA remains valid if you're incapacitated. A "limited" POA restricts authority to trading only (no withdrawals). Contact Alpaca support to confirm their specific POA acceptance process.

- **Bitwarden Emergency Access**: Bitwarden's free tier includes Emergency Access — your designated contact can request access to your vault, and after a configurable wait period (e.g., 48 hours) without denial, access is granted automatically. This is a credentials dead man's switch. Store all API keys, Alpaca credentials, server SSH keys, and the emergency runbook in this vault.

- **One-page laminated Emergency Card** for your trusted contact with screenshots: (1) Go to app.alpaca.markets → log in → (2) Click "Positions" → "Close All Positions" → (3) Click Settings → "Disable API Access" → (4) Call operator's phone, then emergency contact. This person should practice the procedure once before it's needed.

**Insurance is impractical at this scale.** No standard product covers personal algorithmic trading losses from system failure. Self-insurance through conservative position sizing (≤1–2% risk per trade), bracket orders on every position, and capital segregation is the practical approach. SIPC coverage protects up to $500K if the broker itself fails, but not against market losses.

---

## Complete implementation budget and priority checklist

| Priority | Item | Cost | Impact |
|---|---|---|---|
| **1 (Week 1)** | Confirm all bracket orders use GTC time-in-force | $0 | Eliminates largest single risk |
| **2 (Week 1)** | CyberPower CP1500PFCLCD UPS + shutdown scripts | $200–260 | 15-min battery + graceful shutdown |
| **3 (Week 1)** | BIOS auto-power-on + NSSM services + auto-login | $0 | Automated recovery in ~3 minutes |
| **4 (Week 1)** | Windows Update registry hardening + Pro upgrade | $0–200 | Prevents surprise restarts |
| **5 (Week 2)** | SQLite PRAGMA hardening + backup API script | $0 | Eliminates data loss risk |
| **6 (Week 2)** | Ollama watchdog + VRAM monitoring script | $0 | Auto-recovers from LLM failures |
| **7 (Week 2)** | Telegram bot with /status, /positions, /kill | $0 | Remote monitoring + emergency control |
| **8 (Week 2)** | Healthchecks.io external dead man's switch | $0 | Catches total machine death |
| **9 (Week 3)** | Cellular backup (phone tether or TP-Link ER605) | $0–100 | Covers 3–8 annual ISP outages |
| **10 (Month 2)** | Hetzner cloud failover VM | $8.70/mo | Autonomous emergency trading |
| **11 (Month 2)** | Emergency runbook + trusted contact setup | $0 | Key person risk mitigation |
| **12 (Month 2)** | SSD clone + CrystalDiskInfo monitoring | $0–70 | Hardware failure recovery |

**Total one-time cost: $200–430.** Monthly ongoing: $8.70–20. This transforms a single-point-of-failure home setup into a resilient system with **sub-5-minute recovery** for most failure modes, **zero-intervention protection** for existing positions during complete machine death, and **autonomous cloud failover** for extended outages — all within a solo operator's budget.

## Conclusion

The hierarchy of risk for this system is clear: the greatest danger isn't hardware failure or power outages but rather **configuration oversights** — day-TIF bracket orders that expire, Windows updates that restart during market hours, or SQLite running without synchronous=FULL. These cost nothing to fix and eliminate the highest-probability failure modes. The UPS is the single most impactful hardware purchase, converting abrupt power failures into graceful 3-minute recovery events. Beyond that, the Ollama watchdog, Telegram monitoring, and Healthchecks.io dead man's switch create a monitoring mesh that catches failures within minutes — fast enough for the operator to take phone action during a work break. The cloud failover VM at $8.70/month provides genuine autonomy: if the home machine dies at 9:31 AM, the cloud instance can verify bracket order integrity and maintain risk management until the operator returns home. For a system scaling to $25K+, the approximately $400 infrastructure investment provides risk reduction disproportionate to its cost.