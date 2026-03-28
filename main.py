import os
import asyncio
import sys
from telethon import TelegramClient, events
from msal import PublicClientApplication

# 核心凭据
API_ID = 32270889
API_HASH = 'fbdbd08d1e471dbc0e679b1fc11a8388'
BOT_TOKEN = '8615577076:AAGCcVkOYGq6uji9y0XlQodEiI3He0i08aU'

# 微软官方为所有开发人员公开预留的公共客户端 ID (用于 OneDrive 转存最稳的 ID)
CLIENT_ID = "24022753-3939-4ac5-9174-a690d815e966"
# 只请求基础读写，MSAL 会自动静默处理 offline_access
SCOPES = ['Files.ReadWrite.All']

async def main():
    print(">>> Guhee Cloud Engine (Universal Auth Mode) Starting...")
    sys.stdout.reconfigure(line_buffering=True)
    
    # 彻底清理 session 状态，杜绝一切残留
    if os.path.exists('guhee_session.session'): os.remove('guhee_session.session')
    
    try:
        client = TelegramClient('guhee_session', API_ID, API_HASH)
        await client.start(bot_token=BOT_TOKEN)
        print(">>> Telegram Client Connected!")

        @client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            print(">>> Received /start, initiating Microsoft Device Flow...")
            # 关键：authority 必须使用 /common 并由后端根据 Client ID 自动分流
            app = PublicClientApplication(CLIENT_ID, authority="https://login.microsoftonline.com/common")
            
            flow = app.initiate_device_flow(scopes=SCOPES)
            
            # 严格错误校验
            if not flow or "user_code" not in flow:
                err_desc = flow.get("error_description", "Unknown Microsoft error")
                print(f"!!! Microsoft Auth Error: {flow}")
                await event.reply(f"❌ OneDrive 授权初始化失败。\n\n**原因**: `{err_desc}`\n\n请确保您的微软账号是个人账号或已开启第三方授权。")
                return

            msg = (f"👋 主人！您的云端转存助手已就绪。\n\n"
                   f"🔗 **授权链接**: {flow['verification_uri']}\n"
                   f"🔑 **授权代码**: `{flow['user_code']}`\n\n"
                   f"请点开链接输入代码并登录。")
            await event.reply(msg)
            print(f">>> Device Flow Active: {flow['user_code']}")

        @client.on(events.NewMessage)
        async def handler(event):
            # 捕获转发来源
            if event.message.fwd_from:
                await event.reply("📥 **主人，我已锁定这个视频内容！**\n授权完成后，我将自动执行转存。")

        print(">>> Bot entering 15-minute operational standby...")
        await asyncio.wait_for(client.run_until_disconnected(), timeout=900)
    except Exception as e:
        print(f"!!! Critical Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
