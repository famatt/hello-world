#
# SPX Gamma Exposure (GEX) Monitor
# Continuous proxy-based GEX estimation for SPX
# ------------------------------------------------------------------
#
# NOTE: True GEX requires full options chain data (open interest
# and gamma at every strike). thinkScript cannot access this data
# directly. This study uses proxy methods to estimate the GEX
# regime, which are well-established in quantitative research:
#
# PRIMARY METHOD: IV vs RV Spread
#   When implied volatility exceeds realized volatility, options
#   are "expensive" -- market makers are likely net long gamma.
#   They hedge by selling into rallies and buying dips, creating
#   a mean-reverting environment (positive GEX).
#
#   When realized vol exceeds implied vol, options are "cheap" --
#   market makers are likely net short gamma. Their hedging
#   amplifies directional moves, creating a trending environment
#   (negative GEX).
#
# SECONDARY: Gamma Pinning Score
#   Measures how tightly SPX clusters near key option strikes.
#   Strong pinning suggests high positive gamma at nearby levels.
#
# TERTIARY: Dealer Flow Absorption
#   When high volume produces small price moves, dealers are
#   absorbing order flow (positive GEX). When volume amplifies
#   moves, dealers are adding to momentum (negative GEX).
#
# USAGE:
#   1. thinkorswim: Studies > Edit Studies > Studies tab > Create
#   2. Paste this script and click OK
#   3. Apply to SPX intraday chart (1-min, 2-min, or 5-min)
#   4. Green bars = positive GEX (fade moves, buy dips, sell rips)
#   5. Red bars = negative GEX (follow momentum, trade breakouts)
#
# ------------------------------------------------------------------

declare lower;

# ==============================================================
# INPUTS
# ==============================================================

input rvLookback       = 20;     # Realized vol lookback (bars)
input smoothPeriod     = 5;      # Smoothing period
input keyStrikeSpacing = 25;     # Key strike interval (25 or 50)
input pinLookback      = 20;     # Pinning detection lookback
input posThreshold     = 2.0;    # Positive GEX threshold
input negThreshold     = -2.0;   # Negative GEX threshold
input showLabels       = yes;

# ==============================================================
# CHART TIMEFRAME DETECTION
# ==============================================================
# Auto-detect bars per year for proper RV annualization

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
# IMPLIED VOLATILITY
# ==============================================================
# imp_volatility() returns annualized IV as a decimal
# For SPX this effectively reflects VIX
# Falls back to VIX cross-reference if unavailable

def ivFunc = imp_volatility();
def ivVIX = close("VIX") / 100;
def iv = if IsNaN(ivFunc) or ivFunc <= 0 then ivVIX else ivFunc;
def ivPct = iv * 100;
def ivSmooth = ExpAverage(ivPct, smoothPeriod);

# ==============================================================
# REALIZED VOLATILITY (annualized, close-to-close)
# ==============================================================

def logRet = Log(close / close[1]);
def rvPerBar = StDev(logRet, rvLookback);
def rvAnnualized = rvPerBar * Sqrt(barsPerYear);
def rvPct = rvAnnualized * 100;
def rvSmooth = ExpAverage(rvPct, smoothPeriod);

# ==============================================================
# GEX PROXY: IV - RV SPREAD
# ==============================================================
# Positive spread = IV > RV = positive GEX (mean reversion)
#   Dealers long gamma: sell rallies, buy dips
#   Price pins near strikes, range compresses
#
# Negative spread = RV > IV = negative GEX (trending)
#   Dealers short gamma: buy rallies, sell dips
#   Price breaks through levels, range expands

def gexRaw = ivSmooth - rvSmooth;
def gexSignal = ExpAverage(gexRaw, smoothPeriod * 2);

def isPositiveGEX = gexRaw > posThreshold;
def isNegativeGEX = gexRaw < negThreshold;

# ==============================================================
# GAMMA PINNING SCORE
# ==============================================================
# Measures how tightly price clusters near key option strikes
# 100 = right at a strike, 0 = halfway between strikes

def nearStrike = Round(close / keyStrikeSpacing, 0) * keyStrikeSpacing;
def distFromStrike = AbsValue(close - nearStrike);
def halfSpacing = keyStrikeSpacing / 2;
def pinRaw = if halfSpacing > 0
             then (1 - distFromStrike / halfSpacing) * 100
             else 50;
def pinAvg = Average(pinRaw, pinLookback);

# ==============================================================
# DEALER FLOW ABSORPTION
# ==============================================================
# High volume + small move = dealers absorbing (positive GEX)
# Volume amplifying moves = dealers adding momentum (negative GEX)

def barMove = AbsValue(close - open);
def avgBarMove = Average(barMove, rvLookback);
def avgVolume = Average(volume, rvLookback);
def volSurge = if avgVolume > 0 then volume / avgVolume else 1;
def moveSurge = if avgBarMove > 0 then barMove / avgBarMove else 1;
def flowAbsorption = if moveSurge > 0.01 then volSurge / moveSurge else 1;
def flowSmooth = ExpAverage(flowAbsorption, smoothPeriod);

# ==============================================================
# PLOTS
# ==============================================================

# -- Main GEX histogram --
plot GEXHist = gexRaw;
GEXHist.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
GEXHist.AssignValueColor(
    if gexRaw > posThreshold * 2 then Color.GREEN
    else if gexRaw > posThreshold then Color.DARK_GREEN
    else if gexRaw > 0 then CreateColor(70, 100, 70)
    else if gexRaw > negThreshold then CreateColor(100, 70, 70)
    else if gexRaw > negThreshold * 2 then Color.DARK_RED
    else Color.RED);
GEXHist.SetLineWeight(3);

# -- Smoothed signal line --
plot GEXTrend = gexSignal;
GEXTrend.SetDefaultColor(Color.CYAN);
GEXTrend.SetLineWeight(2);

# -- Reference lines --
plot ZeroLine = 0;
ZeroLine.SetDefaultColor(Color.WHITE);
ZeroLine.SetStyle(Curve.SHORT_DASH);
ZeroLine.SetLineWeight(1);
ZeroLine.HideBubble();
ZeroLine.HideTitle();

plot PosLine = posThreshold;
PosLine.SetDefaultColor(Color.DARK_GREEN);
PosLine.SetStyle(Curve.SHORT_DASH);
PosLine.SetLineWeight(1);
PosLine.HideBubble();
PosLine.HideTitle();

plot NegLine = negThreshold;
NegLine.SetDefaultColor(Color.DARK_RED);
NegLine.SetStyle(Curve.SHORT_DASH);
NegLine.SetLineWeight(1);
NegLine.HideBubble();
NegLine.HideTitle();

# ==============================================================
# DASHBOARD LABELS
# ==============================================================

# -- GEX Regime --
AddLabel(showLabels,
    if isPositiveGEX then " +GEX: POSITIVE (Mean-Revert) "
    else if isNegativeGEX then " -GEX: NEGATIVE (Trending) "
    else " GEX: NEUTRAL ",
    if isPositiveGEX then Color.GREEN
    else if isNegativeGEX then Color.RED
    else Color.GRAY);

# -- IV value --
AddLabel(showLabels,
    "IV:" + Round(ivSmooth, 1) + "%",
    Color.CYAN);

# -- RV value --
AddLabel(showLabels,
    "RV:" + Round(rvSmooth, 1) + "%",
    Color.ORANGE);

# -- IV-RV Spread --
AddLabel(showLabels,
    "Spread:" + Round(gexRaw, 1),
    if gexRaw > 0 then Color.GREEN else Color.RED);

# -- Pinning score --
AddLabel(showLabels,
    "Pin:" + Round(pinAvg, 0) + "%",
    if pinAvg > 70 then Color.GREEN
    else if pinAvg > 40 then Color.YELLOW
    else Color.RED);

# -- Key gamma strikes --
def strikeAbove = nearStrike + keyStrikeSpacing;
def strikeBelow = nearStrike - keyStrikeSpacing;

AddLabel(showLabels,
    "Strikes: " + Round(strikeBelow, 0) + " | " + Round(nearStrike, 0) + " | " + Round(strikeAbove, 0),
    Color.WHITE);

# -- Distance to nearest strike --
AddLabel(showLabels,
    "Dist:" + Round(distFromStrike, 1) + "pts to " + Round(nearStrike, 0),
    if distFromStrike < 5 then Color.GREEN
    else if distFromStrike < 10 then Color.YELLOW
    else Color.GRAY);

# -- Dealer flow absorption --
AddLabel(showLabels,
    "Flow:" +
    if flowSmooth > 1.3 then " ABSORBED"
    else if flowSmooth < 0.7 then " AMPLIFIED"
    else " NORMAL",
    if flowSmooth > 1.3 then Color.GREEN
    else if flowSmooth < 0.7 then Color.RED
    else Color.GRAY);

# -- Trading guidance --
AddLabel(showLabels,
    if isPositiveGEX then "TRADE: Fade moves, sell rips/buy dips near " + Round(nearStrike, 0)
    else if isNegativeGEX then "TRADE: Follow momentum, trade breakouts"
    else "TRADE: Mixed regime, reduce size",
    if isPositiveGEX then Color.GREEN
    else if isNegativeGEX then Color.RED
    else Color.YELLOW);
