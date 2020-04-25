import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse

import aiohttp
import websockets


class Binance(object):

    def __init__(self,account_name,api_token,pair,api_secret=None,testnet=False):
        self.account=account_name
        self.pair=pair
        self.api_token=api_token
        self.api_secret = api_secret
        if testnet:
            self.base_url="https://testnet.bitmex.com"
            self.websocket_url = "wss://testnet.bitmex.com/realtime"
        else:
            self.base_url="https://fapi.binance.com"
            self.websocket_url = "wss://fstream.binance.com"

        if not self.api_secret:
            raise Exception("Please provide API Secret")
        pass

        self.exchange = None
        self.listen_key = None


    def generate_signature(self,payload_raw):
        return hmac.new(bytes(self.api_secret, 'utf8'), bytes(payload_raw, 'utf8'), digestmod=hashlib.sha256).hexdigest()


    async def _api_wrapper(self,method,endpoint,payload):

        url = "{}{}".format(self.base_url,endpoint)
        payload["timestamp"] = int(time.time()*1000)
        payload["recvWindow"] = 5000

        payload_raw = urllib.parse.urlencode(payload)

        signature=self.generate_signature(payload_raw)
        payload["signature"] = signature
        # headers
        headers = {
            'X-MBX-APIKEY': self.api_token
        }
        async with aiohttp.ClientSession() as session:
            async with session.request(method,url, headers=headers, data=payload) as resp:
                if resp.status==200:
                    result = await resp.json()
                    return result
                else:
                    try:
                        result = await resp.json()
                    except Exception as e:
                        raise Exception("Exception when POST {} {} {}".format(endpoint, resp.status,e))
                    raise Exception("Exception when POST {}  {}".format(endpoint, result["msg"]))

    async def _get_wrapper(self,endpoint,data={}):
        data["timestamp"] = int(time.time()*1000)
        data["recvWindow"] = 5000
        verb = "GET"

        payload_raw = urllib.parse.urlencode(data)

        signature=self.generate_signature(payload_raw)
        data["signature"] = signature

        # headers
        headers = {
            'X-MBX-APIKEY': self.api_token
        }
        if urllib.parse.urlencode(data)!="":
            endpoint+="?"+urllib.parse.urlencode(data)
        url = "{}{}".format(self.base_url,endpoint)


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
                    raise Exception("Exception when POST {}  {}".format(endpoint,result["msg"]))


    async def update_leverage(self,leverage):
        payload={
            "symbol":self.pair,
            "leverage":leverage
        }
        await self._api_wrapper("POST","/fapi/v1/leverage",payload)
        return True

    async def update_margin_type(self,leverage):
        assert  leverage in ["ISOLATED","CROSSED"]
        payload={
            "symbol":self.pair,
            "marginType":leverage
        }
        try:
            await self._api_wrapper("POST","/fapi/v1/marginType",payload)
        except Exception as e:
            if "No need" in str(e):
                return True
            else:
                raise Exception(str(e))
        return True



    async def do_long(self,amount,price,market=True,reduce=False):
        payload = {
            "symbol":self.pair,
            "side":"BUY",
            "type":"MARKET",
            "quantity":amount,
            "reduceOnly":reduce
        }
        if not market:
            payload["type"]="LIMIT"
            payload["price"]=price
        result = await self._api_wrapper("POST","/fapi/v1/order",payload)
        return result["orderId"]


    async def do_short(self,amount,price,market=True,reduce=False):
        payload = {
            "symbol":self.pair,
            "side":"SELL",
            "type":"MARKET",
            "quantity":amount,
            "reduceOnly": reduce

        }
        if not market:
            payload["type"]="LIMIT"
            payload["price"]=price
        result = await self._api_wrapper("POST","/fapi/v1/order",payload)
        return result["orderId"]

    async def cancel_order(self,order_id):
        payload = {
            "symbol":self.pair,
            "orderId":order_id,
        }
        await self._api_wrapper("DELETE","/fapi/v1/order",payload)
        return True

    async def cancel_all_orders(self):
        payload = {
            "symbol":self.pair,
        }
        await self._api_wrapper("DELETE","/fapi/v1/allOpenOrders",payload)
        return True

    async def get_balance(self,in_usd=True):
        payload = {
        }
        result = await self._get_wrapper("/fapi/v1/balance",payload)
        for a in result:
            if a["asset"]=="USDT":
                return float(a["balance"])
        return 0

    async def get_ticker(self):
        payload = {
            "symbol":self.pair,
            "limit":1
        }
        data = await self._get_wrapper("/fapi/v1/trades",payload)
        for order in data:
            return order["price"]
        return 0

    async def get_listen_key(self):
        resp = await self._api_wrapper("POST","/fapi/v1/listenKey",{})
        return resp["listenKey"]

    async def update_listen_key(self):
        await self._api_wrapper("PUT","/fapi/v1/listenKey",{})


    async def websocket(self,handler,auth=True):
        while True:
            try:
                self.listen_key = await self.get_listen_key()
                uri = self.websocket_url+"/ws/"+self.listen_key
                async with websockets.connect(uri) as websocket:
                    while True:
                        data = await websocket.recv()
                        json_data=json.loads(data)
                        if json_data.get("e")=="listenKeyExpired":
                            raise Exception("ListenKey Expired")
                        await handler(json_data)
            except Exception as e:
                logging.error("ERROR: websocket faced issue: {}, auto respawn".format(e))
                print("ERROR: websocket faced issue: {}, auto respawn".format(e))
                await self.websocket(handler,auth)