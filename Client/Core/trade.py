""" Handles logic for individual trades, including safety features (e.g. stop loss)

Copyright (c) Cambridge Quantum Computing ltd. All rights reserved.  
Licensed under the Attribution-ShareAlike 4.0 International. See LICENSE file
in the project root for full license information.  

"""
from enum import Enum
from .loggable import Loggable

class TradeState(Enum):
    OPEN = 1
    CLOSED = 2
    OPENING = 3
    CLOSING = 4
    FAILED = 5

class Trade(Loggable):
    def __init__(self, stock, shares, action):
        # Create a trade for a given stock, shares, and action (1 for long, -1 for short)
        self.stock = stock
        self.action = action
        self.shares = shares
        self.status = None
        self.open_price = None
        self.close_price = None
        self.percent_return = None
        self.profit = None
    
    def open(self):
        self.status = TradeState.OPENING
        self.open_time = self.stock.current_time
        self.stock.handleOpenOrder(self)
        self.stock.signaller.startOrder(self.stock, self)
        self.report("Trade open triggered at {:s}".format(str(self.stock.current_time)))
        self.report("\tShares : {:d}".format(self.shares * self.action))
        self.report("\tRough price : {:.3f}".format(self.stock.current_bar.close))

    def close(self):
        # Close the trade
        self.status = TradeState.CLOSING
        self.close_time = self.stock.current_time
        self.stock.handleCloseOrder(self)
        self.stock.signaller.closeOrder(self.stock, self)
        self.report("Trade close triggered at {:s}".format(str(self.stock.current_time)))
        self.report("\tShares : {:d}".format(self.shares * self.action))
        self.report("\tOpen price : {:.3f}".format(self.open_price))
        self.report("\tRough close price : {:.3f}".format(self.stock.current_bar.close))

    def openSuccess(self, share_price):
        # This is called by the Stock object the minute after a trade has been opened.
        # It allows for a good approximation of the trade opening price utilising the
        # open of the next bar.
        self.status = TradeState.OPEN
        self.open_price = share_price
        self.report("Trade from {:s} has updated information", self.stock.current_time)
        self.report("\tShares : {:d}".format(self.shares * self.action))
        self.report("\tPrice  : ${:.3f} / share".format(self.open_price))
        self.report("\tTotal  : ${:.3f}".format(self.open_price*self.shares*self.action))

    def closeSuccess(self, share_price):
        # This is called by the Stock object the minute after a trade has closed, allowing for a
        # better approximation of the return by using the next minute's Open.
        self.status = TradeState.CLOSED
        self.close_price = share_price
        self.percent_return = ((self.close_price / self.open_price)-1) * self.action
        self.profit = (self.close_price - self.open_price) * self.shares * self.action

        self.report("Closed trade at", self.stock.current_time)
        self.report("\tStarted :", self.open_time)
        self.report("\tShares :", self.shares * self.action)
        self.report("\tOpen   : $%.2f / share" % self.open_price)
        self.report("\tClose  : $%.2f / share" % self.close_price)
        self.report("\tprofit : $%.3f" % self.profit)
        self.report("\tReturn : %.4f%%\n" % (100 * self.percent_return))
    
    def getLogTag(self):
        return "Trade - {:s}".format(self.stock.symbol)