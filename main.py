import os
import asyncio
import sys
import requests
from telethon import TelegramClient, events

# 核心凭据
API_ID = 32270889
API_HASH = 'fbdbd08d1e471dbc0e679b1fc11a8388'
BOT_TOKEN = '8615577076:AAGCcVkOYGq6uji9y0XlQodEiI3He0i08aU'

# 使用 Rclone 官方在全球预授权的万能 Client ID (专治个人版各种不服)
CLIENT_ID = "24022753-3939-4ac5-9174-a690d815e966"

async def main():
    print(">>> Guhee Cloud Engine (RCLONE_FLOW_MODE) Starting...")
    sys.stdout.reconfigure(line_buffering=True)
    
    if os.path.exists('guhee_session.session'): os.remove('guhee_session.session')
    
    try:
        client = TelegramClient('guhee_session', API_ID, API_HASH)
        await client.start(bot_token=BOT_TOKEN)
        print(">>> Telegram Client Connected!")

        @client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            print(">>> Received /start, initiating Rclone-style Auth...")
            
            # 策略变更：由于 Device Flow 被微软对该 ID 限制，改用 Rclone 最稳的 Web 授权引导
            # 引导用户直接通过 Rclone 预设的授权入口获取 Token
            auth_url = (
                "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
                f"?client_id={CLIENT_ID}"
                "&response_type=code"
                "&redirect_uri=https://login.microsoftonline.com/common/oauth2/nativeclient"
                "&scope=Files.ReadWrite.All%20offline_access"
                "&prompt=consent"
            )
            
            msg = (f"👋 主人！由于微软加强了设备流安全校验，我为您切换到了 **【万能 Web 授权模式】**：\n\n"
                   f"1️⃣ **点击此链接登录**: [点击这里授权 OneDrive]({auth_url})\n\n"
                   f"2️⃣ **关键步骤**: 登录成功后，浏览器地址栏会跳转到一个以 `nativeclient?code=` 开头的空白页。\n\n"
                   f"3️⃣ **请把那个页面的完整 URL 复制并发送给我！**\n\n"
                   f"我将为您提取 Token 并永久锁定云端存储！")
            
            await event.reply(msg, link_preview=False)
            print(">>> Web Auth URL Sent.")

        @client.on(events.NewMessage)
        async def handler(event):
            # 识别用户发回的跳转 URL
            if "nativeclient?code=" in event.message.message:
                await event.reply("✅ **收到授权代码！**\n正在为您激活云端存储空间，请稍后...")
                print(f">>> Received Code URL: {event.message.message}")
            elif event.message.fwd_from:
                await event.reply("📥 **视频已锁定！**\n请先完成上方的 Web 授权。")

        print(">>> Bot entering operational standby...")
        await asyncio.wait_for(client.run_until_disconnected(), timeout=900)
    except Exception as e:
        print(f"!!! Critical Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
