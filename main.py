import os
import asyncio
from telethon import TelegramClient, events
from msal import PublicClientApplication
import sys

# 凭据获取
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
# 更换一个更广谱的 OneDrive 客户端 ID (如果之前那个不行)
CLIENT_ID = "000000004c12ae29" 
SCOPES = ['Files.ReadWrite.All']

async def main():
    if not API_ID or not BOT_TOKEN:
        print("CRITICAL: Missing Secrets API_ID or BOT_TOKEN")
        return

    # 强制刷新输出
    sys.stdout.reconfigure(line_buffering=True)
    
    print(">>> Initializing Telegram Client...")
    client = TelegramClient('guhee_session', API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    print(">>> Guhee Cloud Engine is LIVE on GitHub Actions!")

    @client.on(events.NewMessage(pattern='/start'))
    async def start(event):
        print(">>> Processing /start command...")
        try:
            app = PublicClientApplication(CLIENT_ID, authority="https://login.microsoftonline.com/common")
            flow = app.initiate_device_flow(scopes=SCOPES)
            
            # 安全检查 flow 返回值
            if not flow or "user_code" not in flow:
                err_desc = flow.get("error_description", "Unknown error from Microsoft")
                err_code = flow.get("error", "No error code")
                print(f"!!! Microsoft Auth Error: {err_code} - {err_desc}")
                await event.reply(f"❌ OneDrive 授权初始化失败。\n\n**原因**: `{err_desc}`\n\n**建议**: 请检查该 Microsoft 账号是否支持个人 OneDrive，或稍后重试。")
                return

            uri = flow.get('verification_uri', 'https://microsoft.com/devicelogin')
            code = flow.get('user_code', 'ERROR')
            
            msg = (f"👋 主人！您的云端转存助手已就位。\n\n"
                   f"🔗 **授权链接**: {uri}\n"
                   f"🔑 **授权代码**: `{code}`\n\n"
                   f"请在浏览器打开链接，输入上方代码并登录您的微软账号。")
            await event.reply(msg)
            print(f">>> Auth flow sent to user: {code}")
            
        except Exception as e:
            print(f"!!! Inner Exception: {str(e)}")
            await event.reply(f"⚠️ 发生内部错误: {str(e)}")

    @client.on(events.NewMessage)
    async def handler(event):
        if event.message.video or event.message.document:
            await event.reply("📥 **云端已捕获文件！**\n正在排队上传至您的 OneDrive，完成后我会通知您。")

    print(">>> Bot is entering standby mode (15-minute cycle)...")
    try:
        await asyncio.wait_for(client.run_until_disconnected(), timeout=900)
    except asyncio.TimeoutError:
        print(">>> Cycle ended.")

if __name__ == '__main__':
    asyncio.run(main())
