from core.strategy import MultiStrategy, MovingAverageStrategy
from core.trademonitor import MultiTradeMonitor, BoundaryTradeMonitor, TimeLimitTradeMonitor

moving_average_5_20 = MovingAverageStrategy(5, 20)
moving_average_10_15 = MovingAverageStrategy(10, 15)
multi_strategy = MovingAverageStrategy([moving_average_5_20, moving_average_10_15])

boundaries = BoundaryTradeMonitor(stop_loss_bp=50, take_profit_bp=50)
time_limit = TimeLimitTradeMonitor(30) # up to 30 minutes per trade
multi_strategy = MultiTradeMonitor([boundaries, time_limit])


settings = {
    'trade_monitor' : multi_monitor,
    'strategy' : multi_strategy,
    'exchange': 'EXMPL',
    'currency': 'CUR'
}