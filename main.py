import os
import asyncio
import sys
from telethon import TelegramClient, events
from msal import PublicClientApplication

# 优先级：环境变量 > 硬编码 (双重保险)
API_ID = int(os.environ.get('API_ID', 32270889))
API_HASH = os.environ.get('API_HASH', 'fbdbd08d1e471dbc0e679b1fc11a8388')
# 这里填入主人刚刚给我的最新 Token
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8615577076:AAGCcVkOYGq6uji9y0XlQodEiI3He0i08aU')
CLIENT_ID = "000000004c12ae29" 
SCOPES = ['Files.ReadWrite.All']

async def main():
    if not API_ID or not BOT_TOKEN:
        print("CRITICAL: Missing API_ID or BOT_TOKEN")
        return

    sys.stdout.reconfigure(line_buffering=True)
    print(f">>> Initializing Client with Bot Token: {BOT_TOKEN[:10]}...")
    
    try:
        # 强制清理旧的 session 冲突
        if os.path.exists('guhee_session.session'):
            os.remove('guhee_session.session')
            
        client = TelegramClient('guhee_session', API_ID, API_HASH)
        await client.start(bot_token=BOT_TOKEN)
        print(">>> Guhee Cloud Engine is LIVE!")

        @client.on(events.NewMessage(pattern='/start'))
        async def start(event):
            print(">>> Received /start")
            app = PublicClientApplication(CLIENT_ID, authority="https://login.microsoftonline.com/common")
            flow = app.initiate_device_flow(scopes=SCOPES)
            
            if flow and "verification_uri" in flow:
                await event.reply(f"👋 主人！新引擎已就位。\n\n🔗 授权链接: {flow['verification_uri']}\n🔑 代码: `{flow['user_code']}`")
            else:
                await event.reply("❌ Microsoft 授权握手失败，请稍后重试。")

        @client.on(events.NewMessage)
        async def handler(event):
            if event.message.video or event.message.document:
                await event.reply("📥 收到文件，云端正在处理...")

        await asyncio.wait_for(client.run_until_disconnected(), timeout=900)
    except Exception as e:
        print(f"!!! Error: {e}")

if __name__ == '__main__':
    asyncio.run(main())
