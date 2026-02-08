#
# SPX Day Trade Scalping Strategy
# 10 Contracts | 3-Point Trailing Stop
# ----------------------------------------------------------------------
#
# INDICATORS USED (most common for SPX scalping)
# ----------------------------------------------------------------------
# Indicator  | Purpose              | Call Condition    | Put Condition
# -----------+----------------------+-------------------+-----------------
# VWAP       | Institutional bias   | Price ABOVE       | Price BELOW
# EMA 9/21   | Trend trigger        | 9 crosses above 21| 9 crosses below 21
# ADX        | Trend strength       | ADX > 20 rising   | ADX > 20 rising
# DMI        | Trend direction      | +DI > -DI         | -DI > +DI
# MACD       | Momentum confirm     | Histogram > 0     | Histogram < 0
# RSI        | Exhaustion filter    | RSI < 70          | RSI > 30
# Volume     | Move confirmation    | Above 1.5x avg    | Above 1.5x avg
# -----------+----------------------+-------------------+-----------------
# EXIT       | 3-point trailing stop from best price since entry
# ----------------------------------------------------------------------
#
# USAGE
#   1. thinkorswim: Studies > Edit Studies > Strategies tab > Create
#   2. Paste this script and click OK
#   3. Apply to SPX intraday chart (1-min or 2-min)
#   4. Set to 10 contracts in strategy settings
#
# ----------------------------------------------------------------------

declare upper;

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
input volumeAvgLength      = 20;
input volumeMultiplier     = 1.5;
input trailStopPoints      = 3.0;
input contracts            = 10;
input showLabels           = yes;

# ==============================================================
# EMA 9/21 (Trend Trigger)
# ==============================================================

def ema9  = ExpAverage(close, emaFast);
def ema21 = ExpAverage(close, emaSlow);

def emaBullCrossNow = ema9 crosses above ema21;
def emaBearCrossNow = ema9 crosses below ema21;
def emaBullCross = Sum(emaBullCrossNow, 5) >= 1;
def emaBearCross = Sum(emaBearCrossNow, 5) >= 1;
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

def adxReady = ADXvalue > adxThreshold and ADXvalue > ADXvalue[3];
def bullDMI  = plusDI > minusDI;
def bearDMI  = minusDI > plusDI;

# ==============================================================
# MACD (Momentum Confirmation)
# ==============================================================

def macdLine   = ExpAverage(close, macdFastLength) - ExpAverage(close, macdSlowLength);
def signalLine = ExpAverage(macdLine, macdSignalLength);
def macdHist   = macdLine - signalLine;

def macdBullish = macdHist > 0;
def macdBearish = macdHist < 0;

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
# Volume (Move Confirmation)
# ==============================================================

def avgVol  = Average(volume, volumeAvgLength);
def highVol = volume > avgVol * volumeMultiplier;

# ==============================================================
# ENTRY SIGNALS -- All Indicators Must Align
# ==============================================================

def callSignal = aboveVwap and emaBullCross and emaBullSide
                 and adxReady and bullDMI
                 and macdBullish
                 and rsiCallOK
                 and highVol;

def putSignal  = belowVwap and emaBearCross and emaBearSide
                 and adxReady and bearDMI
                 and macdBearish
                 and rsiPutOK
                 and highVol;

# ==============================================================
# TRAILING STOP (3 Points)
# ==============================================================
# trailHigh > 0 = in a CALL position (tracks running high)
# trailLow  > 0 = in a PUT position (tracks running low)

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

def callExit =  trailHigh[1] > 0 and trailHigh == 0;
def putExit  =  trailLow[1] > 0 and trailLow == 0;

# ==============================================================
# STRATEGY ORDERS
# ==============================================================

# -- Entries --
AddOrder(OrderType.BUY_TO_OPEN,
    callSignal and trailHigh[1] == 0 and trailLow[1] == 0,
    close, contracts, Color.GREEN, Color.GREEN, "BUY CALLS x" + contracts);

AddOrder(OrderType.SELL_TO_OPEN,
    putSignal and trailHigh[1] == 0 and trailLow[1] == 0,
    close, contracts, Color.RED, Color.RED, "BUY PUTS x" + contracts);

# -- Exits (trailing stop hit or end of day) --
AddOrder(OrderType.SELL_TO_CLOSE, callExit,
    close, contracts, Color.YELLOW, Color.YELLOW, "SELL CALLS (TRAIL STOP)");

AddOrder(OrderType.BUY_TO_CLOSE, putExit,
    close, contracts, Color.YELLOW, Color.YELLOW, "SELL PUTS (TRAIL STOP)");

# ==============================================================
# VISUAL ARROWS
# ==============================================================

# -- Entry arrows --
plot CallArrow = if callSignal and trailHigh[1] == 0 and trailLow[1] == 0
                 then low - (TickSize() * 30) else Double.NaN;
CallArrow.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
CallArrow.SetDefaultColor(Color.GREEN);
CallArrow.SetLineWeight(5);

plot PutArrow = if putSignal and trailHigh[1] == 0 and trailLow[1] == 0
                then high + (TickSize() * 30) else Double.NaN;
PutArrow.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
PutArrow.SetDefaultColor(Color.RED);
PutArrow.SetLineWeight(5);

# -- Exit arrows --
plot CallExitArrow = if callExit then high + (TickSize() * 30) else Double.NaN;
CallExitArrow.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
CallExitArrow.SetDefaultColor(Color.YELLOW);
CallExitArrow.SetLineWeight(4);

plot PutExitArrow = if putExit then low - (TickSize() * 30) else Double.NaN;
PutExitArrow.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
PutExitArrow.SetDefaultColor(Color.YELLOW);
PutExitArrow.SetLineWeight(4);

# -- EMA lines on chart --
plot EMA9line = ema9;
EMA9line.SetDefaultColor(Color.CYAN);
EMA9line.SetLineWeight(1);

plot EMA21line = ema21;
EMA21line.SetDefaultColor(Color.ORANGE);
EMA21line.SetLineWeight(1);

# -- VWAP line on chart --
plot VWAPline = vwapValue;
VWAPline.SetDefaultColor(Color.WHITE);
VWAPline.SetStyle(Curve.MEDIUM_DASH);
VWAPline.SetLineWeight(2);

# ==============================================================
# DASHBOARD LABELS
# ==============================================================

AddLabel(showLabels,
    "VWAP:" + Round(vwapValue, 2) +
    if aboveVwap then " ABOVE" else if belowVwap then " BELOW" else " =",
    if aboveVwap then Color.GREEN else if belowVwap then Color.RED else Color.GRAY);

AddLabel(showLabels,
    "EMA:" + Round(ema9, 2) + "/" + Round(ema21, 2),
    if emaBullSide then Color.GREEN else if emaBearSide then Color.RED else Color.GRAY);

AddLabel(showLabels,
    "ADX:" + Round(ADXvalue, 1) + " +DI:" + Round(plusDI, 1) + " -DI:" + Round(minusDI, 1),
    if adxReady and bullDMI then Color.GREEN
    else if adxReady and bearDMI then Color.RED
    else Color.GRAY);

AddLabel(showLabels,
    "MACD Hist:" + Round(macdHist, 2),
    if macdBullish then Color.GREEN else if macdBearish then Color.RED else Color.GRAY);

AddLabel(showLabels,
    "RSI:" + Round(rsiValue, 1),
    if rsiValue >= rsiOverbought then Color.RED
    else if rsiValue <= rsiOversold then Color.RED
    else Color.GREEN);

AddLabel(showLabels,
    "VOL:" + Round(volume / 1000, 1) + "K" +
    if highVol then " HIGH" else " LOW",
    if highVol then Color.GREEN else Color.GRAY);

# -- Position & Trail Stop --
AddLabel(showLabels,
    if inCallTrade then "LONG " + contracts + " CALLS | Trail:" +
        Round(trailHigh, 2) + " Stop:" + Round(trailHigh - trailStopPoints, 2)
    else if inPutTrade then "LONG " + contracts + " PUTS | Trail:" +
        Round(trailLow, 2) + " Stop:" + Round(trailLow + trailStopPoints, 2)
    else "FLAT",
    if inCallTrade then Color.GREEN
    else if inPutTrade then Color.RED
    else Color.DARK_GRAY);

# -- Active Signal --
AddLabel(showLabels,
    if callSignal and trailHigh[1] == 0 and trailLow[1] == 0 then ">>> BUY " + contracts + " CALLS <<<"
    else if putSignal and trailHigh[1] == 0 and trailLow[1] == 0 then ">>> BUY " + contracts + " PUTS <<<"
    else if callExit then ">>> SOLD CALLS (TRAIL STOP) <<<"
    else if putExit then ">>> SOLD PUTS (TRAIL STOP) <<<"
    else "",
    if callSignal then Color.GREEN
    else if putSignal then Color.RED
    else Color.YELLOW);
