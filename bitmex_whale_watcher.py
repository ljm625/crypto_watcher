import json
import logging
import time
import traceback
from datetime import datetime
from random import randint

import aiohttp
import websockets
import asyncio

from argparse import Namespace

import yaml

from BotNotifier import BotNotifier
from Exchanges.Bitmex import Bitmex
from Extra.ClosingAlgo import ClosingAlgo

args = Namespace(
    api = None,
    bot=None,
    funding_rate=[],
    max_funding_rate_holder=0,

)
config ={}
bot = None


async def clear_logger():
    while True:
        await asyncio.sleep(86400)
        with open("debug_whale.log","w"):
            pass



def load_config():
    with open("config_funding.yaml") as file:
        cfg = yaml.safe_load(file.read())
        return cfg

def find_gap():
    max_funding = max(args.funding_rate)
    min_funding = min(args.funding_rate)
    gap = max_funding-min_funding
    if gap >= config["max_gap"]:
        index_max = args.funding_rate.index(max_funding)
        index_min = args.funding_rate.index(min_funding)
        time_gap = abs(index_max-index_min)
        if index_max> index_min:
            msg_body = "Funding increase: {} -> {} {}% in {}mins".format(min_funding,max_funding,gap*100/min_funding, time_gap)
        else:
            msg_body = "Funding decrease: {} -> {} -{}% in {}mins".format(max_funding,min_funding,gap*100/max_funding, time_gap)
        logging.info(msg_body)
        # Reset
        args.funding_rate = []
        msg = "#Funding\n"+msg_body
        asyncio.ensure_future(args.bot.notify(msg))


async def get_funding(data):
    if data.get('data')[0]['symbol'] == 'XBTUSD':
        if data.get('data')[0].get("indicativeFundingRate"):
            funding_rate = data.get('data')[0].get("indicativeFundingRate")
            logging.info("Current funding rate: {}".format(funding_rate))
            if len(args.funding_rate)<config["max_funding_rate_num"]:
                args.funding_rate.append(funding_rate)
            else:
                args.funding_rate.pop(0)
                args.funding_rate.append(funding_rate)
            find_gap()



async def handler_ws(data):
    if data.get('table') == 'instrument':
        await get_funding(data)
    elif data.get('table') == 'funding':
        args.funding_rate=[]

async def main(cfg):
    bm = Bitmex("test","xxx","XBTUSD","xxx",testnet=False)
    args.api = bm
    args.bot = BotNotifier(cfg["telegram_bot_api"],cfg["telegram_channel_id_trade"])
    # Calculate order_size
    asyncio.ensure_future(clear_logger())
    # Auto Close Position
    await bm.websocket(["instrument:XBTUSD","funding:XBTUSD"],handler_ws,auth=False)

if __name__ == '__main__':

    config = load_config()
    logging.basicConfig(
        filename='debug_whale.log',
        level=logging.INFO,
        format = '%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
        datefmt = '%Y-%m-%d %H:%M:%S',
    )
    logging.info('Running Bot')
    coro = main(config)
    asyncio.get_event_loop().run_until_complete(coro)


