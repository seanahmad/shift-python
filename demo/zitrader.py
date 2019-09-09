import getopt
import math
import numpy
import shift
import sys
import time

import goodcbfs

from credentials import my_username, my_password


def usage():
    print()
    print("USAGE: zitrader.py [options] <args>")
    print()
    print("OPTIONS:")
    print("-h [ --help ]            produce help message")
    print("-n [ --number ] arg      client ID number")
    print("-t [ --ticker ] arg      stock ticker (e.g. XYZ)")
    print("-d [ --duration ] arg    duration of simulation (in minutes)")
    print("-r [ --rate ] arg        number of trader per simulation session")
    print("-p [ --price ] arg       initial price")
    print("-c [ --change ] arg      minimum dollar change (e.g. 0.01)")
    print("-v [ --verbose ]         verbose mode")
    print()


def main(argv):
    stock_ticker = "AAPL"  # stock ticker (e.g. XYZ)
    simulation_duration = 380  # duration of simulation (in minutes)
    trading_rate = 190  # number of trader per simulation session
    initial_price = 100.00  # initial price
    minimum_dollar_change = 0.05  # minimum dollar change (e.g. 0.01)
    verbose = False  # verbose mode

    try:
        opts, args = getopt.getopt(
            argv,
            "ht:d:r:p:c:v",
            ["help", "ticker=", "duration=", "rate=", "price=", "change=", "verbose"],
        )
    except getopt.GetoptError as e:
        # print help information and exit:
        print()
        print(e)  # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-t", "--ticker"):
            stock_ticker = str(a)
        elif o in ("-d", "--duration"):
            simulation_duration = int(a)
        elif o in ("-r", "--rate"):
            trading_rate = int(a)
        elif o in ("-p", "--price"):
            initial_price = float(a)
        elif o in ("-c", "--change"):
            minimum_dollar_change = float(a)
        elif o in ("-v", "--verbose"):
            verbose = True
        else:
            assert False, "unhandled option"

    last_price = initial_price

    # confidence level: 1, 2, 3, or 4
    confidence_level = int(numpy.random.randint(low=1, high=5))
    # risk appetite: 1, 2, 3, or 4
    risk_appetite = int(numpy.random.randint(low=1, high=5))
    if verbose:
        print()
        print(f"Confidence Level: {confidence_level}")
        print(f"Risk Appetite: {risk_appetite}")
        print()

    num_trades = numpy.random.poisson(lam=trading_rate)
    trading_times = set()

    trading_times.add(0)
    for i in range(num_trades):
        trading_times.add(
            round(
                simulation_duration
                * 60
                * float(numpy.random.uniform(low=0.0, high=1.0))
            )
        )
    trading_times.add(simulation_duration * 60)

    # sort trading times
    trading_times = list(trading_times)
    trading_times.sort()

    # update num_trades taking bend and end of simulation into consideration
    num_trades = len(trading_times)

    # create trader object
    trader = shift.Trader(my_username)

    # attach callback functors
    # trader.onLastPriceUpdated(goodcbfs.LastPriceUpdatedCB(stock_ticker, verbose))
    # trader.onExecutionUpdated(goodcbfs.ExecutionUpdatedCB(verbose))
    # trader.onPortfolioSummaryUpdated(goodcbfs.PortfolioSummaryUpdatedCB(verbose))
    # trader.onPortfolioItemUpdated(goodcbfs.PortfolioItemUpdatedCB(verbose))
    # trader.onWaitingListUpdated(goodcbfs.WaitingListUpdatedCB(verbose))

    # connect
    try:
        trader.connect("initiator.cfg", my_password)
    except shift.IncorrectPassword as e:
        print(e)
        sys.exit(2)
    except shift.ConnectionTimeout as e:
        print(e)
        sys.exit(2)

    # subscribe to all available order books
    trader.subAllOrderBook()

    # trading strategy
    for i in range(1, num_trades):  # trading_times[0] == 0
        time.sleep(trading_times[i] - trading_times[i - 1])

        if verbose:
            print()
            print(f"Trading Time: {trading_times[i]}")

        # cancel last order if it has not executed yet
        if trader.getWaitingListSize() > 0:
            if verbose:
                print("Canceling Pending Orders!")
            trader.cancelAllPendingOrders()
            # for order in trader.getWaitingList():
            #     trader.submitCancellation(order)
            # while trader.getWaitingListSize() > 0:
            #     time.sleep(1)

        # robot should not trade anymore
        if i == (num_trades - 1):
            break

        target_rate = float(numpy.random.uniform(low=0.0, high=0.25 * confidence_level))
        if verbose:
            print(f"Target Rate: {target_rate}")

        curr_last_price = trader.getLastPrice(stock_ticker)
        last_price = last_price if curr_last_price == 0.0 else curr_last_price

        if numpy.random.binomial(n=1, p=0.5) == 0:  # limit buy

            best_bid = trader.getBestPrice(stock_ticker).getBidPrice()
            best_bid = best_bid if best_bid != 0.0 else last_price

            target_price = min(last_price, best_bid)
            if verbose:
                print(f"Last Price: {last_price:.2f}")
                print(f"Best Bid: {best_bid:.2f}")
                print(f"Target Price: {target_price:.2f}")

            order_price = round(
                target_price
                + minimum_dollar_change
                * float(numpy.random.normal(loc=0.0, scale=(0.5 * risk_appetite))),
                2,
            )
            if verbose:
                print(f"Bid Price: {order_price:.2f}")

            order_size = math.floor(
                (target_rate * trader.getPortfolioSummary().getTotalBP())
                / (100 * order_price)
            )
            if verbose:
                print(f"Bid Size: {order_size}")

            limit_buy = shift.Order(
                shift.Order.LIMIT_BUY, stock_ticker, order_size, order_price
            )
            trader.submitOrder(limit_buy)

        else:  # limit sell

            best_ask = trader.getBestPrice(stock_ticker).getAskPrice()
            best_ask = best_ask if best_ask != 0.0 else last_price

            target_price = max(last_price, best_ask)
            if verbose:
                print(f"Last Price: {last_price:.2f}")
                print(f"Best ask: {best_ask:.2f}")
                print(f"Target Price: {target_price:.2f}")

            order_price = round(
                target_price
                + minimum_dollar_change
                * float(numpy.random.normal(loc=0.0, scale=(0.5 * risk_appetite))),
                2,
            )
            if verbose:
                print(f"Ask Price: {order_price:.2f}")

            order_size = math.floor(
                target_rate * (trader.getPortfolioItem(stock_ticker).getShares() / 100)
            )
            if verbose:
                print(f"Ask Size: {order_size}")

            limit_sell = shift.Order(
                shift.Order.LIMIT_SELL, stock_ticker, order_size, order_price
            )
            trader.submitOrder(limit_sell)

        if verbose:
            print()

    # disconnect
    trader.disconnect()


if __name__ == "__main__":
    main(sys.argv[1:])
