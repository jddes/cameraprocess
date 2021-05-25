

EXP_OFFSET = 28 # from manual, section 5.12: EXPPERIOD = (EXP + 28) / (PIXCLK:MAX) (seconds)
PIXCLK_MAX = 20750000 # read back from the camera once

def countsToSeconds(EXP_adjusted):
    return float(EXP_adjusted)/PIXCLK_MAX