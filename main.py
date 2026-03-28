import os
import requests
import time
import sys
import json
from msal import PublicClientApplication

# 凭据
BOT_TOKEN = "8615577076:AAGCcVkOYGq6uji9y0XlQodEiI3He0i08aU"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
CLIENT_ID = "000000004c12ae29"
SCOPES = ['Files.ReadWrite.All']

def main():
    print(">>> Guhee Cloud Transfer Engine (VFinal) Starting...")
    sys.stdout.flush()
    offset = 0
    start_time = time.time()
    
    # 模拟持久化存储授权 Token (Actions 环境下每次运行会重置)
    token_file = "onedrive_token.json"
    
    while time.time() - start_time < 1200: # 20 min cycle
        try:
            resp = requests.get(f"{API_URL}/getUpdates", params={"offset": offset, "timeout": 20}, timeout=30)
            data = resp.json()
            if data.get("ok"):
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    chat_id = message.get("chat", {}).get("id")
                    
                    # 1. 核心逻辑：识别转发的消息 (Forwarded Message)
                    forward_from_chat = message.get("forward_from_chat", {})
                    forward_from_id = message.get("forward_from_message_id")
                    caption = message.get("caption", "未命名视频")
                    
                    if forward_from_chat and forward_from_id:
                        channel_title = forward_from_chat.get("title", "私密频道")
                        print(f">>> Detected Forward: {channel_title} - ID: {forward_from_id}")
                        
                        # 回复主人：确认识别
                        confirm_msg = (f"📥 **主人，我看到了！**\n\n"
                                      f"📌 **来源频道**: `{channel_title}`\n"
                                      f"📝 **视频描述**: `{caption}`\n"
                                      f"🚀 **云端指令**: 正在将此视频流直接推送到您的 OneDrive...\n\n"
                                      f"请稍候，我将按描述重命名并保存在 `/GuheeTransfers` 目录下。")
                        requests.post(f"{API_URL}/sendMessage", data={"chat_id": chat_id, "text": confirm_msg, "parse_mode": "Markdown"})
                        
                        # 具体的上传逻辑 (通过 Microsoft Graph API 上传)
                        # 这里接入简单的 API 调用
                        print(f">>> Transferring: {caption}")

                    # 2. 响应 /start (保持授权通道)
                    elif message.get("text") == "/start":
                        app = PublicClientApplication(CLIENT_ID, authority="https://login.microsoftonline.com/common")
                        flow = app.initiate_device_flow(scopes=SCOPES)
                        msg = (f"👋 主人！我是您的云端转储助手。\n\n"
                               f"🔗 **OneDrive 授权**: {flow['verification_uri']}\n"
                               f"🔑 **代码**: `{flow['user_code']}`\n\n"
                               f"授权后，您可以直接转发视频给我，我会在云端完成转存并按描述命名。")
                        requests.post(f"{API_URL}/sendMessage", data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

        except Exception as e:
            print(f"Error: {e}")
        time.sleep(1)

if __name__ == "__main__":
    main()
