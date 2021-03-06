import logging
import time
import traceback


class ClosingAlgo(object):
    """
    Algo for closing the existing position using fibonacci lines.
    """
    def __init__(self,api_handler,direction,size,interval="1h",history_bars=24,protect_profit=0.382,maxium_profit=0.618,delta_timegap=3600):
        self.history=history_bars
        self.interval = interval
        self.api = api_handler
        self.protect = protect_profit
        self.maxium = maxium_profit
        self.size=size
        self.max=0
        self.min=0
        self.real_max = 0
        self.real_min = 0
        self.direction = direction
        self.maxium_id = None
        self.reached_protect=False
        self.initial_timestamp = time.time()
        self.disable = False
        self.delta_timegap = 7200


    async def check(self,close=True):
        if self.disable:
            return False
        try:
            histories = await self.api.get_history(self.history,self.interval,incomplete=not close)
            if self.direction =="buy":
                # Completely rewrite this part
                low_timestamp = 0
                high_timestamp = 0
                for kline in histories:
                    if kline["high"] > self.max or self.max == 0:
                        self.max = kline["high"]
                        self.real_max = kline["high"]
                        high_timestamp = kline["timestamp"]
                    if kline["timestamp"]+self.delta_timegap>=self.initial_timestamp and (kline["low"] < self.min or self.min == 0):
                        self.min = kline["low"]
                    if kline["low"] < self.real_min or self.real_min == 0:
                        self.real_min = kline["low"]
                        low_timestamp = kline["timestamp"]
                if high_timestamp<low_timestamp:
                    # high might not be right
                    # Update High
                    self.max = 0
                    for kline in histories:
                        if kline["timestamp"]>=low_timestamp:
                            if kline["high"] > self.max or self.max == 0:
                                self.max = kline["high"]
                                self.real_max = kline["high"]

            elif self.direction == "sell":
                low_timestamp = 0
                high_timestamp = 0

                for kline in histories:
                    if kline["timestamp"]+self.delta_timegap>=self.initial_timestamp and (kline["high"] > self.max or self.max == 0):
                        self.max = kline["high"]
                    if kline["high"] > self.real_max or self.real_max == 0:
                        self.real_max = kline["high"]
                        high_timestamp = kline["timestamp"]
                    if kline["low"] < self.min or self.min == 0:
                        self.min = kline["low"]
                        self.real_min = kline["low"]
                        low_timestamp = kline["timestamp"]
                if low_timestamp< high_timestamp:
                    # low might not be righ
                    # Update low
                    self.min = 0
                    for kline in histories:
                        if kline["timestamp"]>=high_timestamp:
                            if kline["low"] < self.min or self.min == 0:
                                self.min = kline["low"]
                                self.real_min = kline["low"]

            if self.min == 0 or self.max == 0:
                    logging.info("Not enough info for Algo Close, return. Log:")
                    logging.info(histories)
                    logging.info(self.initial_timestamp)
                    return None
            if self.direction=="buy":
                self.protect_price = (self.max-self.min)*self.protect+self.min
                self.maxium_price = (self.max-self.min)*self.maxium+self.min

                if histories[-1]["high"] == self.max and not close:
                    # Buy the dip. No algo close
                    self.disable = True
                    return "TTL"
                middle_price = self.real_max - (self.real_max-self.real_min)*0.386
                if histories[-1]["close"]>middle_price and not close:
                    self.disable = True
                    return "TTL"

            elif self.direction=="sell":
                self.protect_price = self.max - (self.max-self.min)*self.protect
                self.maxium_price = self.max - (self.max-self.min)*self.maxium

                if histories[-1]["low"] == self.min and not close:
                    # Sell the low. No algo close
                    self.disable = True
                    return "TTL"
                middle_price = self.real_min + (self.real_max-self.real_min)*0.386
                if histories[-1]["close"]<middle_price and not close:
                    self.disable = True
                    return "TTL"


            else:
                return
            logging.info("Current Algo prices: 0.386 {} 0.618 {}".format(self.protect_price,self.maxium_price))

            if close:
                # Candle is close, try to check.
                if self.direction=="buy" and histories[-1]["timestamp"]>self.initial_timestamp+3600:
                    if self.reached_protect and histories[-1]["close"]<self.protect_price:
                        # Close position now
                        await self.api.do_short(self.size, self.protect_price, market=True, reduce=True)
                        return True
                    elif histories[-1]["high"]>self.protect_price*1.001 and histories[-1]["close"]<self.protect_price:
                        # Close position now
                        await self.api.do_short(self.size, self.protect_price, market=True, reduce=True)
                        return True
                    # Make sure the Maxium Sell order still there.
                elif self.direction=="sell" and histories[-1]["timestamp"]>self.initial_timestamp+3600:
                    if self.reached_protect and histories[-1]["close"]>self.protect_price:
                        # Close position now
                        await self.api.do_long(self.size, self.protect_price, market=True, reduce=True)
                    elif histories[-1]["low"]<self.protect_price*0.999 and histories[-1]["close"]>self.protect_price:
                        # Close position now
                        await self.api.do_long(self.size, self.protect_price, market=True, reduce=True)
            # Make sure the Maxium Sell order still there.

            if self.maxium_id:
                await self.api.cancel_order(self.maxium_id)
            if self.direction == "buy":
                if histories[-1]["close"] > self.protect_price:
                    self.reached_protect = True
                self.maxium_id = await self.api.do_short(self.size, round(self.maxium_price), market=False, reduce=True)
            elif self.direction=="sell":
                if histories[-1]["close"] < self.protect_price:
                    self.reached_protect = True
                self.maxium_id = await self.api.do_long(self.size, round(self.maxium_price)+1, market=False, reduce=True)
            return self.maxium_id
        except Exception as e:
            traceback.print_exc()
            logging.error("ERROR: AlgoRuner faced issue: {}".format(e))
            print("ERROR: websocket faced issue: {}".format(e))


