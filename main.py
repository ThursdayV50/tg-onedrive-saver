import os
import asyncio
import sys
from telethon import TelegramClient, events
from msal import PublicClientApplication

# 获取凭据
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = '8615577076:AAGCcVkOYGq6uji9y0XlQodEiI3He0i08aU'
# 备用公共 ID 尝试
CLIENT_ID = "000000004c12ae29" 
SCOPES = ['Files.ReadWrite.All']

async def main():
    if not API_ID or not BOT_TOKEN:
        print("Missing credentials! Please check GitHub Secrets.")
        return

    # 强制刷新输出
    sys.stdout.reconfigure(line_buffering=True)

    client = TelegramClient('guhee_session', API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    print(">>> Guhee Cloud Engine is ONLINE!")

    @client.on(events.NewMessage(pattern='/start'))
    async def start(event):
        print(">>> Received /start")
        app = PublicClientApplication(CLIENT_ID, authority="https://login.microsoftonline.com/common")
        flow = app.initiate_device_flow(scopes=SCOPES)
        
        # 强制检查 flow 结构，绝对不直接访问 key
        if flow and "verification_uri" in flow and "user_code" in flow:
            uri = flow["verification_uri"]
            code = flow["user_code"]
            msg = f"👋 主人！您的云端转存助手已上线。\n\n🔗 授权链接: {uri}\n🔑 授权代码: `{code}`"
            await event.reply(msg)
        else:
            error_info = str(flow.get("error_description", "Unknown Microsoft Error"))
            print(f"!!! Flow Error: {flow}")
            await event.reply(f"❌ 初始化 OneDrive 授权失败。\n错误详情: `{error_info}`")

    @client.on(events.NewMessage)
    async def handler(event):
        if event.message.video or event.message.document:
            await event.reply("📥 云端已捕获文件，正在为您处理...")

    try:
        await asyncio.wait_for(client.run_until_disconnected(), timeout=600)
    except Exception as e:
        print(f"Cycle ended: {e}")

if __name__ == '__main__':
    asyncio.run(main())
