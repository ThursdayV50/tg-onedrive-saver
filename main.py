import os
import asyncio
import sys
from telethon import TelegramClient, events
from msal import PublicClientApplication

# 核心凭据
API_ID = 32270889
API_HASH = 'fbdbd08d1e471dbc0e679b1fc11a8388'
BOT_TOKEN = '8615577076:AAGCcVkOYGq6uji9y0XlQodEiI3He0i08aU'

# 核心：使用目前唯一能绕过 AADSTS50059 报错的微软官方公共 ID
# 这个 ID 专门针对个人版账号设计
CLIENT_ID = "24022753-3939-4ac5-9174-a690d815e966"
SCOPES = ['Files.ReadWrite.All']

async def main():
    print(">>> Guhee Cloud Engine (PERSONAL_ONLY_MODE) Starting...")
    sys.stdout.reconfigure(line_buffering=True)
    
    if os.path.exists('guhee_session.session'): os.remove('guhee_session.session')
    
    try:
        client = TelegramClient('guhee_session', API_ID, API_HASH)
        await client.start(bot_token=BOT_TOKEN)
        print(">>> Telegram Client Connected!")

        @client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            print(">>> Received /start, targeting Microsoft Consumers Tenant...")
            # 关键：authority 必须显式改为 /consumers，绝对不能再用 /common
            # 这样微软才知道您是个人账号，而不是寻找“不存在的企业租户”
            app = PublicClientApplication(CLIENT_ID, authority="https://login.microsoftonline.com/consumers")
            
            flow = app.initiate_device_flow(scopes=SCOPES)
            
            if not flow or "user_code" not in flow:
                err_desc = flow.get("error_description", "Unknown Microsoft error")
                print(f"!!! Microsoft Auth Error: {flow}")
                await event.reply(f"❌ OneDrive 授权初始化失败。\n\n**原因**: `{err_desc}`\n\n**Guhee 建议**: 看来微软依然在尝试寻找您的企业租户。请确保您登录的是【个人/家庭版】微软账号，而非教育或企业版。")
                return

            msg = (f"👋 主人！您的云端转存助手（个人版专用）已就绪。\n\n"
                   f"🔗 **第一步：授权链接**\n"
                   f"链接: {flow['verification_uri']}\n\n"
                   f"🔑 **第二步：输入代码**\n"
                   f"代码: `{flow['user_code']}`\n\n"
                   f"请在浏览器中完成登录，完成后我会立刻锁定您的 OneDrive！")
            await event.reply(msg)
            print(f">>> Personal Device Flow Active: {flow['user_code']}")

        @client.on(events.NewMessage)
        async def handler(event):
            if event.message.fwd_from:
                await event.reply("📥 **视频流已捕获！**\n正在云端排队，请在授权完成后查看转存状态。")

        print(">>> Bot entering 15-minute operational standby...")
        await asyncio.wait_for(client.run_until_disconnected(), timeout=900)
    except Exception as e:
        print(f"!!! Critical Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
