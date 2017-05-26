from Core.signals import BacktestSignaller
from Core.reporters import NullReporter

reporter = NullReporter()
signaller = BacktestSignaller()

settings = {
    "signaller" : signaller,
    "reporter" : reporter,
    "processes": 4,
    "is_backtest" : True
}