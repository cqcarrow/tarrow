""" This contains the Stock class, used to handle a specific stock in a trading scenario.

Copyright (c) Cambridge Quantum Computing ltd. All rights reserved.  
Licensed under the Attribution-ShareAlike 4.0 International. See LICENSE file
in the project root for full license information.  

"""
import datetime

from .trade import Trade
from .signals import NullHandler

class Stock:
    def __init__(self, gateway, stockJSON):
        # The Gateway object that bridges this stock class and the server
        # interface
        self.gateway = gateway
        # The signaller, which is used to communicate orders when they are
        # made.
        self.signaller = NullHandler()
        # Stock symbol and exchange.
        self.symbol = stockJSON['Symbol']
        self.exchange = stockJSON['Exchange']
        # backtesting parameters
        self.is_backtest = False
        self.backtest_date = None
        # These are parameters that are set by the settings files, but they
        # generally handle trading logic:
        self.trade_amount = 1000
        # How many minutes of data are needed before the trading strategy can be used
        self.minutes_backward = 30
        # How many minutes to keep a trade open
        self.minutes_forward = 30
        # individual trade safety feature properties.
        self.stop_loss_threshold = 100  # 10,000% - never reached
        self.take_gain_threshold = 100  # 10,000% - never reached
        # Propeties that describe the current state of the Stock (e.g. last bar, time)
        self.current_bar = None
        self.current_time = None
        self.previous_time = None
        self.trades = []
        self.open_orders = {}
        self.close_orders = {}
        self.unique_id = 0

    def load(self):
        # load any past data
        pass
    
    def analyse(self):
        # Here any pre-market analysis can be done and used later on
        self.report("Loading is complete\n\n")

    def hasOpenTrades(self):
        return any(t.status for t in reversed(self.trades))

    def getCurrentTrades(self):
        return [t for t in self.trades if t.status is True]

    def addLivePriceBar(self, price_bar):
        self.adjustBarTime(price_bar, adjustTimeZone)
        self.report("Received price bar: ", price_bar)
        self.previous_time = self.current_time
        self.current_bar = price_bar
        self.current_time = self.current_bar.time
        self.processNewBar()

    def adjustBarTime(self, price_bar, doAdjust=True):
        # Bar datetimes can come in different formats. This
        # tries to catch several formats in one go.
        if len(price_bar.time) == 17:
            price_bar.time = datetime.datetime.strptime(price_bar.time, "%Y%m%d %H:%M:%S")
        elif len(price_bar.time) == 18:
            price_bar.time = datetime.datetime.strptime(price_bar.time, "%Y%m%d  %H:%M:%S")
        else:
            # Catch-all for both Y/m/d and Y-m-d formats
            price_bar.time = price_bar.time.replace("/", "-")
            price_bar.time = datetime.datetime.strptime(
                price_bar.time, "%Y-%m-%d %H:%M:%S")

        if doAdjust and not self.is_backtest:
            price_bar.time += self.time_offset
    
    def processNewBar(self):
        # first, make a decision on whether to trade
        self.makeDecision()

        # if any trades are in a state of opening,
        # use the current pricebar's open as a rough estimate
        # of the trade price. 
        if len(self.open_orders) + len(self.close_orders) > 0:
            order_ids = list(self.open_orders) + list(self.close_orders)
            for order_id in order_ids:
                self.setOrderFilled(order_id, None, self.current_bar.open)

        for trade in self.getCurrentTrades():
            if trade.close_time <= self.current_time:
                trade.close()
            else:
                trade.runSafetyFeatures()
        # run any safety features global to the stock
        self.runSafetyFeatures()
        
    def runSafetyFeatures(self):
        # Here you can handle any stock-wide safety checks, such as an overall stop loss.
        pass
    
    def makeDecision(self):
        # Here you can use self.current_bar to determine whether or not
        # to make a trade. If you do want to make a trade, send the prediction
        # (1: Buy, -1: Sell) to:
        #    self.startOrder(prediction)
        pass

    # Here are some simple order simulators. When an order is created, start a trade with
    # a number of shares and direction. The actual trading price is determined by the next bar.
    def startOrder(self, buyOrSell):
        current_price = self.current_bar.close
        shares = int(self.trade_amount * 100) // int(current_price * 100)
        self.trades.append(Trade(self, shares, buyOrSell))
    # Pass the order to the gateway and register the trade to receive the price at the next bar
    def handleOpenOrder(self, trade, shares, action):
        order_id = self.gateway.makeOrder(self, shares * action)
        self.open_orders[order_id] = trade
    def handleCloseOrder(self, trade, shares, action):
        order_id = self.gateway.makeOrder(self, shares * -action)
        self.close_orders[order_id] = trade
    def addOrder(self, shares):
        self.unique_id += 1
        return self.unique_id
    # This can be used either from the gateway or from this class itself, depending
    # on whether you're doing a simple simulation or a real-life trade.
    def setOrderFilled(self, order_id, amountFilled, averagePrice):
        if order_id in self.open_orders:
            self.open_orders[order_id].openSuccess(averagePrice)
            del self.open_orders[order_id]
        elif order_id in self.close_orders:
            self.close_orders[order_id].closeSuccess(averagePrice)
            del self.close_orders[order_id]


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
