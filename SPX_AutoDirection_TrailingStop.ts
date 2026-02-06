#
# SPX Auto Direction — 30DTE Calls / 0DTE Puts + 2-Point Trailing Stop
# ──────────────────────────────────────────────────────────────────────
#
# LOGIC OVERVIEW
# ──────────────────────────────────────────────────────────────────────
# Condition         │ Bull Setup (Calls 30DTE) │ Bear Setup (Puts 0DTE)
# ──────────────────┼──────────────────────────┼───────────────────────
# Step 1: Time      │ After 9:45 AM ET         │ After 9:45 AM ET
# Step 2: VWAP      │ Price ABOVE VWAP & level  │ Price BELOW VWAP & level
# Step 3: ADX/DMI   │ +DI on top, ADX > 25     │ -DI on top, ADX > 25
# Step 4: MACD      │ MACD crosses ABOVE signal │ MACD crosses BELOW signal
# Step 5: Action    │ BUY 30DTE ATM CALLS      │ BUY 0DTE ATM PUTS
# Exit              │ Trailing Stop 2 pts       │ Trailing Stop 2 pts
# ──────────────────────────────────────────────────────────────────────
#
# USAGE
#   1. Apply as a STRATEGY on SPX intraday chart (1m or 5m)
#   2. Use the signals + alerts to place live orders manually
#      OR set up Conditional Orders in thinkorswim (see notes at bottom)
#
# ──────────────────────────────────────────────────────────────────────

declare lower;

# ═══════════════════════════════════════════════════════════
# INPUTS
# ═══════════════════════════════════════════════════════════

input vwapBullLevel        = 6940;       # Price must be ABOVE this for bull
input vwapBearLevel        = 6940;       # Price must be BELOW this for bear
input adxLength            = 14;         # ADX / DMI lookback period
input adxTrendThreshold    = 25;         # ADX minimum for trend confirmation
input macdFastLength       = 12;         # MACD fast EMA length
input macdSlowLength       = 26;         # MACD slow EMA length
input macdSignalLength     = 9;          # MACD signal smoothing
input openingRangeMinutes  = 15;         # Minutes after 9:30 to wait
input trailingStopPoints   = 2.0;        # Trailing stop distance in points
input showLabels           = yes;
input enableAlerts         = yes;

# ═══════════════════════════════════════════════════════════
# STEP 1 — TIME FILTER: Past Opening Range (9:45 AM ET)
# ═══════════════════════════════════════════════════════════

def marketOpenTime    = 0930;
def entryWindowStart  = marketOpenTime + openingRangeMinutes;
def pastOpeningRange  = SecondsFromTime(entryWindowStart) >= 0;
def beforeClose       = SecondsTillTime(1555) > 0;  # No new entries after 3:55 PM
def tradingWindow     = pastOpeningRange and beforeClose;

# ═══════════════════════════════════════════════════════════
# STEP 2 — VWAP DIRECTION
# ═══════════════════════════════════════════════════════════

def vwapValue    = vwap();
def aboveVwap    = close > vwapValue and close > vwapBullLevel;
def belowVwap    = close < vwapValue and close < vwapBearLevel;

# ═══════════════════════════════════════════════════════════
# STEP 3 — ADX / DMI
# ═══════════════════════════════════════════════════════════

def hiDiff   = high - high[1];
def loDiff   = low[1] - low;
def plusDM   = if hiDiff > loDiff and hiDiff > 0 then hiDiff else 0;
def minusDM  = if loDiff > hiDiff and loDiff > 0 then loDiff else 0;
def ATR      = WildersAverage(TrueRange(high, close, low), adxLength);
def plusDI    = 100 * WildersAverage(plusDM, adxLength) / ATR;
def minusDI   = 100 * WildersAverage(minusDM, adxLength) / ATR;
def DX       = if (plusDI + minusDI > 0)
               then 100 * AbsValue(plusDI - minusDI) / (plusDI + minusDI)
               else 0;
def ADXvalue = WildersAverage(DX, adxLength);

def adxStrong   = ADXvalue > adxTrendThreshold;
def adxRising   = ADXvalue > ADXvalue[1];

# Bull DMI: +DI on top, strong & rising ADX
def bullDMI = plusDI > minusDI and adxStrong and adxRising;

# Bear DMI: -DI on top, strong & rising ADX
def bearDMI = minusDI > plusDI and adxStrong and adxRising;

# ═══════════════════════════════════════════════════════════
# STEP 4 — MACD CROSS
# ═══════════════════════════════════════════════════════════

def macdLine   = ExpAverage(close, macdFastLength) - ExpAverage(close, macdSlowLength);
def signalLine = ExpAverage(macdLine, macdSignalLength);
def macdHist   = macdLine - signalLine;

def macdBullCross = macdLine crosses above signalLine;
def macdBearCross = macdLine crosses below signalLine;

# ═══════════════════════════════════════════════════════════
# STEP 5 — ENTRY SIGNALS
# ═══════════════════════════════════════════════════════════

def callSignal = tradingWindow and aboveVwap and bullDMI and macdBullCross;
def putSignal  = tradingWindow and belowVwap and bearDMI and macdBearCross;

# ═══════════════════════════════════════════════════════════
# POSITION & TRAILING STOP STATE MACHINE
# ═══════════════════════════════════════════════════════════
#  position:  0 = flat, 1 = long calls, -1 = long puts
#  entryPrice: price at time of entry
#  trailHigh:  highest price since call entry (for call trailing stop)
#  trailLow:   lowest price since put entry  (for put trailing stop)

def position;
def entryPrice;
def trailHigh;
def trailLow;
def exitSignal;

if (position[1] == 0) {
    # ── FLAT — look for new entries ──
    if (callSignal) {
        position   = 1;
        entryPrice = close;
        trailHigh  = close;
        trailLow   = close;
        exitSignal = 0;
    } else if (putSignal) {
        position   = -1;
        entryPrice = close;
        trailLow   = close;
        trailHigh  = close;
        exitSignal = 0;
    } else {
        position   = 0;
        entryPrice = 0;
        trailHigh  = 0;
        trailLow   = 0;
        exitSignal = 0;
    }
} else if (position[1] == 1) {
    # ── LONG CALLS — trail the high, stop if price drops 2 pts from peak ──
    def newHigh = Max(trailHigh[1], high);
    if (low <= newHigh - trailingStopPoints) {
        # Trailing stop triggered — exit calls
        position   = 0;
        entryPrice = 0;
        trailHigh  = 0;
        trailLow   = 0;
        exitSignal = 1;
    } else if (!beforeClose) {
        # End-of-day forced exit
        position   = 0;
        entryPrice = 0;
        trailHigh  = 0;
        trailLow   = 0;
        exitSignal = 1;
    } else {
        position   = 1;
        entryPrice = entryPrice[1];
        trailHigh  = newHigh;
        trailLow   = 0;
        exitSignal = 0;
    }
} else {
    # ── LONG PUTS — trail the low, stop if price rises 2 pts from trough ──
    def newLow = Min(trailLow[1], low);
    if (high >= newLow + trailingStopPoints) {
        # Trailing stop triggered — exit puts
        position   = 0;
        entryPrice = 0;
        trailHigh  = 0;
        trailLow   = 0;
        exitSignal = -1;
    } else if (!beforeClose) {
        # End-of-day forced exit
        position   = 0;
        entryPrice = 0;
        trailHigh  = 0;
        trailLow   = 0;
        exitSignal = -1;
    } else {
        position   = -1;
        entryPrice = entryPrice[1];
        trailLow   = newLow;
        trailHigh  = 0;
        exitSignal = 0;
    }
}

# ═══════════════════════════════════════════════════════════
# PLOTS — MACD Panel + Signals
# ═══════════════════════════════════════════════════════════

plot MACD = macdLine;
MACD.SetDefaultColor(Color.CYAN);
MACD.SetLineWeight(2);

plot Signal = signalLine;
Signal.SetDefaultColor(Color.ORANGE);
Signal.SetLineWeight(1);

plot Histogram = macdHist;
Histogram.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
Histogram.AssignValueColor(
    if macdHist >= 0 then Color.DARK_GREEN else Color.DARK_RED
);

plot ZeroLine = 0;
ZeroLine.SetDefaultColor(Color.GRAY);
ZeroLine.SetStyle(Curve.SHORT_DASH);

# ── Entry Arrows ──
plot CallEntry = if callSignal and position[1] == 0 then macdLine else Double.NaN;
CallEntry.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
CallEntry.SetDefaultColor(Color.GREEN);
CallEntry.SetLineWeight(4);

plot PutEntry = if putSignal and position[1] == 0 then macdLine else Double.NaN;
PutEntry.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
PutEntry.SetDefaultColor(Color.MAGENTA);
PutEntry.SetLineWeight(4);

# ── Exit Markers ──
plot ExitCall = if exitSignal == 1 then macdLine else Double.NaN;
ExitCall.SetPaintingStrategy(PaintingStrategy.SQUARE);
ExitCall.SetDefaultColor(Color.YELLOW);
ExitCall.SetLineWeight(3);

plot ExitPut = if exitSignal == -1 then macdLine else Double.NaN;
ExitPut.SetPaintingStrategy(PaintingStrategy.SQUARE);
ExitPut.SetDefaultColor(Color.YELLOW);
ExitPut.SetLineWeight(3);

# ═══════════════════════════════════════════════════════════
# STRATEGY ORDERS (for Strategy Backtesting mode)
# ═══════════════════════════════════════════════════════════

AddOrder(OrderType.BUY_TO_OPEN, callSignal and position[1] == 0,
    close, 1, Color.GREEN, Color.GREEN, name = "BUY 30DTE CALLS");

AddOrder(OrderType.SELL_TO_CLOSE, exitSignal == 1,
    close, 1, Color.YELLOW, Color.YELLOW, name = "SELL CALLS (Trail Stop)");

AddOrder(OrderType.SELL_TO_OPEN, putSignal and position[1] == 0,
    close, 1, Color.MAGENTA, Color.MAGENTA, name = "BUY 0DTE PUTS");

AddOrder(OrderType.BUY_TO_CLOSE, exitSignal == -1,
    close, 1, Color.YELLOW, Color.YELLOW, name = "SELL PUTS (Trail Stop)");

# ═══════════════════════════════════════════════════════════
# CHART LABELS — Live Dashboard
# ═══════════════════════════════════════════════════════════

AddLabel(showLabels,
    if !tradingWindow then "OUTSIDE TRADING WINDOW"
    else if pastOpeningRange then "Step 1: OPEN RANGE SETTLED"
    else "Step 1: WAITING...",
    if tradingWindow then Color.GREEN else Color.GRAY
);

AddLabel(showLabels,
    "VWAP: " + Round(vwapValue, 2) +
    (if aboveVwap then " | BULL ZONE" else if belowVwap then " | BEAR ZONE" else " | NEUTRAL"),
    if aboveVwap then Color.GREEN else if belowVwap then Color.RED else Color.GRAY
);

AddLabel(showLabels,
    "+DI: " + Round(plusDI, 1) +
    " -DI: " + Round(minusDI, 1) +
    " ADX: " + Round(ADXvalue, 1),
    if bullDMI then Color.GREEN else if bearDMI then Color.RED else Color.GRAY
);

AddLabel(showLabels,
    "MACD: " + Round(macdLine, 2) + " Sig: " + Round(signalLine, 2),
    if macdBullCross then Color.GREEN
    else if macdBearCross then Color.MAGENTA
    else Color.GRAY
);

# ── Position Status ──
AddLabel(showLabels,
    if position == 1 then "POSITION: LONG CALLS 30DTE | Trail High: " + Round(trailHigh, 2) +
                          " | Stop: " + Round(trailHigh - trailingStopPoints, 2)
    else if position == -1 then "POSITION: LONG PUTS 0DTE | Trail Low: " + Round(trailLow, 2) +
                                " | Stop: " + Round(trailLow + trailingStopPoints, 2)
    else "POSITION: FLAT",
    if position == 1 then Color.GREEN
    else if position == -1 then Color.MAGENTA
    else Color.DARK_GRAY
);

# ── Last Signal ──
AddLabel(showLabels,
    if callSignal and position[1] == 0 then ">>> BUY 30DTE ATM CALLS <<<"
    else if putSignal and position[1] == 0 then ">>> BUY 0DTE ATM PUTS <<<"
    else if exitSignal == 1 then ">>> SOLD CALLS (TRAIL STOP) <<<"
    else if exitSignal == -1 then ">>> SOLD PUTS (TRAIL STOP) <<<"
    else "",
    if callSignal then Color.GREEN
    else if putSignal then Color.MAGENTA
    else Color.YELLOW
);

# ═══════════════════════════════════════════════════════════
# ALERTS
# ═══════════════════════════════════════════════════════════

Alert(enableAlerts and callSignal and position[1] == 0,
    "SPX BULL: BUY 30DTE ATM CALLS — All conditions met",
    Alert.BAR, Sound.Ding);

Alert(enableAlerts and putSignal and position[1] == 0,
    "SPX BEAR: BUY 0DTE ATM PUTS — All conditions met",
    Alert.BAR, Sound.Ding);

Alert(enableAlerts and exitSignal == 1,
    "TRAILING STOP HIT: SELL 30DTE CALLS — " + trailingStopPoints + " pt trail triggered",
    Alert.BAR, Sound.Ring);

Alert(enableAlerts and exitSignal == -1,
    "TRAILING STOP HIT: SELL 0DTE PUTS — " + trailingStopPoints + " pt trail triggered",
    Alert.BAR, Sound.Ring);

# ═══════════════════════════════════════════════════════════
# NOTES — How to Set Up Live Conditional Orders in thinkorswim
# ═══════════════════════════════════════════════════════════
#
# thinkScript CANNOT place live orders directly. Use the alerts
# from this study to trigger manual entries, then attach a
# Trailing Stop via the Order Entry:
#
# 1. ENTRY:
#    - When you hear the "Ding" alert, go to the Option Chain
#    - For CALLS: select the ATM strike ~30 days out
#    - For PUTS:  select the ATM strike expiring TODAY (0DTE)
#    - Click "Buy" to open the order ticket
#
# 2. TRAILING STOP (attach as conditional exit):
#    - In the Order Entry, right-click your order → "Create Opposite Order"
#    - Change order type to "Trailing Stop"
#    - Set Trail Amount = 2.00 (points)
#    - Set Trail Type = "Standard"
#    - Under "Advanced Order" → make it "1st Triggers 2nd" (1st = entry, 2nd = trail stop)
#    - This auto-submits the trailing stop once your entry fills
#
# 3. BRACKET ORDER (alternative):
#    - Right-click the bid/ask in Option Chain
#    - Select "Buy Custom" → "With Trailing Stop"
#    - Set trail = 2.00 pts
#    - Submit as a single bracket order
#
# ═══════════════════════════════════════════════════════════
