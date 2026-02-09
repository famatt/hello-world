#
# SPX Gamma Exposure (GEX) Monitor v2
# Hybrid: Manual GEX Levels + Real-Time Proxy Signals
# ------------------------------------------------------------------
#
# True GEX requires full options chain data (OI + gamma per strike)
# that thinkScript cannot access. This study combines the best
# available approach: manually-input daily GEX levels from a data
# provider (SpotGamma, Squeezemetrics, etc.) with real-time proxy
# signals that continuously confirm or challenge the regime.
#
# COMPONENTS:
#   1. Manual GEX Levels -- zero-gamma flip, call wall, put wall,
#      vol trigger. Update these each morning from your provider.
#   2. VIX Term Structure -- VIX vs VIX9D ratio detects hedging
#      demand shifts (backwardation = fear/negative GEX)
#   3. IV vs RV Spread -- when IV exceeds RV, positive GEX regime;
#      when RV exceeds IV, negative GEX (dealer hedging amplifies)
#   4. Gamma Pinning -- how tightly price clusters near key strikes
#   5. Volume Surge Detection -- flags dealer hedging near levels
#   6. Composite Confidence -- scores all signals together
#
# READING THE CHART:
#   - Histogram = price distance from zero-gamma level (in points)
#   - Above zero = positive GEX zone (mean-revert, fade moves)
#   - Below zero = negative GEX zone (trending, follow momentum)
#   - Green dashed line = call wall (hedging resistance)
#   - Red dashed line = put wall (hedging support)
#   - Magenta dashed line = vol trigger (selling accelerates below)
#   - Green/Red arrows = gamma regime flip (key signal!)
#   - Yellow dots = volume surge near a GEX level
#
# SETUP:
#   1. thinkorswim: Studies > Edit Studies > Studies tab > Create
#   2. Paste this script and click OK
#   3. Apply to SPX intraday chart (1-min, 2-min, or 5-min)
#   4. Right-click study > Edit properties > set daily GEX levels
#   5. Get levels from: spotgamma.com, squeezemetrics.com, or
#      similar GEX data provider each morning before open
#
# ------------------------------------------------------------------

declare lower;

# ==============================================================
# DAILY GEX LEVELS (update each morning)
# ==============================================================
# Get these from SpotGamma, Squeezemetrics, or your provider
# Right-click the study > Edit properties to update

input zeroGammaLevel  = 6000;   # Gamma Flip -- regime change level
input callWallLevel   = 6050;   # Call Wall -- resistance in +GEX
input putWallLevel    = 5950;   # Put Wall -- support in +GEX
input volTriggerLevel = 5900;   # Vol Trigger -- selling accelerates

# ==============================================================
# STUDY PARAMETERS
# ==============================================================

input rvLookback       = 20;    # Realized vol lookback (bars)
input smoothPeriod     = 5;     # Smoothing period
input keyStrikeSpacing = 25;    # Key strike interval for pinning
input pinLookback      = 20;    # Pinning detection lookback
input showLabels       = yes;
input showAlerts       = yes;

# ==============================================================
# CHART TIMEFRAME DETECTION
# ==============================================================

def aggPeriod = GetAggregationPeriod();
def barsPerDay =
    if aggPeriod == AggregationPeriod.MIN then 390
    else if aggPeriod == AggregationPeriod.TWO_MIN then 195
    else if aggPeriod == AggregationPeriod.THREE_MIN then 130
    else if aggPeriod == AggregationPeriod.FIVE_MIN then 78
    else if aggPeriod == AggregationPeriod.TEN_MIN then 39
    else if aggPeriod == AggregationPeriod.FIFTEEN_MIN then 26
    else if aggPeriod == AggregationPeriod.THIRTY_MIN then 13
    else if aggPeriod == AggregationPeriod.HOUR then 7
    else 1;
def barsPerYear = barsPerDay * 252;

# ==============================================================
# 1. PRICE vs GEX LEVELS
# ==============================================================

def gammaDistance = close - zeroGammaLevel;
def gammaSmooth  = ExpAverage(gammaDistance, smoothPeriod);

def aboveZeroGamma = close > zeroGammaLevel;
def belowZeroGamma = close < zeroGammaLevel;
def gammaFlip = aboveZeroGamma != aboveZeroGamma[1];

def nearCallWall  = AbsValue(close - callWallLevel) < 10;
def nearPutWall   = AbsValue(close - putWallLevel) < 10;
def nearZeroGamma = AbsValue(close - zeroGammaLevel) < 10;
def belowVolTrigger = close < volTriggerLevel;

# ==============================================================
# 2. VIX TERM STRUCTURE (VIX vs VIX9D)
# ==============================================================
# Normal contango: VIX9D < VIX (calm, positive GEX regime)
# Inverted backwardation: VIX9D > VIX (fear, negative GEX regime)
# This is one of the strongest real-time GEX regime indicators

def vixValue  = close("VIX");
def vix9dValue = close("VIX9D");
def termRatio = if vixValue > 0 then vix9dValue / vixValue else 1;
def termContango      = termRatio < 0.95;
def termBackwardation = termRatio > 1.05;

# ==============================================================
# 3. IV vs RV SPREAD
# ==============================================================

def ivFunc = imp_volatility();
def ivFallback = vixValue / 100;
def iv = if IsNaN(ivFunc) or ivFunc <= 0 then ivFallback else ivFunc;
def ivPct = iv * 100;
def ivSmooth = ExpAverage(ivPct, smoothPeriod);

def logRet = Log(close / close[1]);
def rvPerBar = StDev(logRet, rvLookback);
def rvAnn = rvPerBar * Sqrt(barsPerYear);
def rvPct = rvAnn * 100;
def rvSmooth = ExpAverage(rvPct, smoothPeriod);

def ivRvSpread = ivSmooth - rvSmooth;

# ==============================================================
# 4. GAMMA PINNING
# ==============================================================

def nearStrike = Round(close / keyStrikeSpacing, 0) * keyStrikeSpacing;
def distFromStrike = AbsValue(close - nearStrike);
def halfSpacing = keyStrikeSpacing / 2;
def pinRaw = if halfSpacing > 0
             then (1 - distFromStrike / halfSpacing) * 100
             else 50;
def pinAvg = Average(pinRaw, pinLookback);

# ==============================================================
# 5. VOLUME SURGE NEAR GEX LEVELS
# ==============================================================
# Spikes in volume near key levels = dealer hedging footprint

def avgVol = Average(volume, rvLookback);
def volSurge = if avgVol > 0 then volume / avgVol else 1;
def nearAnyLevel = nearCallWall or nearPutWall or nearZeroGamma;
def hedgingSurge = nearAnyLevel and volSurge > 1.5;

# ==============================================================
# 6. COMPOSITE CONFIDENCE SCORE
# ==============================================================
# Combines all signals: range -3 (strong negative) to +4 (strong positive)
#
# Level:     +1 above zero-gamma, -1 below
# VIX Term:  +1 contango, -1 backwardation, 0 flat
# IV-RV:     +1 spread > 2, -1 spread < -2, 0 neutral
# Pinning:   +1 pinAvg > 60 (strong pinning = positive gamma)

def levelConf = if aboveZeroGamma then 1 else -1;
def termConf  = if termContango then 1
                else if termBackwardation then -1 else 0;
def ivRvConf  = if ivRvSpread > 2 then 1
                else if ivRvSpread < -2 then -1 else 0;
def pinConf   = if pinAvg > 60 then 1 else 0;

def confidence = levelConf + termConf + ivRvConf + pinConf;

# ==============================================================
# PLOTS
# ==============================================================

# -- Main: distance from zero-gamma (histogram, in points) --
plot GammaHist = gammaDistance;
GammaHist.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
GammaHist.AssignValueColor(
    if belowVolTrigger then Color.MAGENTA
    else if nearCallWall and gammaDistance > 0 then Color.YELLOW
    else if nearPutWall and gammaDistance < 0 then Color.YELLOW
    else if gammaDistance > 30 then Color.GREEN
    else if gammaDistance > 0 then Color.DARK_GREEN
    else if gammaDistance > -30 then Color.DARK_RED
    else Color.RED);
GammaHist.SetLineWeight(3);

# -- Smoothed trend line --
plot GammaTrend = gammaSmooth;
GammaTrend.SetDefaultColor(Color.CYAN);
GammaTrend.SetLineWeight(2);

# -- Zero-gamma flip level (the most important line) --
plot ZeroLine = 0;
ZeroLine.SetDefaultColor(Color.WHITE);
ZeroLine.SetLineWeight(2);
ZeroLine.HideBubble();

# -- Call wall reference --
plot CallWall = callWallLevel - zeroGammaLevel;
CallWall.SetDefaultColor(Color.GREEN);
CallWall.SetStyle(Curve.MEDIUM_DASH);
CallWall.SetLineWeight(2);
CallWall.HideBubble();

# -- Put wall reference --
plot PutWall = putWallLevel - zeroGammaLevel;
PutWall.SetDefaultColor(Color.RED);
PutWall.SetStyle(Curve.MEDIUM_DASH);
PutWall.SetLineWeight(2);
PutWall.HideBubble();

# -- Vol trigger reference --
plot VolTrigger = volTriggerLevel - zeroGammaLevel;
VolTrigger.SetDefaultColor(Color.MAGENTA);
VolTrigger.SetStyle(Curve.SHORT_DASH);
VolTrigger.SetLineWeight(1);
VolTrigger.HideBubble();

# -- Gamma regime flip arrows --
plot FlipBullish = if gammaFlip and aboveZeroGamma then 0 else Double.NaN;
FlipBullish.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
FlipBullish.SetDefaultColor(Color.GREEN);
FlipBullish.SetLineWeight(5);

plot FlipBearish = if gammaFlip and belowZeroGamma then 0 else Double.NaN;
FlipBearish.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
FlipBearish.SetDefaultColor(Color.RED);
FlipBearish.SetLineWeight(5);

# -- Volume surge markers near GEX levels --
plot HedgeSurge = if hedgingSurge then gammaDistance else Double.NaN;
HedgeSurge.SetPaintingStrategy(PaintingStrategy.POINTS);
HedgeSurge.SetDefaultColor(Color.YELLOW);
HedgeSurge.SetLineWeight(3);

# ==============================================================
# DASHBOARD LABELS
# ==============================================================

# -- Update reminder --
AddLabel(showLabels,
    " Update GEX levels daily ",
    Color.DARK_GRAY);

# -- GEX Zone --
AddLabel(showLabels,
    if belowVolTrigger then " VOL TRIGGER ZONE "
    else if belowZeroGamma then " NEGATIVE GEX "
    else if nearCallWall then " CALL WALL ZONE "
    else " POSITIVE GEX ",
    if belowVolTrigger then Color.MAGENTA
    else if belowZeroGamma then Color.RED
    else if nearCallWall then Color.YELLOW
    else Color.GREEN);

# -- Confidence score --
AddLabel(showLabels,
    "Conf:" + Round(confidence, 0) + "/4",
    if confidence >= 3 then Color.GREEN
    else if confidence >= 1 then Color.DARK_GREEN
    else if confidence >= -1 then Color.GRAY
    else Color.RED);

# -- Zero-gamma distance --
AddLabel(showLabels,
    "Flip:" + Round(zeroGammaLevel, 0) + " " +
    Round(gammaDistance, 1) + "pts " +
    if aboveZeroGamma then "ABOVE" else "BELOW",
    if aboveZeroGamma then Color.GREEN else Color.RED);

# -- Wall distances --
AddLabel(showLabels,
    "CallWall:" + Round(callWallLevel, 0) +
    " (" + Round(callWallLevel - close, 1) + ")",
    if nearCallWall then Color.YELLOW else Color.GREEN);

AddLabel(showLabels,
    "PutWall:" + Round(putWallLevel, 0) +
    " (" + Round(putWallLevel - close, 1) + ")",
    if nearPutWall then Color.YELLOW else Color.RED);

# -- VIX term structure --
AddLabel(showLabels,
    "VIX:" + Round(vixValue, 1) +
    " 9D:" + Round(vix9dValue, 1) +
    " R:" + Round(termRatio, 2) +
    if termContango then " CONTANGO"
    else if termBackwardation then " BACKWRD"
    else " FLAT",
    if termContango then Color.GREEN
    else if termBackwardation then Color.RED
    else Color.GRAY);

# -- IV vs RV --
AddLabel(showLabels,
    "IV:" + Round(ivSmooth, 1) +
    " RV:" + Round(rvSmooth, 1) +
    " Sprd:" + Round(ivRvSpread, 1),
    if ivRvSpread > 2 then Color.GREEN
    else if ivRvSpread < -2 then Color.RED
    else Color.GRAY);

# -- Pinning --
AddLabel(showLabels,
    "Pin:" + Round(pinAvg, 0) + "% at " + Round(nearStrike, 0),
    if pinAvg > 70 then Color.GREEN
    else if pinAvg > 40 then Color.YELLOW
    else Color.RED);

# -- Volume --
AddLabel(showLabels,
    "Vol:" + Round(volSurge, 1) + "x" +
    if hedgingSurge then " HEDGE SURGE" else "",
    if hedgingSurge then Color.YELLOW
    else if volSurge > 1.5 then Color.CYAN
    else Color.GRAY);

# -- Trading guidance --
AddLabel(showLabels,
    if belowVolTrigger
        then "DANGER: Below vol trigger, expect accelerated selling"
    else if nearPutWall and belowZeroGamma
        then "WATCH: Testing put wall at " + Round(putWallLevel, 0)
    else if nearCallWall and aboveZeroGamma
        then "WATCH: Testing call wall at " + Round(callWallLevel, 0)
    else if nearZeroGamma
        then "CAUTION: Near gamma flip at " + Round(zeroGammaLevel, 0)
    else if aboveZeroGamma and confidence >= 2
        then "TRADE: +GEX confirmed, fade moves near " + Round(nearStrike, 0)
    else if belowZeroGamma and confidence <= -2
        then "TRADE: -GEX confirmed, follow momentum"
    else "MIXED: Reduce size, wait for clarity",
    if belowVolTrigger then Color.MAGENTA
    else if aboveZeroGamma and confidence >= 2 then Color.GREEN
    else if belowZeroGamma and confidence <= -2 then Color.RED
    else Color.YELLOW);

# ==============================================================
# ALERTS
# ==============================================================

Alert(showAlerts and gammaFlip and aboveZeroGamma,
    "GEX FLIP BULLISH: Price crossed above zero-gamma",
    Alert.BAR, Sound.Ding);

Alert(showAlerts and gammaFlip and belowZeroGamma,
    "GEX FLIP BEARISH: Price crossed below zero-gamma",
    Alert.BAR, Sound.Ring);

Alert(showAlerts and nearCallWall and close > close[1],
    "Approaching call wall resistance",
    Alert.BAR, Sound.NoSound);

Alert(showAlerts and nearPutWall and close < close[1],
    "Approaching put wall support",
    Alert.BAR, Sound.NoSound);

Alert(showAlerts and belowVolTrigger and close[1] >= volTriggerLevel,
    "VOL TRIGGER BREACHED: Selling may accelerate",
    Alert.BAR, Sound.Bell);
