""" Create an set of stocks (input by symbol) and open communications
between them and the server via the Gateway.

Copyright (c) Cambridge Quantum Computing ltd. All rights reserved.  
Licensed under the MIT License. See LICENSE file
in the project root for full license information.  

"""
import sys
import datetime
import smtplib
import copy
import importlib

from .gateway import Gateway
from .pricebar import PriceBar

class Controller:
    """ Responsible for managing a set of stocks in one process.
    """
    def __init__(self, version, environment, global_settings, client_id, symbols):
        self.version = version
        self.environment = environment
        self.gateway = Gateway()
        self.account = self.gateway.getAccounts()[0]
        self.stocks = {}
        self.new_bars = {}
        self.global_settings = global_settings
        self.loadStocks(symbols)

        if "reporter" not in global_settings:
            global_settings["reporter"] = NullReporter()

        self.reporter = global_settings["reporter"]
        self.reporter.initiate(version, environment, client_id)

    def loadStock(self, symbol, exchange, currency):
        self.report("Getting stock {:s} from gateway".format(symbol))
        return self.gateway.getStock(
            self.account,
            symbol,
            exchange,
            currency
        )

    def loadStocks(self, symbols):
        for symbol in symbols:
            stock_settings = self.getStockSettings(symbol)
            stock = self.loadStock(
                symbol,
                stock_settings['exchange'],
                stock_settings['currency']
            )
            for option_name in stock_settings:
                if not hasattr(stock, option_name):
                    self.report(
                        "Warning: attribute {:s} hasn't got a default value".format(
                            option_name
                        )
                    )
                setattr(stock, option_name, stock_settings[option_name])
            self.report("Initiating signallers")
            stock.signaller.initialise()
            # now we store the stock object in self.stocks, referenced by its
            # symbol.
            self.stocks[symbol] = stock

    def getStockSettings(self, symbol):
        self.report("getting settings for {:s}".format(symbol))
        # Create a shallow copy of settings so that settings can be overwritten by each stock.
        stock_settings = copy.copy(self.global_settings)
        self.report("after copy")
        self.report("copied settings for {:s}".format(symbol))
        self.report("loading version file for {:s}".format(symbol))
        try:
            # try to load the generic index file for the stock
            version_file = importlib.import_module(
                "Versions.{:s}.Stocks.{:s}.index".format(
                    self.version,
                    symbol
                )
            )
            self.report("loaded version file for {:s}".format(symbol))
            stock_settings.update(version_file.settings)
        except Exception as error:
            self.report("Exception type: ", error)
            self.report("Stock file {:s} has no index.py file, continuing anyway".format(
                symbol
            ))
        self.report("loading version file for {:s}".format(symbol))
        try:
            # try to load the environment-specific file for the stock
            environment_file = importlib.import_module(
                "Versions.{:s}.Stocks.{:s}.{:s}".format(
                    self.version,
                    symbol,
                    self.environment
                )
            )
            self.report("loaded environment file for {:s}".format(symbol))
            stock_settings.update(environment_file.settings)
        except Exception as error:
            self.report("Exception type: ", error)
            self.report("Stock file {:s} has no {:s}.py file, continuing anyway".format(
                symbol,
                self.environment
            ))
        # verify that we have the exchange and currency. If not, then
        # we don't have enough information to launch the client.
        if "exchange" not in stock_settings:
            raise ValueError(
                "Stock {:s}'s exchange should be in it's index file or {:s} file".format(
                    symbol,
                    self.environment
                )
            )
        elif "currency" not in stock_settings:
            raise ValueError(
                "Stock {:s}'s currency should be in it's index file or {:s} file".format(
                    symbol,
                    self.environment
                )
            )
        self.report("loaded all settings for {:s}".format(symbol))
        return stock_settings

    def goLive(self):
        # these are done in blocks rather than all-in-one, to allow separate stocks
        # to get to the same stage before moving on
        for symbol in self.stocks:
            # load the stock data from 2012 to the current year
            # (this also performs detection, classification, learning)
            self.report("Loading Stock Data", symbol)
            self.stocks[symbol].load()
        for symbol in self.stocks:
            self.stocks[symbol].analyse()
        for symbol in self.stocks:
            # Grab historical data from the stock. This is just in case
            # this client starts up after the market opens or misses the previous
            # day, etc.
            self.report(
                "Requesting historical data for stock '" + symbol + "'")
            self.stocks[symbol].addHistoricalPriceBars(
                self.gateway.getHistory(self.stocks[symbol])
            )
        for symbol in self.stocks:
            # Subscribe to live market data
            self.report("Requesting live data for stock '" + symbol + "'")
            self.gateway.subscribeToMarketData(self.stocks[symbol])
        self.gateway.finalise()
        # Run the listening loop.
        self.listen()

    def getLogTag(self):
        return "Controller"
    
    def listen(self):
        """ Run the main listening loop, handling responses from the gateway. """
        while True:
            # wait or the gateway to send us something
            listen_input = self.gateway.listen()
            if listen_input["Type"] == "Prepare for Live Bars":
                # PriceBars are going to come in - store them all and process in bulk afterwards,
                # so that the message queue isn't blocked
                self.new_bars = {}
            # We have received a live bar, pass it to the stock.
            elif listen_input["Type"] == "Live Bar":
                # Find the stock based on the returned live data request's ID
                symbol = self.gateway.request_to_stock[listen_input['RequestID']]
                stock = self.stocks[symbol]
                # Pass the new bar to the stock
                self.new_bars[symbol] = PriceBar(listen_input['Bar'])
            elif listen_input["Type"] == "End of Live Bars":
                self.report("All bars are in. Adding them to the stock...")
                for symbol in self.new_bars:
                    self.stocks[symbol].addLivePriceBar(self.new_bars[symbol])
                self.report("Ready to process!")
                for symbol in self.new_bars:
                    self.stocks[symbol].processNewBar()
                    self.current_time = self.stocks[symbol].current_time
                self.report("Done. Flushing signallers.")
                for symbol in self.stocks:
                    self.stocks[symbol].signaller.flush()
                self.reporter.newBars(self, self.current_time)
                # now tell the Arrow Server that we are done processing, for bookkeeping purposes.
                self.gateway.finalise()
            elif listen_input["Type"] == "Server Exit":
                self.report("Server has closed.")
                self.report("Generating complete report.")
                self.report("Trades:", sum(len(self.stocks[symbol].closed_trades) for symbol in self.stocks))
                self.reporter.endOfDay(self)
                sys.exit(0)