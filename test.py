# -*- coding: utf-8 -*-

import asyncio
import os
import sys
import traceback

import ccxt.async_support as ccxt
from pprint import pprint


async def run_bot():
    while True:
        try:
            await test_bot_checker()
        except:
            pass


async def test_bot_checker():

    bfx = ccxt.bitfinex({
        #
        # ↓ The "proxy" property setting below is for CORS-proxying only!
        # Do not use it if you don't know what a CORS proxy is.
        # https://github.com/ccxt/ccxt/wiki/Install#cors-access-control-allow-origin
        # You should only use the "proxy" setting if you're having a problem with Access-Control-Allow-Origin
        # In Python you rarely need to use it, if ever at all.
        #
        # 'proxy': 'https://cors-anywhere.herokuapp.com/',
        #
        # ↓ The "aiohttp_proxy" setting is for HTTP(S)-proxying (SOCKS, etc...)
        # It is a standard method of sending your requests through your proxies
        # This gets passed to the `asyncio` and `aiohttp` implementation directly
        # You can use this setting as documented here:
        # https://docs.aiohttp.org/en/stable/client_advanced.html#proxy-support
        # This is the setting you should be using with async version of ccxt in Python 3.5+
        #
        # 'aiohttp_proxy': 'http://proxy.com',
        # 'aiohttp_proxy': 'http://user:pass@some.proxy.com',
        # 'aiohttp_proxy': 'http://10.10.1.10:3128',
        'enableRateLimit': False,

    })
    binance = ccxt.binance({
        'enableRateLimit': False,

    })

    try:
    # your code goes here...
        while True:
            ticker1 = await bfx.fetch_ticker('BTC/USD')
            ticker2 = await binance.fetch_ticker('BTC/USDT')
            if abs(ticker1["last"]-ticker2["last"])/((ticker1["last"]+ticker2["last"])/2)>0.01:
                print("Opportunity for arb: {} {} differ: {}%".format(ticker1["last"],ticker1["last"],(100*abs(ticker1["last"]-ticker2["last"]))/((ticker1["last"]+ticker2["last"])/2)))
            print("BFX: {} Binance: {}".format(ticker1["last"],ticker2["last"]))
            # await bfx.close()
            # await binance.close()
            await asyncio.sleep(1)
    except:
        # traceback.print_stack()
        pass
    finally:
        await bfx.close()
        await binance.close()

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(run_bot())
