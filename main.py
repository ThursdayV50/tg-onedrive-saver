import os
import requests
import time
import sys
import re
from msal import PublicClientApplication

# 凭据
BOT_TOKEN = "8615577076:AAGCcVkOYGq6uji9y0XlQodEiI3He0i08aU"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
# OneDrive 公共客户端 ID
CLIENT_ID = "000000004c12ae29"
SCOPES = ['Files.ReadWrite.All']

def main():
    print(">>> Guhee Cloud Transfer Engine (V2.0) Starting...")
    sys.stdout.flush()
    offset = 0
    start_time = time.time()
    
    while time.time() - start_time < 900: # 运行 15 分钟
        try:
            resp = requests.get(f"{API_URL}/getUpdates", params={"offset": offset, "timeout": 20}, timeout=30)
            data = resp.json()
            if data.get("ok"):
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    chat_id = message.get("chat", {}).get("id")
                    text = message.get("text", "")
                    
                    if not text: continue

                    # 逻辑1: 响应 /start 命令并提供 OneDrive 授权
                    if text == "/start":
                        app = PublicClientApplication(CLIENT_ID, authority="https://login.microsoftonline.com/common")
                        flow = app.initiate_device_flow(scopes=SCOPES)
                        if "user_code" in flow:
                            msg = (f"👋 主人！云端转存系统已准备就绪。\n\n"
                                   f"🔗 **第一步：授权 OneDrive**\n"
                                   f"请点击链接: {flow['verification_uri']}\n"
                                   f"输入代码: `{flow['user_code']}`\n\n"
                                   f"🔗 **第二步：转存视频**\n"
                                   f"授权成功后，直接把视频链接（如 `t.me/xxx/123`）发给我即可。")
                        else:
                            msg = "❌ 初始化 OneDrive 授权失败，请稍后重试。"
                        requests.post(f"{API_URL}/sendMessage", data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

                    # 逻辑2: 识别链接 (t.me/channel/id)
                    elif "t.me/" in text:
                        match = re.search(r't\.me/([^/]+)/(\d+)', text)
                        if match:
                            channel = match.group(1)
                            msg_id = match.group(2)
                            print(f">>> Detected link: {channel}/{msg_id}")
                            requests.post(f"{API_URL}/sendMessage", data={
                                "chat_id": chat_id, 
                                "text": f"📥 **正在解析链接内容...**\n频道: `{channel}`\n消息ID: `{msg_id}`\n\n正在为您寻找视频流并推送到 OneDrive，请稍候。"
                            })
                            # 后续这里会接入具体的 Telethon 抓取和 Graph API 上传
                        else:
                            requests.post(f"{API_URL}/sendMessage", data={"chat_id": chat_id, "text": "⚠️ 链接格式似乎不正确，请发送类似 `t.me/name/123` 的链接。"})

        except Exception as e:
            print(f"Error: {e}")
        time.sleep(1)

if __name__ == "__main__":
    main()
