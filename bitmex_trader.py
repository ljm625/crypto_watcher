import json
import logging
import traceback

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
    blocker= False,
    current_pos = 0,
    max_pos = 0
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
    cur_price = int(args.bitmex_price)
    if gap_percentage>=0.01:
        logging.info("Triggering 100X Leverage Trade at {}".format(args.bitmex_price))
        await do_trade(direction,cur_price,args.order_size,100)
    elif gap_percentage>=0.005:
        logging.info("Triggering 50X Leverage Trade at {}".format(args.bitmex_price))
        await do_trade(direction,cur_price,args.order_size,50)

async def order_ttl(order_id):
    try:
        await asyncio.sleep(config["order_ttl"])
        await args.api.cancel_order(order_id)
        logging.info("Order cancelled by TTL timeout {}".format(order_id))
    except Exception as e:
        await args.bot.notify("ERROR in Program")
        logging.error("Order TTL issue {}".format(e))


async def unblock():
    await asyncio.sleep(30)
    logging.info("Unblock Buy")
    args.blocker = False


async def clear_logger():
    while True:
        await asyncio.sleep(86400)
        with open("debug.log","w"):
            pass

async def do_trade(direction,price,amount,leverage):
    # Blocker
    if args.blocker:
        logging.info("Blocked Trade {} {}".format(direction,price))
        return
    else:
        args.blocker = True
        # Make sure if exception happens, it can still unblock
        asyncio.ensure_future(unblock())
    success =False
    count = 0
    while not success and count<3:
        try:
        # Check before placing order
            # Whether update order
            if args.have_pos and args.direction == direction:
                if args.cur_leverage*args.max_pos>args.current_pos+amount*args.cur_leverage:
                    logging.info(
                        "Adding current position {} {} {}".format(direction.upper(), args.bitmex_price,
                                                                                          amount * args.cur_leverage))
                    leverage=args.cur_leverage
                else:
                    msg = "#Order\nIgnoring {} Order at {} {} because current have position".format(direction.upper(), args.bitmex_price, amount * leverage)
                    await args.bot.notify(msg)
                    logging.info("Ignoring {} Order at {} {} because current have position".format(direction.upper(), args.bitmex_price, amount * leverage))
                    return
            if args.have_order:
                logging.info("Cancelling order {}".format(args.order_id))
                await args.api.cancel_order(args.order_id)
            if args.cur_leverage != leverage:
                logging.info("Updating Leverage {}".format(leverage))
                await args.api.update_leverage(leverage)
                args.cur_leverage = leverage
            if direction=='buy':
                logging.info("Executing Buy at {}".format(price))
                if price<args.bitmex_price:
                    order_id = await args.api.do_long(amount*leverage,price)
                else:
                    order_id = await args.api.do_long(amount*leverage,args.bitmex_price)
            else:
                logging.info("Executing Sell at {}".format(price))
                if price > args.bitmex_price:
                    order_id = await args.api.do_short(amount*leverage, price)
                else:
                    order_id = await args.api.do_short(amount*leverage,args.bitmex_price)
            # Make sure order will be ignored after ttl.
            args.have_order = True
            args.order_id = order_id
            asyncio.ensure_future(order_ttl(order_id))
            msg = "#Order\nSubmitted {} Order at {} {}".format(direction.upper(),args.bitmex_price,amount*leverage)
            logging.info("Submitted {} Order at {} {}".format(direction.upper(),args.bitmex_price,amount*leverage))
            await args.bot.notify(msg)
            success =True
            return
        except Exception as e:
            logging.error("Order issue: {}".format(e))
            if "overloaded" in str(e):
                print("System Overload")
                await asyncio.sleep(5)
                count+=1
            else:
                await args.bot.notify("ERROR in Program")
                return

    # args.blocker = False

def load_config():
    with open("config.yaml") as file:
        cfg = yaml.safe_load(file.read())
        return cfg

async def find_gap(data):
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
            logging.info("Bitmex/BXBT Price: {} {}".format(args.bitmex_price, args.bxbt_price))
            logging.info("GAP: {}%".format(gap_percentage*100))
            await opportunity_finder()

def update_position(data):
    if data.get('action') and data.get('action')=='update':
        for pair in data['data']:
            if pair['symbol']=="XBTUSD":
                if pair['currentQty']!=0:
                    args.have_pos = True
                    args.current_pos = pair['currentQty']
                    if pair['currentQty']>0:
                        args.direction="buy"
                    else:
                        args.direction = "sell"
                elif pair['currentQty']==0:
                    args.have_pos = False
                    args.current_pos = pair['currentQty']
                if pair.get("posState") and pair["posState"]=="Liquidated":
                    # Oh fuck its liquidated!
                    if args.have_order and not args.have_pos:
                        # Oh Fuck instant liquidate!
                        args.have_order = False
                    args.have_pos = False
                    args.current_pos = 0
                    # Trigger Liquidated warning
                    msg = "#Liquidation\nYour Position has been Liquidated at {}".format(args.bitmex_price)
                    logging.info("Position has been Liquidated at {}".format(args.bitmex_price))
                    asyncio.ensure_future(args.bot.notify(msg))


def update_order(data):
    if data.get('action') and data.get('action')=='update':
        for order in data["data"]:
            if order.get("ordStatus") and order["ordStatus"] == "Filled":
                if order["orderID"]==args.order_id:
                    args.have_order = False
                    msg = "#Order\nYour Order has been Filled at {}".format(args.bitmex_price)
                    logging.info("Order has been Filled at {}".format(args.bitmex_price))
                    asyncio.ensure_future(args.bot.notify(msg))
                else:
                    msg = "#Order\nExisting Order has been Filled at {}".format(args.bitmex_price)
                    logging.info("Existing Order has been Filled at {}".format(args.bitmex_price))
                    asyncio.ensure_future(args.bot.notify(msg))



async def handler_ws(data):
    if data.get('table') == 'instrument':
        await find_gap(data)
    elif data.get('table') == 'position':
        update_position(data)
    elif data.get('table') == 'order':
        update_order(data)

async def balance_checker():
    while True:
        try:
            await asyncio.sleep(3600)
            balance = await args.api.get_balance()
            if balance<= args.start_balance*0.2:
                # Generate Warning Message.
                msg = "#Warning\nYour BitMEX current balance is : {} which may cause issue on Bot. Please Check NOW.".format(balance)
                await args.bot.notify(msg)
        except Exception as e:
            traceback.print_exc()
            logging.error("Balance Checker issue: {}".format(e))
            await args.bot.notify("ERROR in Program")


async def main(cfg):
    bm = Bitmex("test",cfg["bitmex_test_id"],"XBTUSD",cfg["bitmex_test_secret"],testnet=cfg["testnet"])
    args.api = bm
    args.bot = BotNotifier(cfg["telegram_bot_api"],cfg["telegram_channel_id_trade"])
    # Calculate order_size
    args.start_balance = await bm.get_balance()
    args.order_size = int(args.start_balance/cfg["money_split"])
    args.max_pos = int(args.start_balance/cfg["max_position"])

    # Check balance
    asyncio.ensure_future(balance_checker())
    # Clear logging
    asyncio.ensure_future(clear_logger())

    await bm.websocket(["instrument:XBTUSD","instrument:.BXBT","position:XBTUSD","order:XBTUSD"],handler_ws)



if __name__ == '__main__':

    config = load_config()
    logging.basicConfig(filename='debug.log', level=logging.INFO)
    logging.info('Running Bot')
    coro = main(config)
    asyncio.get_event_loop().run_until_complete(coro)


