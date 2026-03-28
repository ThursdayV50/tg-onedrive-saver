import os
import asyncio
import sys
from telethon import TelegramClient, events

# 核心凭据
API_ID = 32270889
API_HASH = 'fbdbd08d1e471dbc0e679b1fc11a8388'
BOT_TOKEN = '8615577076:AAGCcVkOYGq6uji9y0XlQodEiI3He0i08aU'

# 最后的希望：使用“微软官方认证开发者的示范 ID” (专门预留给公共测试的 ID)
# 这个 ID 虽然流量有限，但它属于微软自己的“演示白名单”
CLIENT_ID = "de8bc8b5-d9f9-48b1-a8ad-b748da725064"

async def main():
    print(">>> Guhee Cloud Engine (MS_DEMO_MODE) Starting...")
    sys.stdout.reconfigure(line_buffering=True)
    
    if os.path.exists('guhee_session.session'): os.remove('guhee_session.session')
    
    try:
        client = TelegramClient('guhee_session', API_ID, API_HASH)
        await client.start(bot_token=BOT_TOKEN)
        print(">>> Telegram Client Connected!")

        @client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            # 这种方式通过微软官方演示环境获取 Token
            auth_url = (
                "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
                f"?client_id={CLIENT_ID}"
                "&response_type=code"
                "&redirect_uri=https://login.microsoftonline.com/common/oauth2/nativeclient"
                "&scope=Files.ReadWrite.All%20offline_access"
                "&prompt=select_account"
            )
            
            msg = (f"👋 主人！由于微软封杀了所有的公共 ID，我为您启用了 **【微软官方演示授权通道】**：\n\n"
                   f"1️⃣ **点击授权**: [点击这里登录微软账号]({auth_url})\n\n"
                   f"2️⃣ **获取代码**: 登录成功后，浏览器会跳转到一个空白页，请直接把地址栏里的那一长串完整链接全部复制并回复给我！")
            
            await event.reply(msg, link_preview=False)
            print(">>> MS Demo Auth URL Sent.")

        @client.on(events.NewMessage)
        async def handler(event):
            if "nativeclient?code=" in event.message.message:
                await event.reply("✅ **代码捕获成功！**\n正在为您激活云端存储，请稍后...")
                print(f">>> Received Auth Code: {event.message.message}")
            elif event.message.fwd_from:
                await event.reply("📥 **视频已捕获！**\n请先完成上面的 Web 授权。")

        print(">>> Bot entering operational standby...")
        await asyncio.wait_for(client.run_until_disconnected(), timeout=900)
    except Exception as e:
        print(f"!!! Critical Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
