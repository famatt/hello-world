#
# SPX Auto Direction -- 30DTE Calls / 0DTE Puts + 2-Point Trailing Stop
# ----------------------------------------------------------------------
#
# LOGIC OVERVIEW
# ----------------------------------------------------------------------
# Condition         | Bull Setup (Calls 30DTE) | Bear Setup (Puts 0DTE)
# ------------------+--------------------------+-----------------------
# Step 1: Time      | After 9:45 AM ET         | After 9:45 AM ET
# Step 2: VWAP      | Price ABOVE VWAP         | Price BELOW VWAP
# Step 3: ADX/DMI   | +DI on top, ADX > 25     | -DI on top, ADX > 25
# Step 4: MACD      | MACD crosses ABOVE signal| MACD crosses BELOW signal
# Step 5: Action    | BUY 30DTE ATM CALLS      | BUY 0DTE ATM PUTS
# Exit              | Trailing Stop 2 pts       | Trailing Stop 2 pts
# ----------------------------------------------------------------------
#
# USAGE
#   1. In thinkorswim go to Studies > Edit Studies > Create
#   2. Paste this entire script and click OK
#   3. Apply to an SPX intraday chart (1-min or 5-min recommended)
#   4. When an alert fires, manually place the order and attach
#      a Trailing Stop (see instructions at the bottom of this file)
#
# ----------------------------------------------------------------------

declare lower;

# ==============================================================
# INPUTS
# ==============================================================

input adxLength            = 14;
input adxTrendThreshold    = 25;
input macdFastLength       = 12;
input macdSlowLength       = 26;
input macdSignalLength     = 9;
input entryTime            = 0945;
input trailingStopPoints   = 2.0;
input showLabels           = yes;
input enableAlerts         = yes;

# ==============================================================
# STEP 1 -- TIME FILTER
# ==============================================================

def pastOpeningRange = SecondsFromTime(entryTime) >= 0;
def beforeClose     = SecondsTillTime(1555) > 0;
def tradingWindow   = pastOpeningRange and beforeClose;

# ==============================================================
# STEP 2 -- VWAP DIRECTION
# ==============================================================

def vwapValue = vwap();
def aboveVwap = close > vwapValue;
def belowVwap = close < vwapValue;

# ==============================================================
# STEP 3 -- ADX / DMI
# ==============================================================

def hiDiff  = high - high[1];
def loDiff  = low[1] - low;
def plusDM  = if hiDiff > loDiff and hiDiff > 0 then hiDiff else 0;
def minusDM = if loDiff > hiDiff and loDiff > 0 then loDiff else 0;
def ATR     = WildersAverage(TrueRange(high, close, low), adxLength);
def plusDI   = 100 * WildersAverage(plusDM, adxLength) / ATR;
def minusDI  = 100 * WildersAverage(minusDM, adxLength) / ATR;
def DX = if (plusDI + minusDI > 0)
         then 100 * AbsValue(plusDI - minusDI) / (plusDI + minusDI)
         else 0;
def ADXvalue = WildersAverage(DX, adxLength);

def adxStrong  = ADXvalue > adxTrendThreshold;
def adxRising  = ADXvalue > ADXvalue[1];
def bullDMI    = plusDI > minusDI and adxStrong and adxRising;
def bearDMI    = minusDI > plusDI and adxStrong and adxRising;

# ==============================================================
# STEP 4 -- MACD CROSS
# ==============================================================

def macdLine   = ExpAverage(close, macdFastLength) - ExpAverage(close, macdSlowLength);
def signalLine = ExpAverage(macdLine, macdSignalLength);
def macdHist   = macdLine - signalLine;

def macdBullCross = macdLine crosses above signalLine;
def macdBearCross = macdLine crosses below signalLine;

# ==============================================================
# STEP 5 -- ENTRY SIGNALS
# ==============================================================

def callSignal = tradingWindow and aboveVwap and bullDMI and macdBullCross;
def putSignal  = tradingWindow and belowVwap and bearDMI and macdBearCross;

# ==============================================================
# POSITION & TRAILING STOP
# ==============================================================
# Each variable uses its own inline if/then/else with self-reference.
# This is the reliable recursive pattern for thinkScript.
#
# position:  0 = flat, 1 = long calls, -1 = long puts

def position =
    if position[1] == 0 then
        if callSignal then 1
        else if putSignal then -1
        else 0
    else if position[1] == 1 then
        if low <= Max(trailHigh[1], high) - trailingStopPoints then 0
        else if beforeClose == 0 then 0
        else 1
    else
        if high >= Min(trailLow[1], low) + trailingStopPoints then 0
        else if beforeClose == 0 then 0
        else -1;

def trailHigh =
    if position[1] == 0 then
        if callSignal then close
        else 0
    else if position[1] == 1 then
        if low <= Max(trailHigh[1], high) - trailingStopPoints then 0
        else if beforeClose == 0 then 0
        else Max(trailHigh[1], high)
    else 0;

def trailLow =
    if position[1] == 0 then
        if putSignal then close
        else 0
    else if position[1] == -1 then
        if high >= Min(trailLow[1], low) + trailingStopPoints then 0
        else if beforeClose == 0 then 0
        else Min(trailLow[1], low)
    else 0;

def exitSignal =
    if position[1] == 0 then 0
    else if position[1] == 1 then
        if low <= Max(trailHigh[1], high) - trailingStopPoints then 1
        else if beforeClose == 0 then 1
        else 0
    else
        if high >= Min(trailLow[1], low) + trailingStopPoints then -1
        else if beforeClose == 0 then -1
        else 0;

# ==============================================================
# PLOTS -- MACD Panel
# ==============================================================

plot MACDplot = macdLine;
MACDplot.SetDefaultColor(Color.CYAN);
MACDplot.SetLineWeight(2);

plot SignalPlot = signalLine;
SignalPlot.SetDefaultColor(Color.ORANGE);
SignalPlot.SetLineWeight(1);

plot Hist = macdHist;
Hist.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
Hist.AssignValueColor(if macdHist >= 0 then Color.DARK_GREEN else Color.DARK_RED);

plot ZeroLine = 0;
ZeroLine.SetDefaultColor(Color.GRAY);
ZeroLine.SetStyle(Curve.SHORT_DASH);

# -- Entry Arrows --
plot CallEntry = if callSignal and position[1] == 0 then macdLine else Double.NaN;
CallEntry.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
CallEntry.SetDefaultColor(Color.GREEN);
CallEntry.SetLineWeight(4);

plot PutEntry = if putSignal and position[1] == 0 then macdLine else Double.NaN;
PutEntry.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
PutEntry.SetDefaultColor(Color.MAGENTA);
PutEntry.SetLineWeight(4);

# -- Exit Markers --
plot ExitCall = if exitSignal == 1 then macdLine else Double.NaN;
ExitCall.SetPaintingStrategy(PaintingStrategy.POINTS);
ExitCall.SetDefaultColor(Color.YELLOW);
ExitCall.SetLineWeight(4);

plot ExitPut = if exitSignal == -1 then macdLine else Double.NaN;
ExitPut.SetPaintingStrategy(PaintingStrategy.POINTS);
ExitPut.SetDefaultColor(Color.YELLOW);
ExitPut.SetLineWeight(4);

# ==============================================================
# CHART LABELS
# ==============================================================

AddLabel(showLabels,
    if tradingWindow then "TRADING WINDOW OPEN" else "OUTSIDE TRADING WINDOW",
    if tradingWindow then Color.GREEN else Color.GRAY);

AddLabel(showLabels,
    "VWAP: " + Round(vwapValue, 2) +
    if aboveVwap then " BULL" else if belowVwap then " BEAR" else " NEUTRAL",
    if aboveVwap then Color.GREEN else if belowVwap then Color.RED else Color.GRAY);

AddLabel(showLabels,
    "+DI:" + Round(plusDI, 1) + " -DI:" + Round(minusDI, 1) + " ADX:" + Round(ADXvalue, 1),
    if bullDMI then Color.GREEN else if bearDMI then Color.RED else Color.GRAY);

AddLabel(showLabels,
    "MACD:" + Round(macdLine, 2) + " Sig:" + Round(signalLine, 2),
    if macdBullCross then Color.GREEN else if macdBearCross then Color.MAGENTA else Color.GRAY);

AddLabel(showLabels,
    if position == 1 then "LONG CALLS | Stop:" + Round(trailHigh - trailingStopPoints, 2)
    else if position == -1 then "LONG PUTS | Stop:" + Round(trailLow + trailingStopPoints, 2)
    else "FLAT",
    if position == 1 then Color.GREEN
    else if position == -1 then Color.MAGENTA
    else Color.DARK_GRAY);

AddLabel(showLabels,
    if callSignal and position[1] == 0 then ">>> BUY 30DTE CALLS <<<"
    else if putSignal and position[1] == 0 then ">>> BUY 0DTE PUTS <<<"
    else if exitSignal == 1 then ">>> SOLD CALLS <<<"
    else if exitSignal == -1 then ">>> SOLD PUTS <<<"
    else "",
    if callSignal then Color.GREEN
    else if putSignal then Color.MAGENTA
    else Color.YELLOW);

# ==============================================================
# ALERTS
# ==============================================================

Alert(enableAlerts and callSignal and position[1] == 0,
    "SPX BULL: BUY 30DTE ATM CALLS", Alert.BAR, Sound.Ding);

Alert(enableAlerts and putSignal and position[1] == 0,
    "SPX BEAR: BUY 0DTE ATM PUTS", Alert.BAR, Sound.Ding);

Alert(enableAlerts and exitSignal == 1,
    "TRAIL STOP: SELL CALLS", Alert.BAR, Sound.Ring);

Alert(enableAlerts and exitSignal == -1,
    "TRAIL STOP: SELL PUTS", Alert.BAR, Sound.Ring);

# ==============================================================
# HOW TO SET UP LIVE TRAILING STOP ORDERS
# ==============================================================
#
# thinkScript cannot place live orders. Use alerts to trigger
# manual entries, then attach a Trailing Stop:
#
# 1. ENTRY:
#    - When alert fires, open the Option Chain
#    - CALLS: select ATM strike about 30 days out
#    - PUTS:  select ATM strike expiring TODAY (0DTE)
#
# 2. TRAILING STOP:
#    - Right-click your order > Create Opposite Order
#    - Change order type to Trailing Stop
#    - Set Trail Amount = 2.00
#    - Under Advanced Order > 1st Triggers 2nd
#
# 3. BRACKET ORDER (alternative):
#    - Right-click bid/ask > Buy Custom > With Trailing Stop
#    - Set trail = 2.00 pts > Submit
#
# ==============================================================
