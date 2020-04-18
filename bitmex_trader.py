import json

import aiohttp
import websockets
import asyncio

from argparse import Namespace

import yaml

from BotNotifier import BotNotifier
from Exchanges.Bitmex import Bitmex

args = Namespace(
    bitmex_price=0,
    bxbt_price=0,
    highest_gap={},
    sent = False,
    have_pos = False,
    have_order = False,
    api = None,
    cur_leverage = 0,
    order_id = None,
    direction = "watch",
    order_size = 0,
    start_balance = 0,
    bot=None,
    blocker= False
)
config ={}
bot = None

async def opportunity_finder():
    def build_msg():
        return "Bitmex: {} BXBT: {} GAP: {}%".format(args.bitmex_price,args.bxbt_price,gap_percentage*100)
    gap = abs(args.bitmex_price - args.bxbt_price)
    gap_percentage = gap / args.bitmex_price
    if not args.highest_gap or gap_percentage>= args.highest_gap["percentage"]:
        args.highest_gap = {
            "percentage":gap_percentage,
            "bitmex":args.bitmex_price,
            "bxbt":args.bxbt_price
        }
    if args.bitmex_price > args.bxbt_price:
        direction="sell"
    else:
        direction="buy"
    if gap_percentage>=0.01:
        await do_trade(direction,args.order_size,100)
    elif gap_percentage>=0.005:
        await do_trade(direction,args.order_size,50)

async def order_ttl(order_id):
    await asyncio.sleep(config["order_ttl"])
    await args.api.cancel_order(order_id)

async def unblock():
    await asyncio.sleep(30)
    args.blocker = False

async def do_trade(direction,amount,leverage):
    # Blocker
    if args.blocker:
        return
    else:
        args.blocker = True
        # Make sure if exception happens, it can still unblock
        asyncio.ensure_future(unblock())
    # Check before placing order
    # Whether update order
    if args.have_pos and args.direction == direction:
        return
    if args.have_order:
        await args.api.cancel_order(args.order_id)
    if args.cur_leverage != leverage:
        await args.api.update_leverage(leverage)
        args.cur_leverage = leverage
    if direction=='buy':
        order_id = await args.api.do_long(amount,args.bitmex_price)
    else:
        order_id = await args.api.do_short(amount,args.bitmex_price)
    # Make sure order will be ignored after ttl.
    args.have_order = True
    args.order_id = order_id
    asyncio.ensure_future(order_ttl(order_id))
    msg = "#Order\nSubmitted {} Order at {} {}".format(direction.upper(),args.bitmex_price,amount)
    await args.bot.notify(msg)

    # args.blocker = False

def load_config():
    with open("config.yaml") as file:
        cfg = yaml.safe_load(file.read())
        return cfg

def find_gap(data):
    if data.get('data')[0]['symbol'] == 'XBTUSD':
        trade_data = data.get('data')[0]
        if trade_data.get("lastPrice"):
            args.bitmex_price = trade_data.get("lastPrice")
    elif data.get('data')[0]['symbol'] == '.BXBT':
        trade_data = data.get('data')[0]
        if trade_data.get("lastPrice"):
            args.bxbt_price = trade_data.get("lastPrice")
        print("Bitmex/BXBT Price: {} {}".format(args.bitmex_price, args.bxbt_price))
        gap = abs(args.bitmex_price - args.bxbt_price)
        gap_percentage = gap / args.bitmex_price
        if gap_percentage >=0.001:
            asyncio.ensure_future(opportunity_finder())

def update_position(data):
    if data.get('action') and data.get('action')=='update':
        for pair in data['data']:
            if pair['symbol']=="XBTUSD":
                if pair['currentQty']!=0:
                    args.have_pos = True
                    if pair['currentQty']>0:
                        args.direction="buy"
                    else:
                        args.direction = "sell"
                elif pair['currentQty']==0:
                    args.have_pos = False
                if pair.get("posState") and pair["posState"]=="Liquidated":
                    # Oh fuck its liquidated!
                    if args.have_order and not args.have_pos:
                        # Oh Fuck instant liquidate!
                        args.have_order = False
                    args.have_pos = False
                    # Trigger Liquidated warning
                    msg = "#Liquidation\nYour Position has been Liquidated at {}".format(args.bitmex_price)
                    asyncio.ensure_future(args.bot.notify(msg))


def update_order(data):
    if data.get('action') and data.get('action')=='update':
        for order in data["data"]:
            if order["orderID"]==args.order_id:
                if order.get("ordStatus") and order["ordStatus"]=="Filled":
                    args.have_order = False
                    msg = "#Order\nYour Order has been Filled at {}".format(args.bitmex_price)
                    asyncio.ensure_future(args.bot.notify(msg))


def handler_ws(data):
    if data.get('table') == 'instrument':
        find_gap(data)
    elif data.get('table') == 'position':
        update_position(data)
    elif data.get('table') == 'order':
        update_order(data)

async def balance_checker():
    while True:
        await asyncio.sleep(3600)
        balance = await args.api.get_balance()
        if balance<= args.start_balance*0.2:
            # Generate Warning Message.
            msg = "#Warning\nYour BitMEX current balance is : {} which may cause issue on Bot. Please Check NOW.".format(balance)
            await args.bot.notify(msg)


async def main(cfg):
    bm = Bitmex("test",cfg["bitmex_test_id"],"XBTUSD",cfg["bitmex_test_secret"],testnet=cfg["testnet"])
    args.api = bm
    args.bot = BotNotifier(cfg["telegram_bot_api"],cfg["telegram_channel_id_trade"])
    # Calculate order_size
    args.start_balance = await bm.get_balance()
    args.order_size = int(args.start_balance/cfg["money_split"])
    # Check balance
    asyncio.ensure_future(balance_checker())

    await bm.websocket(["instrument:XBTUSD","instrument:.BXBT","position:XBTUSD","order:XBTUSD"],handler_ws)



if __name__ == '__main__':

    config = load_config()
    coro = main(config)
    asyncio.get_event_loop().run_until_complete(coro)


