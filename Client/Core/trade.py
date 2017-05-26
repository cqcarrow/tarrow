""" Handles logic for individual trades, including safety features (e.g. stop loss)

Copyright (c) Cambridge Quantum Computing ltd. All rights reserved.  
Licensed under the Attribution-ShareAlike 4.0 International. See LICENSE file
in the project root for full license information.  

"""
import datetime
class Trade:
    def __init__(self, stock, shares, action):
        # Create a trade for a given stock, shares, and action (1 for long, -1 for short)
        self.stock = stock
        self.action = action
        self.shares = shares
        self.status = False
        self.open_time = self.stock.current_time
        self.close_time = self.open_time + datetime.timedelta(minutes=self.stock.minutes_forward)
        self.close_asap = False
        self.open_price = None
        self.close_price = None
        self.percent_return = None
        self.profit = None
        self.stock.handleOpenOrder(self, self.shares, self.action)
        self.stock.signaller.startOrder(self.stock, self)


    def runSafetyFeatures(self):
        # Monitor the trade, closing if necessary
        if not self.status:
            return

        if self.close_asap:
            self.close()

        if not self.checkStopLoss(self.stock.stop_loss_threshold):
            return

        if not self.checkTakeprofit(self.stock.take_gain_threshold):
            return

    def checkStopLoss(self, threshold):
        # Has the current trade reached its stop loss limit? If so, close the position.
        if threshold is None:
            return True

        current_price = self.stock.current_bar.close
        trade_price = self.open_price

        loss_percentage = (1 - current_price / trade_price) * self.action
        if loss_percentage > threshold:
            self.stock.report(
                "Stop loss on stock", self.stock.symbol,
                "at", self.stock.current_bar.time
            )
            self.stock.report("\tPrice at trade : $%.3f" % trade_price)
            self.stock.report("\tPrice now      : $%.3f" % current_price)
            self.stock.report("\tLoss           : %.3f%%" % (loss_percentage * 100))
            self.close()
            return False
        else:
            return True

    def checkTakeprofit(self, threshold):
        # Has the current trade reached its stop loss limit? If so, close the position.
        if threshold is None:
            return True

        current_price = self.stock.current_bar.close
        trade_price = self.open_price

        gain_percentage = (current_price / trade_price - 1) * self.action
        if gain_percentage > threshold:
            self.stock.report(
                "Take gain on stock", self.stock.symbol,
                "at", self.stock.current_bar.time
            )
            self.stock.report("\tPrice at trade : $%.3f" % trade_price)
            self.stock.report("\tPrice now      : $%.3f" % current_price)
            self.stock.report("\tGain           : %.3f%%" % (gain_percentage * 100))
            self.close()
            return False
        else:
            return True

    def openSuccess(self, share_price):
        # This is called by the Stock object the minute after a trade has been opened. It allows for a
        # good approximation of the trade opening price utilising the open of the next bar.
        self.status = True
        self.open_price = share_price
        self.stock.report("Opened order at", self.stock.current_bar.time)
        self.stock.report("\tShares : %d" % (self.shares * self.action))
        self.stock.report("\tPrice  : $%.2f per share" % self.open_price)
        self.stock.report("\tTotal  : $%.2f\n" % (self.open_price*self.shares*self.action))
        
    def close(self):
        # Close the trade
        self.close_time = self.stock.current_time
        if self.status is True:
            self.stock.handleCloseOrder(self, self.shares, self.action)
        else:
            self.close_asap = True
        self.stock.signaller.closeOrder(self.stock, self)

    def closeSuccess(self, share_price):
        # This is called by the Stock object the minute after a trade has closed, allowing for a
        # better approximation of the return by using the next minute's Open.
        self.status = False
        self.close_price = share_price
        self.percent_return = ((self.close_price / self.open_price)-1) * self.action
        self.profit = (self.close_price - self.open_price) * self.shares * self.action

        self.stock.report("Closed trade at", self.stock.current_bar.time)
        self.stock.report("\tStarted :", self.open_time)
        self.stock.report("\tShares :", self.shares * self.action)
        self.stock.report("\tOpen   : $%.2f / share" % self.open_price)
        self.stock.report("\tClose  : $%.2f / share" % self.close_price)
        self.stock.report("\tprofit : $%.3f" % self.profit)
        self.stock.report("\tReturn : %.4f%%\n" % (100 * self.percent_return))