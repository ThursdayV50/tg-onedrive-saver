import os
import asyncio
import sys
from telethon import TelegramClient, events
from msal import PublicClientApplication

# 核心凭据
API_ID = 32270889
API_HASH = 'fbdbd08d1e471dbc0e679b1fc11a8388'
BOT_TOKEN = '8615577076:AAGCcVkOYGq6uji9y0XlQodEiI3He0i08aU'
# 更换一个 OneDrive Personal 专用的公共 Client ID，尝试解决 KeyError
CLIENT_ID = "000000004c12ae29" 
SCOPES = ['Files.ReadWrite.All']

async def main():
    print(">>> Guhee Cloud Engine (Diagnostic Mode) Starting...")
    sys.stdout.reconfigure(line_buffering=True)
    
    # 清理 session 冲突
    if os.path.exists('guhee_session.session'): os.remove('guhee_session.session')
    
    try:
        client = TelegramClient('guhee_session', API_ID, API_HASH)
        await client.start(bot_token=BOT_TOKEN)
        print(">>> Telegram Client Connected!")

        @client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            print(">>> Received /start, initiating Microsoft Device Flow...")
            app = PublicClientApplication(CLIENT_ID, authority="https://login.microsoftonline.com/common")
            
            # 获取授权 flow
            flow = app.initiate_device_flow(scopes=SCOPES)
            
            # 调试输出：如果报错，打印出完整的 flow 内容
            if "user_code" not in flow:
                error_msg = flow.get("error_description", "Unknown MS Error")
                print(f"!!! Microsoft Auth Error: {flow}")
                await event.reply(f"❌ OneDrive 授权初始化失败。\n\n**原因**: `{error_msg}`\n\n**调试信息**: `{flow.get('error', 'no_code')}`")
                return

            uri = flow.get('verification_uri', 'https://microsoft.com/devicelogin')
            code = flow.get('user_code', 'ERROR')
            
            await event.reply(f"👋 主人！云端转存助手已就绪。\n\n🔗 **授权链接**: {uri}\n🔑 **代码**: `{code}`\n\n请在浏览器完成授权后再转发视频。")
            print(f">>> Device Flow Sent: {code}")

        @client.on(events.NewMessage)
        async def handler(event):
            if event.message.fwd_from:
                await event.reply("📥 **已捕获转发内容！**\n正在云端排队下载并重命名...")

        print(">>> Bot entering standby (15-min cycle)...")
        await asyncio.wait_for(client.run_until_disconnected(), timeout=900)
    except Exception as e:
        print(f"!!! Fatal Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
