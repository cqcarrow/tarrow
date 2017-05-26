"""
The Versions/[VersionName]/index.py defines the parameters that apply to all, or most, of the
stocks across all versions. Each environment in Versions/[VersionName]/[environment].py
(e.g. Internal.py) overrides settings from this file. For each stock,
Versions/[VersionName]/Stock/[Stock]/index.py overrides THOSE settings, which are finally
overridden by Versions/[VersionName]/Stock/[environment].py, if it exists.
"""

settings = {
    "processes": 4,
    "trade_amount": 25000,
    "stop_loss_threshold": 0.004, # e.g. 0.4% stoploss
}
