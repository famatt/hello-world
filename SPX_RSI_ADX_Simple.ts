# RSI + ADX Call/Put Signal
# ----------------------------------------------------------------------
# Calls: RSI near 0 (oversold) and ADX > 20
# Puts:  RSI near 100 (overbought) and ADX > 20
# ----------------------------------------------------------------------

declare upper;

# ==============================================================
# INPUTS
# ==============================================================

input rsiLength        = 14;
input adxLength        = 14;
input adxThreshold     = 20;
input rsiCallBelow     = 10;
input rsiPutAbove      = 90;
input showLabels       = yes;

# ==============================================================
# RSI (manual calculation)
# ==============================================================

def rsiUp   = Max(close - close[1], 0);
def rsiDown = Max(close[1] - close, 0);
def avgUp   = WildersAverage(rsiUp, rsiLength);
def avgDown = WildersAverage(rsiDown, rsiLength);
def rs      = if avgDown > 0 then avgUp / avgDown else 0;
def rsiValue = if avgDown == 0 then 100 else 100 - (100 / (1 + rs));

# ==============================================================
# ADX
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

# ==============================================================
# SIGNALS
# ==============================================================

def callSignal = rsiValue <= rsiCallBelow and adxReady;
def putSignal  = rsiValue >= rsiPutAbove and adxReady;

# ==============================================================
# ARROWS
# ==============================================================

plot CallArrow = if callSignal then low - (TickSize() * 20) else Double.NaN;
CallArrow.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
CallArrow.SetDefaultColor(Color.GREEN);
CallArrow.SetLineWeight(5);

plot PutArrow = if putSignal then high + (TickSize() * 20) else Double.NaN;
PutArrow.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
PutArrow.SetDefaultColor(Color.RED);
PutArrow.SetLineWeight(5);

# ==============================================================
# LABELS
# ==============================================================

AddLabel(showLabels,
    "RSI:" + Round(rsiValue, 1),
    if rsiValue <= rsiCallBelow then Color.GREEN
    else if rsiValue >= rsiPutAbove then Color.RED
    else Color.GRAY);

AddLabel(showLabels,
    "ADX:" + Round(ADXvalue, 1),
    if adxReady then Color.GREEN else Color.GRAY);

AddLabel(showLabels,
    if callSignal then "BUY CALLS"
    else if putSignal then "BUY PUTS"
    else "NO SIGNAL",
    if callSignal then Color.GREEN
    else if putSignal then Color.RED
    else Color.GRAY);
