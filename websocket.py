import json

import websockets
import asyncio

from argparse import Namespace
args = Namespace(
    bfx_price=0,
    binance_price=0,
    balance=2000,
    position= [],
    capital_bfx= 1000,
    capital_binance= 1000,
    amount = 100,
    open_rate = 0.0015,
    close_rate = 0.0002,
    loss_threshold = -15
)


async def opportunity_finder():
    while True:
        if args.bfx_price!=0 and args.binance_price!=0:
            avg_price= (args.bfx_price+args.binance_price)/2
            price_gap = float(abs(args.bfx_price-args.binance_price))
            gap = price_gap/avg_price
            print("Current GAP : {}%".format(gap*100))
            if gap>= args.open_rate:
                print("Current Price {} {}, differ {}%".format(args.bfx_price,args.binance_price,gap*100))
                coro = paper_trader()
                asyncio.ensure_future(coro)
        print("Balance : {} Bitfinex: {} Binance: {}".format(args.balance,args.capital_bfx,args.capital_binance))
        await asyncio.sleep(10)

    pass


async def paper_trader():
    if args.balance <= 0 :
        print("No Extra Money yet.")
        return
    if args.bfx_price>args.binance_price and args.capital_bfx> args.amount and args.capital_binance> args.amount:
        pos ={
            "buy":"binance",
            "sell":"bfx",
            "buy_price":args.binance_price,
            "sell_price":args.bfx_price,
            "amount": float(args.amount)/args.binance_price
        }
        args.position.append(pos)
        print(pos)
        args.capital_bfx = args.capital_bfx - float(pos["amount"])*args.bfx_price
        args.capital_binance = args.capital_binance - args.amount
        args.balance = args.capital_bfx+args.capital_binance
        while True:
            profit = (args.binance_price-pos["buy_price"])*pos["amount"]+(pos["sell_price"]-args.bfx_price)*pos["amount"]
            print("Current Profit: {}".format(profit))
            avg_price= (args.bfx_price+args.binance_price)/2
            price_gap = float(args.bfx_price-args.binance_price)
            gap = price_gap/avg_price

            if gap<= args.close_rate:
                print("Closing Position")
                print("Profit: {}".format(profit))
                args.capital_binance = args.binance_price*pos["amount"]+args.capital_binance
                args.capital_bfx = (pos["sell_price"] -args.bfx_price)*pos["amount"] + pos["sell_price"]*pos["amount"] +args.capital_bfx
                args.balance = args.capital_bfx + args.capital_binance

                return
            elif profit<args.loss_threshold:
                print("Closing Position with LOSS")
                print("Profit: {}".format(profit))
                args.capital_binance = (args.binance_price-pos["buy_price"])*pos["amount"]+args.capital_binance
                args.capital_bfx = (pos["sell_price"] -args.bfx_price)*pos["amount"] + pos["sell_price"]*pos["amount"] +args.capital_bfx
                args.balance = args.capital_bfx + args.capital_binance

                return
            else:
                await asyncio.sleep(10)
    elif args.bfx_price<args.binance_price and args.capital_bfx> args.amount and args.capital_binance> args.amount:
        pos ={
            "buy":"bfx",
            "sell":"binance",
            "buy_price":args.bfx_price,
            "sell_price":args.binance_price,
            "amount": float(args.amount)/args.bfx_price
        }
        args.position.append(pos)
        print(pos)
        args.capital_binance = args.capital_binance - float(pos["amount"])*args.binance_price
        args.capital_bfx = args.capital_bfx - args.amount
        args.balance = args.capital_bfx+args.capital_binance
        while True:
            profit = (args.bfx_price-pos["buy_price"])*pos["amount"]+(pos["sell_price"]-args.binance_price)*pos["amount"]
            avg_price= (args.bfx_price+args.binance_price)/2
            price_gap = float(args.binance_price-args.bfx_price)
            gap = price_gap/avg_price
            if gap<= args.close_rate:
                print("Closing Position")
                print("Profit: {}".format(profit))
                args.capital_bfx = args.bfx_price*pos["amount"]+args.capital_bfx
                args.capital_binance = (pos["sell_price"] - args.binance_price)*pos["amount"] + pos["sell_price"]*pos["amount"] +args.capital_binance
                args.balance = args.capital_bfx + args.capital_binance
                return
            elif profit<args.loss_threshold:
                print("Closing Position with LOSS")
                print("Profit: {}".format(profit))
                args.capital_bfx = (args.bfx_price-pos["buy_price"])*pos["amount"]+args.capital_bfx
                args.capital_binance = (pos["sell_price"] - args.binance_price)*pos["amount"] + pos["sell_price"]*pos["amount"] +args.capital_binance
                args.balance = args.capital_bfx + args.capital_binance
                return
            else:
                await asyncio.sleep(10)




async def binance_ticker():
    uri = "wss://stream.binance.com:9443/ws/btcusdt@kline_1m"
    async with websockets.connect(uri) as websocket:
        # name = input("What's your name? ")
        # ping=json.dumps({
        #    "event": "subscribe",
        #    "channel": "ticker",
        #    "symbol": 'tBTCUSD'
        # })
        #
        # await websocket.send(ping)
        # print(f"> {ping}")
        while True:
            data = await websocket.recv()
            json_data=json.loads(data)
            # print(json.loads(data))
            if type(json_data)==dict and json_data["k"]!=None:
                print("Binance Price: {}".format(json_data["k"]["c"]))
                args.binance_price = float(json_data["k"]["c"])

    pass


async def bfx_ticker():
    uri = "wss://api-pub.bitfinex.com/ws/2"
    async with websockets.connect(uri) as websocket:
        # name = input("What's your name? ")
        ping=json.dumps({
           "event": "subscribe",
           "channel": "ticker",
           "symbol": 'tBTCUSD'
        })

        await websocket.send(ping)
        print(f"> {ping}")
        while True:
            data = await websocket.recv()
            json_data=json.loads(data)
            # print(json.loads(data))
            if type(json_data)==list and json_data[1]!='hb':
                print("Bitfinex Price: {}".format(json_data[1][6]))
                args.bfx_price = float(json_data[1][6])


coro = bfx_ticker()
asyncio.ensure_future(coro)
coro = binance_ticker()
asyncio.ensure_future(coro)
asyncio.ensure_future(opportunity_finder())
asyncio.get_event_loop().run_forever()


