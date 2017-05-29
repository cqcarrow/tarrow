""" Handles logic for individual trades, including safety features (e.g. stop loss)

Copyright (c) Cambridge Quantum Computing ltd. All rights reserved.  
Licensed under the Attribution-ShareAlike 4.0 International. See LICENSE file
in the project root for full license information.  

"""
import sys
import datetime
class TradeMonitor:
    """ Used for monitoring open positions and determining when it is time to
    close them. This could be due to a timed position of n minutes, or because
    of a stop loss, or any monitoring tactic you want. """
    def notify_single(self, trade, current_bar):
        """ Monitor a single trade given the current bar. This is useful for
        checking trade-specific metrics such as the current return or trading
        length. True is returned if the trade should remain open, False if it
        should be closed.
        """
        return True
    def notify_multiple(self, open_trades, closed_trades, current_bar):
        """ Monitor all trades opened so far, including closed trades.
        This is useful for multi-trade metrics, such as the overall return
        so far in the day (e.g. for a daily stoploss to shut down all open
        trades).
        """
        raise NotImplementedError("Multiple trade monitoring is not yet implemented")

    def report(self, *arg):
        print(
            "{:s} ~ {:s} > ".format(
                str(datetime.datetime.now())[:23],
                self.__class__.__name__
            ),
            *arg
        )
        sys.stdout.flush()

class MultiTradeMonitor(TradeMonitor):
    def __init__(self, child_trade_monitors):
        self.child_trade_monitors = child_trade_monitors
    def notify_single(self, trade, current_bar):
        """ Run the child monitors on the trades. If one closes an order,
        it should return False to prevent other monitors from wasting time
        on it. """
        for monitor in self.child_trade_monitors:
            if not monitor.notify_single(trade, current_bar):
                return False
            return True
    def notify_multiple(self, open_trades, closed_trades, current_bar):
        for monitor in self.child_trade_monitors:
            monitor.notify_multiple(open_trades, closed_trades, current_bar)

class NullTradeMonitor(TradeMonitor):
    pass

class BoundaryTradeMonitor(TradeMonitor):
    def __init__(self, stop_loss_bp=None, take_profit_bp=None):
        self.stop_loss_bp = stop_loss_bp
        self.take_profit_bp = take_profit_bp
    def notify_single(self, trade, current_bar):
        current_return_bp = ((current_bar.close / trade.close_price) - 1) * 10000
        if -current_return_bp > self.stop_loss_bp:
            #fire stop loss
            self.report("Stop loss triggered")
            return False
        elif current_return_bp > self.take_profit_bp:
            self.report("Take profit triggered")
            return False
        return True

class TimeLimitTradeMonitor(TradeMonitor):
    def __init__(self, time_limit):
        self.timedelta = datetime.timedelta(minutes=time_limit)
    def notify_single(self, trade, current_bar):
        if trade.open_time + self.timedelta >= current_bar.time:
            self.report("Time limit triggered")
            return False
        return True
