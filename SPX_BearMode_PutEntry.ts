#
# SPX Bear Mode Put Entry Strategy
# ----------------------------------------------------------------------
# 5-Step Bearish Entry Signal for SPX
#
# Step 1: Wait 15 mins after open (9:45 AM ET) for Opening Range to settle
# Step 2: Check VWAP -- SPX must be below 6,940 = "Bear Mode"
# Step 3: Check ADX/DMI -- -DI on top, ADX climbing past 25
# Step 4: MACD crossover -- MACD line crosses below signal line
# Step 5: Signal -- Buy ATM Puts
#
# Usage: Apply to SPX on an intraday chart (1-min, 5-min, or 15-min)
# ----------------------------------------------------------------------

declare lower;

# ==============================================================
# INPUTS -- Tune these to your preference
# ==============================================================

input vwapBearLevel        = 6940;       # Step 2: Bear threshold
input adxLength            = 14;         # Step 3: ADX/DMI lookback
input adxTrendThreshold    = 25;         # Step 3: ADX strength threshold
input macdFastLength       = 12;         # Step 4: MACD fast EMA
input macdSlowLength       = 26;         # Step 4: MACD slow EMA
input macdSignalLength     = 9;          # Step 4: MACD signal smoothing
input entryTime            = 0945;       # Step 1: Earliest entry time (HHMM)
input showLabels           = yes;        # Show status labels on chart
input enableAlerts         = yes;        # Fire alerts on entry signal

# ==============================================================
# STEP 1 -- Opening Range Timer (Wait 15 Mins After 9:30 AM)
# ==============================================================

def pastOpeningRange = SecondsFromTime(entryTime) >= 0;

# ==============================================================
# STEP 2 -- VWAP Bear Mode Check (Price Below Threshold)
# ==============================================================

def vwapValue = vwap();
def belowVwap = close < vwapValue;
def belowBearLevel = close < vwapBearLevel;
def bearMode = belowVwap and belowBearLevel;

# ==============================================================
# STEP 3 -- ADX / DMI Trend Confirmation
# ==============================================================

def hiDiff = high - high[1];
def loDiff = low[1] - low;
def plusDM = if hiDiff > loDiff and hiDiff > 0 then hiDiff else 0;
def minusDM = if loDiff > hiDiff and loDiff > 0 then loDiff else 0;

def ATR = WildersAverage(TrueRange(high, close, low), adxLength);

def plusDI  = 100 * WildersAverage(plusDM, adxLength) / ATR;
def minusDI = 100 * WildersAverage(minusDM, adxLength) / ATR;

def DX = if (plusDI + minusDI > 0)
         then 100 * AbsValue(plusDI - minusDI) / (plusDI + minusDI)
         else 0;
def ADXvalue = WildersAverage(DX, adxLength);

# -DI must be above +DI (bearish directional pressure)
def minusDIonTop = minusDI > plusDI;

# ADX must be above threshold (strong trend)
def adxStrong = ADXvalue > adxTrendThreshold;

# ADX must be climbing (momentum building)
def adxRising = ADXvalue > ADXvalue[1];

def dmiConfirmed = minusDIonTop and adxStrong and adxRising;

# ==============================================================
# STEP 4 -- MACD Bearish Crossover
# ==============================================================

def macdLine   = ExpAverage(close, macdFastLength) - ExpAverage(close, macdSlowLength);
def signalLine = ExpAverage(macdLine, macdSignalLength);
def macdHist   = macdLine - signalLine;

# MACD line just crossed below signal line (bearish cross)
def macdBearCross = macdLine crosses below signalLine;

# ==============================================================
# STEP 5 -- ENTRY SIGNAL: All Conditions Met = Buy ATM Puts
# ==============================================================

def allConditionsMet = pastOpeningRange
                   and bearMode
                   and dmiConfirmed
                   and macdBearCross;

# ==============================================================
# PLOTS -- Visual Signals on Lower Panel
# ==============================================================

# Plot the MACD and Signal for visual reference
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

# -- Entry Arrow --
plot PutEntry = if allConditionsMet then macdLine else Double.NaN;
PutEntry.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
PutEntry.SetDefaultColor(Color.MAGENTA);
PutEntry.SetLineWeight(4);

# ==============================================================
# STEP TRACKER -- Individual Condition Plots (1 = met, 0 = not)
# ==============================================================

plot Step1_OpeningRange = if pastOpeningRange then 1 else 0;
Step1_OpeningRange.SetDefaultColor(Color.GRAY);
Step1_OpeningRange.SetPaintingStrategy(PaintingStrategy.POINTS);
Step1_OpeningRange.Hide();

plot Step2_BearMode = if bearMode then 1 else 0;
Step2_BearMode.SetDefaultColor(Color.RED);
Step2_BearMode.SetPaintingStrategy(PaintingStrategy.POINTS);
Step2_BearMode.Hide();

plot Step3_DMI = if dmiConfirmed then 1 else 0;
Step3_DMI.SetDefaultColor(Color.YELLOW);
Step3_DMI.SetPaintingStrategy(PaintingStrategy.POINTS);
Step3_DMI.Hide();

plot Step4_MACD = if macdBearCross then 1 else 0;
Step4_MACD.SetDefaultColor(Color.ORANGE);
Step4_MACD.SetPaintingStrategy(PaintingStrategy.POINTS);
Step4_MACD.Hide();

# ==============================================================
# CHART LABELS -- Real-Time Status Dashboard
# ==============================================================

AddLabel(showLabels,
    if pastOpeningRange then "Step 1: OPEN RANGE SETTLED" else "Step 1: WAITING FOR 9:45",
    if pastOpeningRange then Color.GREEN else Color.GRAY
);

AddLabel(showLabels,
    "VWAP: " + Round(vwapValue, 2) +
    (if bearMode then " | BEAR MODE" else " | NO BEAR"),
    if bearMode then Color.RED else Color.GRAY
);

AddLabel(showLabels,
    "-DI: " + Round(minusDI, 1) +
    " +DI: " + Round(plusDI, 1) +
    " ADX: " + Round(ADXvalue, 1),
    if dmiConfirmed then Color.GREEN else Color.GRAY
);

AddLabel(showLabels,
    "MACD: " + Round(macdLine, 2) +
    " Sig: " + Round(signalLine, 2),
    if macdBearCross then Color.MAGENTA else Color.GRAY
);

AddLabel(showLabels,
    if allConditionsMet then ">>> BUY ATM PUTS <<<" else "NO SIGNAL",
    if allConditionsMet then Color.MAGENTA else Color.DARK_GRAY
);

# ==============================================================
# ALERTS
# ==============================================================

Alert(enableAlerts and allConditionsMet,
    "SPX Bear Mode: ALL 5 STEPS MET - BUY ATM PUTS",
    Alert.BAR, Sound.Ding
);

Alert(enableAlerts and bearMode and !bearMode[1],
    "SPX entered Bear Mode (below VWAP and " + vwapBearLevel + ")",
    Alert.BAR, Sound.NoSound
);

Alert(enableAlerts and dmiConfirmed and !dmiConfirmed[1],
    "DMI confirmed: -DI on top, ADX > " + adxTrendThreshold + " and rising",
    Alert.BAR, Sound.NoSound
);
