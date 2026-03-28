import os
import asyncio
from telethon import TelegramClient, events
from msal import PublicClientApplication
import json

# 从 GitHub Secrets 获取凭证
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
# 备用公共 ID 尝试
CLIENT_ID = "000000004c12ae29" 
SCOPES = ['Files.ReadWrite.All']

async def main():
    if not API_ID or not BOT_TOKEN:
        print("Missing credentials! Please check GitHub Secrets.")
        return

    client = TelegramClient('guhee_session', API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    print(">>> Guhee Cloud Engine is ONLINE on GitHub Actions!")

    @client.on(events.NewMessage(pattern='/start'))
    async def start(event):
        print(">>> Received /start command")
        app = PublicClientApplication(CLIENT_ID, authority="https://login.microsoftonline.com/common")
        
        # 尝试初始化设备流
        flow = app.initiate_device_flow(scopes=SCOPES)
        
        if "user_code" not in flow:
            error_msg = flow.get("error_description", "Unknown error from Microsoft Auth")
            print(f">>> Microsoft Auth Error: {flow}")
            await event.reply(f"❌ 初始化 OneDrive 授权失败。\n错误详情: `{error_msg}`\n\n请检查网络或稍后再试。")
            return
            
        msg = (f"👋 主人！您的云端转存助手已上线。\n\n"
               f"🔗 授权链接: {flow['verification_uri']}\n"
               f"🔑 授权代码: `{flow['user_code']}`\n\n"
               f"请在浏览器打开链接并输入代码。")
        await event.reply(msg)
        
        # 在 Actions 中我们不阻塞等待，先让用户看到链接
        print(f">>> User Code sent: {flow['user_code']}")

    @client.on(events.NewMessage)
    async def handler(event):
        if event.message.video or event.message.document:
            await event.reply("📥 云端已捕获文件，正在为您处理上传逻辑...")

    # 每次运行持续 15 分钟，确保有足够时间接收转发
    try:
        print(">>> Bot is running for a 15-minute cycle...")
        await asyncio.wait_for(client.run_until_disconnected(), timeout=900)
    except asyncio.TimeoutError:
        print(">>> Cycle finished naturally.")

if __name__ == '__main__':
    asyncio.run(main())
