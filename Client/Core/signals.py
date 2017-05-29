""" This module contains the signalling classes used to transmit an order.

Copyright (c) Cambridge Quantum Computing ltd. All rights reserved.  
Licensed under the Attribution-ShareAlike 4.0 International. See LICENSE file
in the project root for full license information.  

"""
from .loggable import Loggable
from abc import ABCMeta, abstractmethod

class Handler(ABCMeta, Loggable):
    """ Generic abstract class defining the methods that a signaller requires """
    @abstractmethod
    def initialise(self):
        """ The main handling process will create an instance of each signaller. This
        might not be ideal if e.g. the receiver can only accept a single connection,
        so we place the physical connection commands into this method so that no connections
        are made by the main handling process. Must have protection such that it is only 
        run once. """
        pass
    @abstractmethod
    def startOrder(self, stock, trade):
        """ Transmit an order for a stock, with an action and time """
        #Signal the start of an order
        pass
    @abstractmethod
    def closeOrder(self, stock, trade):
        """ Transmit a closing signal for a stock, with a time """
        #Close an order
        pass
    @abstractmethod
    def closeAll(self, stock, time):
        """ Transmit a signal to close all open orders on a stock """
        #Close all orders
        pass
    def flush(self):
        """ Flush any transmissions.
        This is called after all stocks have been processed, and is useful
        for methods that may introduce a lag.
        """
        # useful for signalling methods that introduce latency
        pass
    def getLogTag(self):
        return self.__class__.__name__



class MultiHandler(Handler):
    """ A combined handler, allowing multiple signalling objects to be combined.
    When a method is called, it fires the same method on all of the contained
    child handlers.
    """
    def __init__(self, child_handlers):
        """ Create a MultiHandler with a list of child handlers, each of which will be
        invoked when an order is made
        """
        self.handlers = child_handlers
    def initialise(self):
        for handler in self.handlers:
            handler.initialise()
    def startOrder(self, stock, trade):
        for handler in self.handlers:
            handler.startOrder(stock, trade)
    def closeOrder(self, stock, trade):
        for handler in self.handlers:
            handler.closeOrder(stock, trade)
    def closeAll(self, stock, time):
        for handler in self.handlers:
            handler.closeAll(stock, time)
    def flush(self):
        for handler in self.handlers:
            handler.flush()

class NullHandler(Handler):
    """ Sends no signals, useful for a stand-in when no signalling is required """
    def startOrder(self, stock, trade):
        pass
    def closeOrder(self, stock, trade):
        pass
    def closeAll(self, stock, time):
        pass
    def initialise(self):
        pass

class BacktestSignaller(NullHandler):
    """ Used for backtesting. What this class does depends on how backtests
    should be handled. At current, it prints out the orders to the terminal.
    """
    def startOrder(self, stock, trade):
        self.report("--- simulated signal ---")
        self.report("Start Order")
        self.report("Action: {:s}".format("Buy" if trade.action == 1 else "Sell"))
        self.report("Time  : {:s}", str(trade.open_time))
    def closeOrder(self, stock, trade):
        self.report("--- simulated signal ---")
        self.report("Closing Order")
        self.report("Time  : {:s}", str(trade.close_time))
    def closeAll(self, stock, time):
        self.report("--- simulated signal ---")
        self.report("Closing ALL orders")