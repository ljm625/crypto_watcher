import json
import websockets
import asyncio

from argparse import Namespace

import yaml

from BotNotifier import BotNotifier

args = Namespace(
    bitmex_price=0,
    bxbt_price=0,
    balance=2000,
    position= [],
    capital= 1000,
    amount = 0.1,
    leverage = 100,
    sent = False
)
config ={}
bot = None

async def opportunity_finder():
    def build_msg():
        return "Bitmex: {} BXBT: {} GAP: {}%".format(args.bitmex_price,args.bxbt_price,gap_percentage*100)
    gap = abs(args.bitmex_price - args.bxbt_price)
    gap_percentage = gap / args.bitmex_price
    msg = None
    if gap_percentage>=0.05:
        msg = "#100X Leverage NOW\n"
        msg+=build_msg()
    elif gap_percentage>=0.02:
        msg = "#50X Leverage NOW\n"
        msg+=build_msg()
    elif gap_percentage>=0.01:
        msg = build_msg()
    if msg and args.sent:
        await bot.notify(msg)
        args.sent=True



async def bitmex_ticker():
    while True:
        try:
            uri = "wss://www.bitmex.com/realtime"
            async with websockets.connect(uri) as websocket:
                # name = input("What's your name? ")
                ping=json.dumps({"op": "subscribe", "args": ["instrument:XBTUSD","instrument:.BXBT"]})
                await websocket.send(ping)
                while True:
                    data = await websocket.recv()
                    json_data=json.loads(data)
                    # print(json.loads(data))
                    if json_data.get('table')=='instrument':
                        if json_data.get('data')[0]['symbol']=='XBTUSD':
                            trade_data = json_data.get('data')[0]
                            if trade_data.get("lastPrice"):
                                args.bitmex_price = trade_data.get("lastPrice")
                        elif json_data.get('data')[0]['symbol']=='.BXBT':
                            trade_data = json_data.get('data')[0]
                            if trade_data.get("lastPrice"):
                                args.bxbt_price = trade_data.get("lastPrice")
                            print("Bitmex/BXBT Price: {} {}".format(args.bitmex_price,args.bxbt_price))
                            gap = abs(args.bitmex_price-args.bxbt_price)
                            gap_percentage = gap/args.bitmex_price
                            if gap >= 10:
                                print("GAP: {} {}%".format(gap,gap_percentage*100))
                            if gap_percentage >=0.01:
                                print("OPPORTUNITY!!!")
                            await opportunity_finder()

        except:
            pass

            # if type(json_data)==list and json_data[1]!='hb':
            #     print("Bitfinex Price: {}".format(json_data[1][6]))
            #     args.bfx_price = float(json_data[1][6])

def load_config():
    with open("config.yaml") as file:
        cfg = yaml.safe_load(file.read())
        return cfg

async def rate_limiter():
    while True:
        if args.sent:
            args.sent = False
        await asyncio.sleep(config["delta"])

if __name__ == '__main__':

    config = load_config()
    bot = BotNotifier(config["telegram_bot_api"],config["telegram_channel_id"])
    coro = bitmex_ticker()
    asyncio.ensure_future(coro)
    asyncio.get_event_loop().run_forever()


