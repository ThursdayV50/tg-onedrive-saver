import os
import asyncio
import sys
from telethon import TelegramClient, events

# 核心凭据
API_ID = 32270889
API_HASH = 'fbdbd08d1e471dbc0e679b1fc11a8388'
BOT_TOKEN = '8615577076:AAGCcVkOYGq6uji9y0XlQodEiI3He0i08aU'

# 核心：使用目前全球最稳、专门适配个人版/家庭版 OneDrive 的 Rclone 预设 Client ID
# 这个 ID 的权限被微软官方“全绿灯”放行
CLIENT_ID = "3368949b-7667-4638-a25e-3367d32e92c3"

async def main():
    print(">>> Guhee Cloud Engine (RCLONE_OFFICIAL_MODE) Starting...")
    sys.stdout.reconfigure(line_buffering=True)
    
    if os.path.exists('guhee_session.session'): os.remove('guhee_session.session')
    
    try:
        client = TelegramClient('guhee_session', API_ID, API_HASH)
        await client.start(bot_token=BOT_TOKEN)
        print(">>> Telegram Client Connected!")

        @client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            # 这种方式通过 Rclone 的官方重定向，绝对能弹出登录页
            auth_url = (
                "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
                f"?client_id={CLIENT_ID}"
                "&response_type=code"
                "&redirect_uri=http://localhost:53682/"
                "&scope=Files.ReadWrite.All%20offline_access"
                "&prompt=consent"
            )
            
            msg = (f"👋 主人！我为您开启了 **【全球万能授权通道 (Rclone 级)】**：\n\n"
                   f"1️⃣ **点击授权**: [点击这里直接登录微软账号]({auth_url})\n\n"
                   f"2️⃣ **获取代码**: 登录成功后，浏览器会跳转到一个失败页面（因为 localhost:53682 无法访问），**这没关系！**\n\n"
                   f"3️⃣ **最关键步骤**: 请直接把那个【失败页面地址栏】里的全部长链接复制并回复给我！")
            
            await event.reply(msg, link_preview=False)
            print(">>> Rclone-style Auth URL Sent.")

        @client.on(events.NewMessage)
        async def handler(event):
            if "localhost:53682/?code=" in event.message.message:
                await event.reply("✅ **代码捕获成功！**\n正在为您锁定存储权限，请稍后...")
                print(f">>> Received Auth Code: {event.message.message}")
            elif event.message.fwd_from:
                await event.reply("📥 **视频已捕获！**\n请先完成上面的 Web 授权，完成后我立刻开工。")

        print(">>> Bot entering operational standby...")
        await asyncio.wait_for(client.run_until_disconnected(), timeout=900)
    except Exception as e:
        print(f"!!! Critical Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
