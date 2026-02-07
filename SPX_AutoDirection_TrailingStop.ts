#
# SPX 5-Filter 0DTE Strategy (Backtest + Live Signals)
# ----------------------------------------------------------------------
#
# FILTER LOGIC
# ----------------------------------------------------------------------
# Filter | Calls                     | Puts
# -------+---------------------------+---------------------------
# 1 VWAP | Price ABOVE VWAP          | Price BELOW VWAP
# 2 ADX  | ADX > 20 and rising       | ADX > 20 and rising
# 3 DMI  | +DI above -DI             | -DI above +DI
# 4 MACD | Bullish crossover         | Bearish crossover
# 5 RSI  | RSI must be < 70          | RSI must be > 30
# -------+---------------------------+---------------------------
#
# USAGE
#   1. In thinkorswim: Studies > Edit Studies > Strategies tab
#   2. Create new strategy, paste this script, click OK
#   3. Apply to SPX intraday chart (1-min or 2-min recommended)
#
# ----------------------------------------------------------------------

declare upper;

# ==============================================================
# INPUTS
# ==============================================================

input adxLength            = 14;
input adxTrendThreshold    = 20;
input macdFastLength       = 12;
input macdSlowLength       = 26;
input macdSignalLength     = 9;
input rsiLength            = 14;
input rsiOverbought        = 70;
input rsiOversold          = 30;
input showLabels           = yes;

# ==============================================================
# FILTER 1 -- VWAP (The Institutional Line)
# ==============================================================

def vwapValue = vwap();
def aboveVwap = close > vwapValue;
def belowVwap = close < vwapValue;

# ==============================================================
# FILTER 2 -- ADX (The Power Meter)
# ==============================================================
# ADX must be > 20 and trending upward (higher than 3 bars ago)

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

def adxReady = ADXvalue > adxTrendThreshold and ADXvalue > ADXvalue[3];

# ==============================================================
# FILTER 3 -- DMI (The Scissor Check)
# ==============================================================

def bullDMI = plusDI > minusDI;
def bearDMI = minusDI > plusDI;

# ==============================================================
# FILTER 4 -- MACD (The Firing Pin)
# ==============================================================
# Crossover within the last 5 bars so filters have time to align

def macdLine   = ExpAverage(close, macdFastLength) - ExpAverage(close, macdSlowLength);
def signalLine = ExpAverage(macdLine, macdSignalLength);
def macdHist   = macdLine - signalLine;

def macdBullCrossNow = macdLine crosses above signalLine;
def macdBearCrossNow = macdLine crosses below signalLine;
def macdBullCross = Sum(macdBullCrossNow, 5) >= 1;
def macdBearCross = Sum(macdBearCrossNow, 5) >= 1;

# ==============================================================
# FILTER 5 -- RSI (The Exhaustion Check)
# ==============================================================
# Computed manually for reliable numeric output

def rsiUp   = Max(close - close[1], 0);
def rsiDown = Max(close[1] - close, 0);
def avgUp   = WildersAverage(rsiUp, rsiLength);
def avgDown = WildersAverage(rsiDown, rsiLength);
def rs      = if avgDown > 0 then avgUp / avgDown else 0;
def rsiValue = if avgDown == 0 then 100 else 100 - (100 / (1 + rs));

def rsiCallOK = rsiValue < rsiOverbought;
def rsiPutOK  = rsiValue > rsiOversold;

# ==============================================================
# ENTRY SIGNALS -- All 5 Filters Must Pass
# ==============================================================

def callSignal = aboveVwap and adxReady and bullDMI
                 and macdBullCross and macdLine >= signalLine
                 and rsiCallOK;

def putSignal  = belowVwap and adxReady and bearDMI
                 and macdBearCross and macdLine <= signalLine
                 and rsiPutOK;

# ==============================================================
# FILTER PASS COUNT (for debugging)
# ==============================================================

def callFilters = (if aboveVwap then 1 else 0)
               + (if adxReady then 1 else 0)
               + (if bullDMI then 1 else 0)
               + (if macdBullCross and macdLine >= signalLine then 1 else 0)
               + (if rsiCallOK then 1 else 0);

def putFilters = (if belowVwap then 1 else 0)
              + (if adxReady then 1 else 0)
              + (if bearDMI then 1 else 0)
              + (if macdBearCross and macdLine <= signalLine then 1 else 0)
              + (if rsiPutOK then 1 else 0);

# ==============================================================
# STRATEGY ORDERS (for backtesting)
# ==============================================================
# BUY_AUTO = go long (simulates buying calls)
# SELL_AUTO = go short (simulates buying puts)
# Opposing signal auto-closes the previous position

AddOrder(OrderType.BUY_AUTO, callSignal, close, 1,
         Color.GREEN, Color.GREEN, "CALL ENTRY");

AddOrder(OrderType.SELL_AUTO, putSignal, close, 1,
         Color.RED, Color.RED, "PUT ENTRY");

# ==============================================================
# VISUAL ENTRY ARROWS
# ==============================================================

plot CallEntryArrow = if callSignal then low - (TickSize() * 20) else Double.NaN;
CallEntryArrow.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
CallEntryArrow.SetDefaultColor(Color.CYAN);
CallEntryArrow.SetLineWeight(5);

plot PutEntryArrow = if putSignal then high + (TickSize() * 20) else Double.NaN;
PutEntryArrow.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
PutEntryArrow.SetDefaultColor(Color.MAGENTA);
PutEntryArrow.SetLineWeight(5);

# ==============================================================
# DASHBOARD LABELS
# ==============================================================

AddLabel(showLabels,
    "F1 VWAP:" + Round(vwapValue, 2) +
    if aboveVwap then " ABOVE" else if belowVwap then " BELOW" else " =",
    if aboveVwap then Color.GREEN else if belowVwap then Color.RED else Color.GRAY);

AddLabel(showLabels,
    "F2 ADX:" + Round(ADXvalue, 1) +
    if adxReady then " TRENDING" else " CHOP",
    if adxReady then Color.GREEN else Color.GRAY);

AddLabel(showLabels,
    "F3 +DI:" + Round(plusDI, 1) + " -DI:" + Round(minusDI, 1),
    if bullDMI then Color.GREEN else if bearDMI then Color.RED else Color.GRAY);

AddLabel(showLabels,
    "F4 MACD:" + Round(macdLine, 2) + " Sig:" + Round(signalLine, 2),
    if macdBullCross and macdLine >= signalLine then Color.GREEN
    else if macdBearCross and macdLine <= signalLine then Color.MAGENTA
    else Color.GRAY);

AddLabel(showLabels,
    "F5 RSI:" + Round(rsiValue, 1),
    if rsiValue >= rsiOverbought then Color.RED
    else if rsiValue <= rsiOversold then Color.RED
    else Color.GREEN);

# -- Filter count --
AddLabel(showLabels,
    if aboveVwap then "CALL " + callFilters + "/5"
    else if belowVwap then "PUT " + putFilters + "/5"
    else "0/5",
    if callFilters == 5 or putFilters == 5 then Color.GREEN
    else if callFilters >= 4 or putFilters >= 4 then Color.YELLOW
    else Color.GRAY);

AddLabel(showLabels,
    if callSignal then "SIGNAL: BUY CALLS"
    else if putSignal then "SIGNAL: BUY PUTS"
    else "SIGNAL: NONE",
    if callSignal then Color.GREEN
    else if putSignal then Color.MAGENTA
    else Color.GRAY);
