# [![tarrow](./logo/logo_70.png)](https://github.com/cqcarrow/tarrow) [TArrow Trading Interface](https://github.com/cqcarrow/tarrow)
TA> is a cross-platform trading interface developed by Cambridge Quantum Computing. TA> was built in Python resulting in both speed and adaptability. 
TA> has been under development at [Cambridge Quantum Computing](http://www.cambridgequantum.com/) since 2016.

## Core features
Based on our own in-house trading interface, which runs on minute-by-minute price bars, this open-source platform is centred around flexibility:
* Price feeds can easily be integrated into TA> through JSON messaging over ZMQ, and a backtesting price server is provided.
* Decision logic can be easily integrated into our strategy classes, which allow combined strategies for extra confidence.
* Trading positions can be signalled through a flexible signaller interface.
* Once positions have been opened, their current status can be monitored every minute, allowing implementation of stoplosses, timeouts, and other features.
* A reporting interface is given, allowing e.g. regular email reports
* Our core process, provided in Client/run.py, manages the splitting of stocks groups into several, separate, processes. Their standard logs and error logs are split into separate files to allow for easy navigation and live monitoring of TA>'s status.
* Our unified logging interface is designed to be as meaningful as possible. Datetimes are provided in millisecond accuracy, and the source of each log message is provided.

## Efficiency
As well as aiming for flexibility, TA> is designed to be lightweight. For extra speed and efficiency, we recommend wrapping trading
logic classes around C++ classes using a popular cross-language wrapper such as SWIG or Cython where possible.

## Future Input
As well as supplying the skeleton of TA>, we will be working on some examples to make your integration process smoother. We will also provide, where possible, integrated server applications for several popular pricefeeds, getting you a big step closer to using TA> on a live trading platform with minimal effort.