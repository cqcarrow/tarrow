"""

Copyright (c) Cambridge Quantum Computing ltd. All rights reserved.  
Licensed under the MIT License. See LICENSE file
in the project root for full license information.  

"""

class PriceBar:
    """ Represents a pricebar from gateway """
    def __init__(self, bar_dict):
        """ Create a pricebar from a dictionary
        The dictionary should contain Time, Open,
        Close, High, Low, and Volume as keys.
        """
        self.time = bar_dict['Time']
        self.open = bar_dict['Open']
        self.close = bar_dict['Close']
        self.high = bar_dict['High']
        self.low = bar_dict['Low']
        self.volume = bar_dict['Volume']

    def __repr__(self):
        """ Get the string representation of the pricebar """
        return str(self.time)  + "," + \
               str(self.open)  + "," + \
               str(self.high)  + "," + \
               str(self.low)   + "," + \
               str(self.close) + "," + \
               str(self.volume)
