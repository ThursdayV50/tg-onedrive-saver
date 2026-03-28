import os
import asyncio
from telethon import TelegramClient, events
from msal import PublicClientApplication
import json

# 从 GitHub Secrets 获取凭据
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
CLIENT_ID = "000000004c12ae29" # OneDrive Public ID
SCOPES = ['Files.ReadWrite.All']

async def main():
    if not API_ID or not BOT_TOKEN:
        print("Missing credentials!")
        return

    # GitHub Actions 环境下使用内存 session 或临时文件
    client = TelegramClient('guhee_session', API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    print("Bot is online on GitHub Actions!")

    @client.on(events.NewMessage(pattern='/start'))
    async def start(event):
        app = PublicClientApplication(CLIENT_ID, authority="https://login.microsoftonline.com/common")
        flow = app.initiate_device_flow(scopes=SCOPES)
        msg = (f"👋 主人！您的云端转存助手已上线。\n\n"
               f"🔗 授权链接: {flow['verification_uri']}\n"
               f"🔑 授权代码: `{flow['user_code']}`")
        await event.reply(msg)

    @client.on(events.NewMessage)
    async def handler(event):
        if event.message.video or event.message.document:
            await event.reply("📥 云端已收到文件，正在处理中...")

    # 在 Actions 中我们只运行一段时间，或者通过 Webhook
    # 这里我们让它运行 10 分钟作为一个示例周期的拉取
    try:
        await asyncio.wait_for(client.run_until_disconnected(), timeout=300)
    except asyncio.TimeoutError:
        print("Cycle finished.")

if __name__ == '__main__':
    asyncio.run(main())
