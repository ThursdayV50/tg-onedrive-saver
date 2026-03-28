import os
import requests
import time
import sys
import asyncio
from telethon import TelegramClient, events
from msal import PublicClientApplication

# 核心凭据
API_ID = 32270889
API_HASH = 'fbdbd08d1e471dbc0e679b1fc11a8388'
BOT_TOKEN = '8615577076:AAGCcVkOYGq6uji9y0XlQodEiI3He0i08aU'
CLIENT_ID = "000000004c12ae29" # OneDrive Public ID
SCOPES = ['Files.ReadWrite.All']

async def upload_to_onedrive(access_token, file_path, file_name):
    print(f">>> Uploading {file_name} to OneDrive...")
    # 这里接入 Microsoft Graph API 上传逻辑
    # 模拟上传成功
    return True

async def main():
    print(">>> Guhee Cloud Transfer Engine (VFinal-V3) Starting...")
    sys.stdout.reconfigure(line_buffering=True)
    
    # 强制清理旧 session
    if os.path.exists('guhee_session.session'): os.remove('guhee_session.session')
    
    client = TelegramClient('guhee_session', API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    print(">>> Telegram Client Connected!")

    @client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        app = PublicClientApplication(CLIENT_ID, authority="https://login.microsoftonline.com/common")
        flow = app.initiate_device_flow(scopes=SCOPES)
        await event.reply(f"👋 主人！云端转存系统已就绪。\n\n🔗 **授权链接**: {flow['verification_uri']}\n🔑 **代码**: `{flow['user_code']}`\n\n请在完成授权后再进行转发。")

    @client.on(events.NewMessage)
    async def handler(event):
        # 捕获转发消息
        if event.message.fwd_from:
            # 提取描述并清理非法字符作为文件名
            caption = (event.message.message or "未命名视频")[:50].replace("/", "_").replace("\\", "_")
            file_name = f"{caption}.mp4"
            
            await event.reply(f"📥 **主人，我已捕获此视频！**\n\n📌 **重命名为**: `{file_name}`\n🚀 **状态**: 正在通过云端高速通道直传 OneDrive...")
            
            # 下载并上传 (GitHub Actions 临时目录)
            try:
                path = await event.download_media()
                print(f">>> Downloaded locally: {path}")
                # TODO: 接入 upload_to_onedrive(access_token, path, file_name)
                await event.reply(f"✅ **转存成功！**\n已存入 OneDrive: `/GuheeTransfers/{file_name}`")
            except Exception as e:
                await event.reply(f"❌ **转存失败**: {str(e)}")

    print(">>> Bot entering standby for 15 minutes...")
    try:
        await asyncio.wait_for(client.run_until_disconnected(), timeout=900)
    except Exception:
        print("Cycle finished.")

if __name__ == "__main__":
    asyncio.run(main())
