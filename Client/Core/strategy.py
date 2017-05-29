""" Handles data storage and decision making

Copyright (c) Cambridge Quantum Computing ltd. All rights reserved.  
Licensed under the Attribution-ShareAlike 4.0 International. See LICENSE file
in the project root for full license information.  

"""
from abc import abstractmethod, ABCMeta
class Strategy(ABCMeta):
    """
    Data storage and handling approaches can vary wildly, so we aim to provide
    a flexible way of allowing users of TArrow to handle data in their own way.

    This strategy class is our way of doing this. Users can customise how new
    bars are handled, and how decisions are made. The rest is handled by TArrow.
    """
    @abstractmethod
    def add_record(self, record):
        pass
    @abstractmethod
    def decide(self):
        """ Return 1 to go long, -1 to go short, 0 to do nothing. """
        pass

class MultiStrategy(Strategy):
    """
    Combine multiple strategies with a vote-like system.
    """
    def __init__(self, child_strategies, minimal_agreement):
        assert hasattr(child_strategies, '__iter__'), "child_strategies must be iterable"
        assert minimal_agreement > 0, "minimal_agreement must be greater than zero"
        self.child_strategies = child_strategies
        self.minimal_agreement = minimal_agreement
    def add_record(self, record):
        """ Add the bar to all child strategies """
        for strategy in self.child_strategies:
            strategy.add_record(record)
    def decide(self):
        """ Tally the decisions made by the child strategies.
        If the majority is greater than self.minimal_agreement,
        it is used as the final decision. """
        total = 0
        for strategy in self.child_strategies:
            total += strategy.decide()
        if abs(total) >= self.minimal_agreement:
            return total / abs(total)
        return 0

class NullStrategy(Strategy):
    """
    A strategy that does nothing. It is the default in the stock class.
    """
    def add_record(self, record):
        pass
    def decide(self):
        return 0

# Example strategy. Far too naive for real use.

from collections import deque
class MovingAverageStrategy(ABCMeta):
    """
    A simply moving average strategy.

    If the moving average price over a small period of time overtakes
    that over a long period of time, it is a sign that the price is
    trending upwards, and a 'go long' position is taken. In the opposite
    situation, a 'go short' position is taken. If the average over the smaller
    period of time remains on the same side of the larger time average, then
    no action is taken.
    """
    def __init__(self, small_timespan, large_timespan):
        assert self.small_timespan < self.large_timespan, "small_timespan must be smaller than large_timespan"
        assert self.small_timespan > 0, "timespans must be greater than zero minutes"

        self.small_timespan = small_timespan
        self.large_timespan = large_timespan
        self.small_large_ratio = None
        self.prices = deque(maxlen=self.large_timespan)
    
    def add_record(self, record):
        """ Here we choose to average over the OHLC bar """
        self.prices.append((record.Open + record.Close + record.High + record.Low) / 4)
    
    def decide(self):
        if len(self.prices) < self.large_timespan:
            # not enough price history, do nothing
            return 0
        new_large_average = sum(self.prices) / self.large_timespan
        new_small_average = sum(self.prices[:-self.small_timespan]) / self.small_timespan
        if self.small_large_ratio is not None:
            old_small_large_ratio = self.small_large_ratio
            self.small_large_ratio = new_small_average / new_large_average
            if self.small_large_ratio > 1 and old_small_large_ratio < 1:
                # the price is increasing, go long
                return 1
            elif self.small_large_ratio < 1 and old_small_large_ratio > 1:
                # the price is falling, go short
                return -1
            else:
                return 0