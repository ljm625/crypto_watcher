import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from datetime import datetime

import aiohttp
import dateutil
import websockets


class Bitmex(object):

    def __init__(self,account_name,api_token,pair,api_secret=None,testnet=False):
        self.account=account_name
        self.pair=pair
        self.api_token=api_token
        self.api_secret = api_secret
        if testnet:
            self.base_url="https://testnet.bitmex.com"
            self.websocket_url = "wss://testnet.bitmex.com/realtime"
        else:
            self.base_url="https://www.bitmex.com"
            self.websocket_url = "wss://www.bitmex.com/realtime"

        if not self.api_secret:
            raise Exception("Please provide API Secret")
        pass

        self.exchange = None


    def generate_signature(self,payload_raw):
        return hmac.new(bytes(self.api_secret, 'utf8'), bytes(payload_raw, 'utf8'), digestmod=hashlib.sha256).hexdigest()


    async def _api_wrapper(self,method,endpoint,payload):
        url = "{}{}".format(self.base_url,endpoint)
        expire = str(int(time.time())+10)
        verb = method.upper()

        payload_raw = verb+endpoint+str(expire)+json.dumps(payload)

        signature=self.generate_signature(payload_raw)
        # headers
        headers = {
            'api-expires': expire,
            'api-key': self.api_token,
            'api-signature': signature
        }
        async with aiohttp.ClientSession() as session:
            async with session.request(method,url, headers=headers, json=payload) as resp:
                if resp.status==200:
                    result = await resp.json()
                    return result
                else:
                    try:
                        result = await resp.json()
                    except Exception as e:
                        raise Exception("Exception when POST {} {} {}".format(endpoint, resp.status,e))
                    raise Exception("Exception when POST {}  {}".format(endpoint, result["error"]["message"]))

    async def _get_wrapper(self,endpoint,data={}):
        expire = str(int(time.time())+10)
        verb = "GET"
        if urllib.parse.urlencode(data)!="":
            endpoint+="?"+urllib.parse.urlencode(data)
        url = "{}{}".format(self.base_url,endpoint)

        payload_raw = verb+endpoint+str(expire)

        signature=self.generate_signature(payload_raw)


        # headers
        headers = {
            'api-expires': expire,
            'api-key': self.api_token,
            'api-signature': signature
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status==200:
                    result = await resp.json()
                    return result
                else:
                    try:
                        result = await resp.json()
                    except Exception as e:
                        raise Exception("Exception when POST {} {} {}".format(endpoint, resp.status,e))
                    raise Exception("Exception when POST {}  {}".format(endpoint,result["error"]["message"]))


    async def update_leverage(self,leverage):
            payload={
                "symbol":"XBTUSD",
                "leverage":leverage
            }
            await self._api_wrapper("POST","/api/v1/position/leverage",payload)
            return True

    async def do_long(self,amount,price,market=False,reduce=False):
        payload = {
            "symbol":self.pair,
            "orderQty":amount,
            "price":price,
            "ordType":"Limit"
        }
        if market:
            payload["ordType"]="Market"
        if reduce:
            payload["execInst"]="ReduceOnly"
        result = await self._api_wrapper("POST","/api/v1/order",payload)
        return result["orderID"]


    async def do_short(self,amount,price,market=False,reduce=False):
        payload = {
            "symbol":self.pair,
            "orderQty":-amount,
            "price":price,
            "ordType":"Limit"
        }
        if market:
            payload["ordType"]="Market"
        if reduce:
            payload["execInst"]="ReduceOnly"
        result = await self._api_wrapper("POST","/api/v1/order",payload)
        return result["orderID"]

    async def cancel_order(self,order_id):
        payload = {
            "orderID":order_id,
        }
        await self._api_wrapper("DELETE","/api/v1/order",payload)
        return True

    async def cancel_all_orders(self):
        payload = {
            "symbol":self.pair,
        }
        await self._api_wrapper("DELETE","/api/v1/order/all",payload)
        return True

    async def get_balance(self,in_usd=True):
        payload = {
            "currency":"XBt"
        }
        result = await self._get_wrapper("/api/v1/user/margin",payload)
        balance = result["availableMargin"]*0.00000001
        if in_usd:
            price = await self.get_ticker()
            balance = price*balance
        return balance

    async def get_ticker(self):
        payload = {
            "symbol":"XBTUSD"
        }
        data = await self._get_wrapper("/api/v1/orderBook/L2",payload)
        for order in data:
            if order["side"]=="Buy":
                return order["price"]
        return 0

    async def websocket(self,subcribes,handler,auth=True):
        while True:
            try:
                uri = self.websocket_url
                async with websockets.connect(uri) as websocket:
                    if auth:
                        expire = int(time.time()) + 10
                        payload = 'GET/realtime' + str(expire)
                        signature = self.generate_signature(payload)
                        msg = {"op": "authKeyExpires", "args": [self.api_token, expire, signature]}
                        await websocket.send(json.dumps(msg))

                    ping=json.dumps({"op": "subscribe", "args": subcribes})
                    await websocket.send(ping)
                    while True:
                        data = await websocket.recv()
                        json_data=json.loads(data)
                        await handler(json_data)
            except Exception as e:
                logging.error("ERROR: websocket faced issue: {}, auto respawn".format(e))
                print("ERROR: websocket faced issue: {}, auto respawn".format(e))
                await self.websocket(subcribes,handler,auth)

    async def get_history(self,candles,bin):
        assert bin in ["1m","5m","1h","1d"]
        payload = {
            "binSize":bin,
            "symbol":self.pair,
            "partial":False,
            "reverse":True,
            "count":candles
        }
        result = await self._get_wrapper("/api/v1/trade/bucketed",payload)

        return self.parse_history(result)

    @staticmethod
    def parse_history(result):
        history = []
        for data in result:
            history.append(
                {
                    "timestamp":dateutil.parser.parse(data["timestamp"]).timestamp(),
                    "open":float(data["open"]),
                    "close": float(data["close"]),
                    "low": float(data["low"]),
                    "high": float(data["high"]),
                    "vol":float(data["volume"])
                }
            )
        history.reverse()
        return history
