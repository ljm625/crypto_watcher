


class ClosingAlgo(object):
    """
    Algo for closing the existing position using fibonacci lines.
    """
    def __init__(self,api_handler,direction,size,interval="1h",history_bars=24,protect_profit=0.382,maxium_profit=0.618):
        self.history=history_bars
        self.interval = interval
        self.api = api_handler
        self.protect = protect_profit
        self.maxium = maxium_profit
        self.size=size
        self.max=0
        self.min=0
        self.direction = direction
        self.maxium_id = None
        self.reached_protect=False


    async def check(self,close=False):
        histories = await self.api.get_history(self.history,self.interval)
        for kline in histories:
            if kline["high"]> self.max or self.max==0:
                self.max=kline["high"]
            if kline["low"]<self.min or self.min==0:
                self.min=kline["low"]
        if self.direction=="BUY":
            self.protect_price = (self.max-self.min)*self.protect+self.min
            self.maxium_price = (self.max-self.min)*self.maxium+self.min
        else:
            self.protect_price = self.max - (self.max-self.min)*self.protect
            self.maxium_price = self.max - (self.max-self.min)*self.maxium

        if close:
            # Try to close the position
            if self.direction=="BUY":
                if self.maxium_id:
                    await self.api.cancel_order(self.maxium_id)
                if self.reached_protect and histories[-1]["close"]<self.protect_price:
                    # Close position now
                    await self.api.do_short(self.size, self.protect_price, market=True, reduce=True)
                    return True
                elif histories[-1]["high"]>self.protect_price*1.001 and histories[-1]["close"]<self.protect_price:
                    # Close position now
                    await self.api.do_short(self.size, self.protect_price, market=True, reduce=True)
                    return True
                elif histories[-1]["close"]>self.protect_price:
                    self.reached_protect=True
                # Make sure the Maxium Sell order still there.
                self.maxium_id = await self.api.do_short(self.size,self.maxium_price,market=False,reduce=True)
                return self.maxium_id
            else:
                if self.maxium_id:
                    await self.api.cancel_order(self.maxium_id)
                if self.reached_protect and histories[-1]["close"]>self.protect_price:
                    # Close position now
                    await self.api.do_long(self.size, self.maxium_price, market=True, reduce=True)

                elif histories[-1]["low"]<self.protect_price*0.999 and histories[-1]["close"]>self.protect_price:
                    # Close position now
                    await self.api.do_long(self.size, self.maxium_price, market=True, reduce=True)
                elif histories[-1]["close"]<self.protect_price:
                    self.reached_protect=True
                # Make sure the Maxium Sell order still there.
                self.maxium_id = await self.api.do_long(self.size,self.maxium_price,market=False,reduce=True)
                return self.maxium_id
        else:
            return None

