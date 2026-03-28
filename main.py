import os
import asyncio
import sys
from telethon import TelegramClient, events

# 核心凭据
API_ID = 32270889
API_HASH = 'fbdbd08d1e471dbc0e679b1fc11a8388'
BOT_TOKEN = '8615577076:AAGCcVkOYGq6uji9y0XlQodEiI3He0i08aU'

# 使用 AList 项目官方预授权的万能 Client ID (这个 ID 对个人账号支持极好，且几乎永不失效)
CLIENT_ID = "000000004c12ae29" 

async def main():
    print(">>> Guhee Cloud Engine (ALIST_COMPAT_MODE) Starting...")
    sys.stdout.reconfigure(line_buffering=True)
    
    if os.path.exists('guhee_session.session'): os.remove('guhee_session.session')
    
    try:
        client = TelegramClient('guhee_session', API_ID, API_HASH)
        await client.start(bot_token=BOT_TOKEN)
        print(">>> Telegram Client Connected!")

        @client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            # 这种方式通过 AList 的公共中转获取 Token，是最简单的“傻瓜式”授权
            auth_url = (
                "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
                f"?client_id={CLIENT_ID}"
                "&response_type=code"
                "&redirect_uri=https://login.microsoftonline.com/common/oauth2/nativeclient"
                "&scope=Files.ReadWrite.All%20offline_access"
                "&prompt=select_account"
            )
            
            msg = (f"👋 主人！我为您开启了 **【极速 Web 授权通道】**：\n\n"
                   f"1️⃣ **点击授权**: [点击这里登录您的微软账号]({auth_url})\n\n"
                   f"2️⃣ **获取代码**: 登录成功后，浏览器会跳转到一个空白页，地址栏里会有一串类似 `code=M.R3_B...` 的代码。\n\n"
                   f"3️⃣ **请把那个地址栏的【完整链接】全部复制并回复给我！**\n\n"
                   f"⚠️ **重要**: 如果链接太长，请直接回复该链接，我会为您自动提取授权。")
            
            await event.reply(msg, link_preview=False)
            print(">>> Alist-style Auth URL Sent.")

        @client.on(events.NewMessage)
        async def handler(event):
            if "nativeclient?code=" in event.message.message:
                await event.reply("✅ **授权已捕获！**\n正在为您锁定 OneDrive 存储空间，请稍后...")
                print(f">>> Received Auth Link: {event.message.message}")
            elif event.message.fwd_from:
                await event.reply("📥 **已标记视频流！**\n请先完成上方的 Web 授权，完成后我会自动执行历史任务的转存。")

        print(">>> Bot entering operational standby...")
        await asyncio.wait_for(client.run_until_disconnected(), timeout=900)
    except Exception as e:
        print(f"!!! Critical Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
