import aiohttp
import urllib.parse

class BotNotifier(object):
    """
    This class is used for notify signals
    """

    def __init__(self,api,channel):
        self.api=api
        self.channel = channel
        pass

    async def notify(self,msg):

        url = "https://api.telegram.org/bot{}/sendMessage?chat_id={}&text={}".format( self.api, self.channel,
                urllib.parse.quote(msg, safe=''))

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                pass



