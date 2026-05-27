"""Project constants for the HSI futures intraday workflow."""

DATA_PATH = "hi1_20170701_20200609.csv"

# Raw dataset columns.
COL_DATE = "date"
COL_TIME = "time"
COL_OPEN = "hi1_open"
COL_HIGH = "hi1_high"
COL_LOW = "hi1_low"
COL_CLOSE = "hi1_close"
COL_VOLUME = "hi1_volume"

# Day-session boundaries.
MORNING_START = 91400
MORNING_END = 115900
AFTERNOON_START = 130000
AFTERNOON_END = 162900
FORCED_EXIT_TIME = 162800

# Date splits.
TRAIN_START = 20170703
TRAIN_END = 20190628
VAL_START = 20190701
VAL_END = 20191231
TEST_START = 20200102
TEST_END = 20200609

# Contract parameters.
TICK_SIZE = 1
CONTRACT_MULTIPLIER = 50

# Round-trip cost assumptions.
BASE_SLIPPAGE = 2
COMMISSION_RT = 2
