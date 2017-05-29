""" This contains the Stock class, used to handle a specific stock in a trading scenario.

Copyright (c) Cambridge Quantum Computing ltd. All rights reserved.  
Licensed under the Attribution-ShareAlike 4.0 International. See LICENSE file
in the project root for full license information.  

"""
import datetime
import sys

from .strategy import NullStrategy
from .trademonitor import NullTradeMonitor
from .signals import NullHandler
from .trade import Trade

class Stock:
    def __init__(self, gateway, symbol, exchange):
        # The Gateway object that bridges this stock class and the server
        # interface
        self.gateway = gateway
        # Stock symbol and exchange.
        self.symbol = symbol
        self.exchange = exchange
        # difference between the timestamp on incoming bars and the market time
        self.time_offset = datetime.timedelta(minutes=0)
        # The strategy, used to handle trading decisions
        self.strategy = NullStrategy()
        # The trade monitor, used to determine when an open trade should be closed
        self.trade_monitor = NullTradeMonitor()
        # The signaller, used to communicate orders.
        self.signaller = NullHandler()
        # backtesting parameters
        self.is_backtest = False
        self.backtest_date = None
        # These are parameters that are set by the settings files, but they
        # generally handle trading logic:
        self.trade_amount = 10000
        # How many minutes to keep a trade open. None for no time limit
        self.trade_length = None
        # individual trade safety feature properties.
        self.stop_loss_threshold = 100  # 10,000% - never reached
        self.take_gain_threshold = 100  # 10,000% - never reached
        # Properties that describe the current state of the Stock (e.g. last bar, time)
        self.current_bar = None
        self.current_time = None
        self.previous_time = None
        self.open_trades = []
        self.closed_trades = []
        self.open_orders = {}
        self.close_orders = {}
        self.unique_id = 0

    def addLivePriceBar(self, price_bar, adjustTimeZone):
        """ When a live price bar is received through the Controller,
        it is passed to this method. It is best to keep processing minimal
        at this stage to allow minimalise blocking of the ZMQ socket. Once
        all stocks' pricebars are in, processNewBar is called, and this
        is where any heavier processing should occur. """
        self.adjustBarTime(price_bar, adjustTimeZone)
        self.report("Received price bar: ", price_bar)
        self.previous_time = self.current_time
        self.current_bar = price_bar
        self.current_time = self.current_bar.time
        self.strategy.add_record(self.current_bar)

    def processNewBar(self):
        # first, make a decision on whether to trade
        decision = self.strategy.decide()
        if decision != 0:
            self.startOrder(decision)

        # if any trades are in a state of opening,
        # use the current pricebar's open as a rough estimate
        # of the trade price. 
        if len(self.open_orders) + len(self.close_orders) > 0:
            order_ids = list(self.open_orders) + list(self.close_orders)
            for order_id in order_ids:
                self.setOrderFilled(order_id, self.current_bar.open)

        """ Monitor open trades for opening and closing purposes. """
        for trade in self.open_trades:
            if not self.trade_monitor.notify_single(trade, self.current_bar):
                trade.close()

    # Here are some simple order simulators. When an order is created, start a trade with
    # a number of shares and direction. The actual trading price is determined by the next bar.
    def startOrder(self, buyOrSell):
        current_price = self.current_bar.close
        shares = int(self.trade_amount * 100) // int(current_price * 100)
        self.open_trades.append(Trade(self, shares, buyOrSell))
    # Register the trade to receive the price at the next bar
    def handleOpenOrder(self, trade):
        self.unique_id += 1
        self.open_orders[self.unique_id] = trade
    
    def handleCloseOrder(self, trade):
        self.unique_id += 1
        self.close_orders[self.unique_id] = trade

    # This can be used either from the gateway or from this class itself, depending
    # on whether you're doing a simple simulation or a real-life trade.
    def setOrderFilled(self, order_id, averagePrice):
        if order_id in self.open_orders:
            self.open_orders[order_id].openSuccess(averagePrice)
            del self.open_orders[order_id]
        elif order_id in self.close_orders:
            self.close_orders[order_id].closeSuccess(averagePrice)
            del self.close_orders[order_id]

    def adjustBarTime(self, price_bar, doAdjust=True):
        # Bar datetimes can come in different formats. This
        # tries to catch several formats in one go.
        time = price_bar.time
        time = time.replace("  ", " ")
        time = time.replace("/", "")
        time = time.replace("-", "")
        price_bar.time = datetime.datetime.strptime(price_bar.time, "%Y%m%d %H:%M:%S")
        if doAdjust and not self.is_backtest:
            price_bar.time += self.time_offset

    def report(self, *arg):
        print(
            "{:s} ~ {:s} > ".format(
                str(datetime.datetime.now())[:23],
                self.symbol
            ),
            *arg
        )
        sys.stdout.flush()

    def reportError(self, *arg):
        print(
            "{:s} ~ {:s} > ".format(
                str(datetime.datetime.now())[:23],
                self.symbol
            ),
            *arg,
            file=sys.stderr
        )
        sys.stderr.flush()
