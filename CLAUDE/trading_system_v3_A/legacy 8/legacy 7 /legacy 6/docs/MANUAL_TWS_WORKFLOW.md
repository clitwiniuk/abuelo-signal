# Manual TWS Workflow Guide

## ✅ Recommended Workflow (No Automation Needed)

### For Development & Testing

1. **Start TWS/Gateway manually:**
   ```bash
   # Option A: TWS (full interface)
   open "/Users/carlos/Applications/Trader Workstation/Trader Workstation.app"
   
   # Option B: Gateway (lighter, API-only)
   open "/Applications/IB Gateway.app"  # If you have it installed
   ```

2. **Login once:**
   - Enter your credentials (carlli554)
   - TWS/Gateway will stay open

3. **Start your trading system:**
   ```bash
   cd ~/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3
   python simple_main.py
   ```

4. **Your system connects automatically** to TWS/Gateway on port 7497 (paper)

### Benefits of Manual Approach

✅ **No compatibility issues** - Always works with latest IBKR versions  
✅ **More secure** - No passwords stored in files  
✅ **Easier debugging** - You can see TWS interface  
✅ **Simpler setup** - No complex automation scripts  

### For Production (Optional)

If you need 24/7 operation later:

1. **Keep TWS/Gateway running** - It can stay open for days/weeks
2. **System auto-restart** - macOS can relaunch apps on reboot
3. **Monitoring** - Add health checks to restart if needed

## 🚫 Why IBC Doesn't Work

- **IBC 3.23.0** was designed for old TWS versions
- **TWS 1028+** changed internal structure completely
- **No fix available** - Would need IBC rewrite
- **Not worth the effort** - Manual launch is simple enough

## 📝 Daily Routine

**Morning (before market open):**
```bash
# 1. Open TWS
open "/Users/carlos/Applications/Trader Workstation/Trader Workstation.app"

# 2. Login

# 3. Start trading system
cd ~/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3
python simple_main.py
```

**Evening (after market close):**
```bash
# Stop trading system (Ctrl+C)
# Close TWS (File → Exit)
```

That's it! Simple and reliable.

## 🧹 Cleanup

To remove IBC files:
```bash
cd ~/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3
./scripts/automation/cleanup_ibc.sh
```
