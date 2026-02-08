#
# SPX Day Trade Scalping Strategy
# 10 Contracts | 3-Point Trailing Stop
# ----------------------------------------------------------------------
#
# INDICATORS (most common for SPX scalping)
# ----------------------------------------------------------------------
# Indicator  | Purpose              | Call Condition    | Put Condition
# -----------+----------------------+-------------------+-----------------
# VWAP       | Institutional bias   | Price ABOVE       | Price BELOW
# EMA 9/21   | Trend trigger        | 9 above 21        | 9 below 21
# ADX        | Trend strength       | ADX > 20          | ADX > 20
# DMI        | Trend direction      | +DI > -DI         | -DI > +DI
# MACD       | Momentum trigger     | Bullish cross      | Bearish cross
# RSI        | Exhaustion filter    | RSI < 70          | RSI > 30
# -----------+----------------------+-------------------+-----------------
# EXIT       | 3-point trailing stop from best price since entry
# ----------------------------------------------------------------------
#
# USAGE
#   1. thinkorswim: Studies > Edit Studies > Strategies tab > Create
#   2. Paste this script and click OK
#   3. Apply to SPX intraday chart (1-min or 2-min)
#
# ----------------------------------------------------------------------

declare lower;

# ==============================================================
# INPUTS
# ==============================================================

input emaFast              = 9;
input emaSlow              = 21;
input adxLength            = 14;
input adxThreshold         = 20;
input macdFastLength       = 12;
input macdSlowLength       = 26;
input macdSignalLength     = 9;
input rsiLength            = 14;
input rsiOverbought        = 70;
input rsiOversold          = 30;
input trailStopPoints      = 3.0;
input contracts            = 10;
input showLabels           = yes;

# ==============================================================
# EMA 9/21 (Trend Direction)
# ==============================================================

def ema9  = ExpAverage(close, emaFast);
def ema21 = ExpAverage(close, emaSlow);
def emaBullSide = ema9 > ema21;
def emaBearSide = ema9 < ema21;

# ==============================================================
# VWAP (Institutional Bias)
# ==============================================================

def vwapValue = vwap();
def aboveVwap = close > vwapValue;
def belowVwap = close < vwapValue;

# ==============================================================
# ADX / DMI (Trend Strength + Direction)
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

def adxReady = ADXvalue > adxThreshold;
def bullDMI  = plusDI > minusDI;
def bearDMI  = minusDI > plusDI;

# ==============================================================
# MACD (Momentum Trigger)
# ==============================================================
# Crossover within last 5 bars - this is the firing pin

def macdLine   = ExpAverage(close, macdFastLength) - ExpAverage(close, macdSlowLength);
def signalLine = ExpAverage(macdLine, macdSignalLength);
def macdHist   = macdLine - signalLine;

def macdBullCrossNow = macdLine crosses above signalLine;
def macdBearCrossNow = macdLine crosses below signalLine;
def macdBullCross = Sum(macdBullCrossNow, 5) >= 1;
def macdBearCross = Sum(macdBearCrossNow, 5) >= 1;

# ==============================================================
# RSI (Exhaustion Filter)
# ==============================================================

def rsiUp   = Max(close - close[1], 0);
def rsiDown = Max(close[1] - close, 0);
def avgUp   = WildersAverage(rsiUp, rsiLength);
def avgDown = WildersAverage(rsiDown, rsiLength);
def rs      = if avgDown > 0 then avgUp / avgDown else 0;
def rsiValue = if avgDown == 0 then 100 else 100 - (100 / (1 + rs));

def rsiCallOK = rsiValue < rsiOverbought;
def rsiPutOK  = rsiValue > rsiOversold;

# ==============================================================
# ENTRY SIGNALS -- 6 Indicators Must Align
# ==============================================================

def callSignal = aboveVwap and emaBullSide
                 and adxReady and bullDMI
                 and macdBullCross and macdLine >= signalLine
                 and rsiCallOK;

def putSignal  = belowVwap and emaBearSide
                 and adxReady and bearDMI
                 and macdBearCross and macdLine <= signalLine
                 and rsiPutOK;

# ==============================================================
# FILTER PASS COUNT (for debugging)
# ==============================================================

def callFilters = (if aboveVwap then 1 else 0)
               + (if emaBullSide then 1 else 0)
               + (if adxReady and bullDMI then 1 else 0)
               + (if macdBullCross and macdLine >= signalLine then 1 else 0)
               + (if rsiCallOK then 1 else 0);

def putFilters = (if belowVwap then 1 else 0)
              + (if emaBearSide then 1 else 0)
              + (if adxReady and bearDMI then 1 else 0)
              + (if macdBearCross and macdLine <= signalLine then 1 else 0)
              + (if rsiPutOK then 1 else 0);

# ==============================================================
# TRAILING STOP (3 Points)
# ==============================================================

def beforeClose = SecondsTillTime(1555) > 0;

def trailHigh =
    if trailHigh[1] > 0 then
        if low <= Max(trailHigh[1], high) - trailStopPoints then 0
        else if beforeClose == 0 then 0
        else Max(trailHigh[1], high)
    else if callSignal then close
    else 0;

def trailLow =
    if trailLow[1] > 0 then
        if high >= Min(trailLow[1], low) + trailStopPoints then 0
        else if beforeClose == 0 then 0
        else Min(trailLow[1], low)
    else if putSignal and trailHigh == 0 then close
    else 0;

def inCallTrade = trailHigh > 0;
def inPutTrade  = trailLow > 0;
def callExit = trailHigh[1] > 0 and trailHigh == 0;
def putExit  = trailLow[1] > 0 and trailLow == 0;

# ==============================================================
# STRATEGY ORDERS
# ==============================================================

AddOrder(OrderType.BUY_TO_OPEN,
    callSignal and trailHigh[1] == 0 and trailLow[1] == 0,
    close, contracts, Color.GREEN, Color.GREEN, "BUY CALLS x" + contracts);

AddOrder(OrderType.SELL_TO_OPEN,
    putSignal and trailHigh[1] == 0 and trailLow[1] == 0,
    close, contracts, Color.RED, Color.RED, "BUY PUTS x" + contracts);

AddOrder(OrderType.SELL_TO_CLOSE, callExit,
    close, contracts, Color.YELLOW, Color.YELLOW, "SELL CALLS (TRAIL)");

AddOrder(OrderType.BUY_TO_CLOSE, putExit,
    close, contracts, Color.YELLOW, Color.YELLOW, "SELL PUTS (TRAIL)");

# ==============================================================
# VISUAL ARROWS (Lower Panel)
# ==============================================================
# Values: +1 = call entry, -1 = put entry
#         +0.5 = call exit, -0.5 = put exit

plot CallArrow = if callSignal and trailHigh[1] == 0 and trailLow[1] == 0
                 then 1 else Double.NaN;
CallArrow.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
CallArrow.SetDefaultColor(Color.GREEN);
CallArrow.SetLineWeight(5);

plot PutArrow = if putSignal and trailHigh[1] == 0 and trailLow[1] == 0
                then -1 else Double.NaN;
PutArrow.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
PutArrow.SetDefaultColor(Color.RED);
PutArrow.SetLineWeight(5);

plot CallExitArrow = if callExit then 0.5 else Double.NaN;
CallExitArrow.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
CallExitArrow.SetDefaultColor(Color.YELLOW);
CallExitArrow.SetLineWeight(4);

plot PutExitArrow = if putExit then -0.5 else Double.NaN;
PutExitArrow.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
PutExitArrow.SetDefaultColor(Color.YELLOW);
PutExitArrow.SetLineWeight(4);

# -- Zero reference line --
plot ZeroLine = 0;
ZeroLine.SetDefaultColor(Color.GRAY);
ZeroLine.SetStyle(Curve.SHORT_DASH);
ZeroLine.SetLineWeight(1);

# ==============================================================
# DASHBOARD LABELS
# ==============================================================

AddLabel(showLabels,
    "VWAP:" + Round(vwapValue, 2) +
    if aboveVwap then " ABOVE" else if belowVwap then " BELOW" else " =",
    if aboveVwap then Color.GREEN else if belowVwap then Color.RED else Color.GRAY);

AddLabel(showLabels,
    "EMA " + emaFast + "/" + emaSlow + ":" +
    if emaBullSide then " BULL" else " BEAR",
    if emaBullSide then Color.GREEN else if emaBearSide then Color.RED else Color.GRAY);

AddLabel(showLabels,
    "ADX:" + Round(ADXvalue, 1) + " +DI:" + Round(plusDI, 1) + " -DI:" + Round(minusDI, 1),
    if adxReady and bullDMI then Color.GREEN
    else if adxReady and bearDMI then Color.RED
    else Color.GRAY);

AddLabel(showLabels,
    "MACD:" + Round(macdLine, 2) + " Sig:" + Round(signalLine, 2),
    if macdBullCross and macdLine >= signalLine then Color.GREEN
    else if macdBearCross and macdLine <= signalLine then Color.RED
    else Color.GRAY);

AddLabel(showLabels,
    "RSI:" + Round(rsiValue, 1),
    if rsiValue >= rsiOverbought then Color.RED
    else if rsiValue <= rsiOversold then Color.RED
    else Color.GREEN);

# -- Filter count --
AddLabel(showLabels,
    if aboveVwap or emaBullSide then "CALL " + callFilters + "/5"
    else "PUT " + putFilters + "/5",
    if callFilters == 5 or putFilters == 5 then Color.GREEN
    else if callFilters >= 4 or putFilters >= 4 then Color.YELLOW
    else Color.GRAY);

# -- Position status --
AddLabel(showLabels,
    if inCallTrade then "LONG " + contracts + " CALLS | Stop:" +
        Round(trailHigh - trailStopPoints, 2)
    else if inPutTrade then "LONG " + contracts + " PUTS | Stop:" +
        Round(trailLow + trailStopPoints, 2)
    else "FLAT",
    if inCallTrade then Color.GREEN
    else if inPutTrade then Color.RED
    else Color.DARK_GRAY);

AddLabel(showLabels,
    if callSignal and trailHigh[1] == 0 and trailLow[1] == 0
        then ">>> BUY " + contracts + " CALLS <<<"
    else if putSignal and trailHigh[1] == 0 and trailLow[1] == 0
        then ">>> BUY " + contracts + " PUTS <<<"
    else if callExit then ">>> SOLD CALLS <<<"
    else if putExit then ">>> SOLD PUTS <<<"
    else "",
    if callSignal then Color.GREEN
    else if putSignal then Color.RED
    else Color.YELLOW);
