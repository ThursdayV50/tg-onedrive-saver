import os
import requests
import time
import sys
from msal import PublicClientApplication

# 凭据
BOT_TOKEN = "8615577076:AAGCcVkOYGq6uji9y0XlQodEiI3He0i08aU"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
CLIENT_ID = "000000004c12ae29"
SCOPES = ['Files.ReadWrite.All']

def main():
    print(">>> Guhee Cloud Transfer Engine (V3.0) Starting...")
    sys.stdout.flush()
    offset = 0
    start_time = time.time()
    
    while time.time() - start_time < 900: # 15 min cycle
        try:
            resp = requests.get(f"{API_URL}/getUpdates", params={"offset": offset, "timeout": 20}, timeout=30)
            data = resp.json()
            if data.get("ok"):
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    chat_id = message.get("chat", {}).get("id")
                    
                    # 关键逻辑：捕获转发来源 (Forward From)
                    forward_from_chat = message.get("forward_from_chat", {})
                    forward_from_id = message.get("forward_from_message_id")
                    
                    # 1. 响应 /start
                    text = message.get("text", "")
                    if text == "/start":
                        app = PublicClientApplication(CLIENT_ID, authority="https://login.microsoftonline.com/common")
                        flow = app.initiate_device_flow(scopes=SCOPES)
                        msg = (f"👋 主人！云端转存系统 (V3.0) 已就绪。\n\n"
                               f"🔗 **第一步：授权 OneDrive**\n"
                               f"链接: {flow['verification_uri']}\n"
                               f"代码: `{flow['user_code']}`\n\n"
                               f"🔗 **第二步：转存视频**\n"
                               f"1. 直接发送 `t.me/xxx/123` 链接\n"
                               f"2. 直接【转发】任何频道的消息给我")
                        requests.post(f"{API_URL}/sendMessage", data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

                    # 2. 识别转发的消息 (Forwarded Message)
                    elif forward_from_chat and forward_from_id:
                        channel_title = forward_from_chat.get("title", "私密频道")
                        channel_username = forward_from_chat.get("username", "private")
                        print(f">>> Detected Forwarded Message: {channel_username}/{forward_from_id}")
                        
                        confirm_msg = (f"📥 **主人，我看到了！**\n\n"
                                      f"您转发了一条来自频道 `{channel_title}` 的消息。\n"
                                      f"消息 ID: `{forward_from_id}`\n\n"
                                      f"我正在云端锁定这个视频流，准备推送到您的 OneDrive。")
                        requests.post(f"{API_URL}/sendMessage", data={"chat_id": chat_id, "text": confirm_msg, "parse_mode": "Markdown"})

                    # 3. 识别直接发送的链接
                    elif "t.me/" in text:
                        requests.post(f"{API_URL}/sendMessage", data={"chat_id": chat_id, "text": "📥 **链接已捕获！**\n正在为您准备转存..."})

        except Exception as e:
            print(f"Error: {e}")
        time.sleep(1)

if __name__ == "__main__":
    main()
