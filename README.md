# Crypto Watcher

自行配置config.yaml
```yaml
telegram_bot_api : tg机器人api
telegram_channel_id_trade: 频道号，-100开头

bitmex_test_id: bitmex api key
bitmex_test_secret: bitmex api secret
testnet : false
money_split : 钱分多少份，如20的话就每次开单1/20
order_ttl: 自动下单的存活时间，以秒为单位，7200秒就代表2小时后如没有成交自动撤单
```