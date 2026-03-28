import os
import requests
import time

# 凭据
BOT_TOKEN = "8615577076:AAGCcVkOYGq6uji9y0XlQodEiI3He0i08aU"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def main():
    print(">>> Guhee Simple Engine Starting...")
    offset = 0
    # 运行 10 分钟
    start_time = time.time()
    while time.time() - start_time < 600:
        try:
            resp = requests.get(f"{API_URL}/getUpdates", params={"offset": offset, "timeout": 20}, timeout=30)
            data = resp.json()
            if data.get("ok"):
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    chat_id = message.get("chat", {}).get("id")
                    text = message.get("text", "")
                    
                    if text == "/start":
                        print(f">>> Received /start from {chat_id}")
                        # 发送授权链接 (这里直接回复，以后接入 OneDrive)
                        requests.post(f"{API_URL}/sendMessage", data={
                            "chat_id": chat_id,
                            "text": "👋 主人！极简云端引擎已激活。\n\n由于系统环境限制，我为您开启了【基础转存模式】。请稍后，我正在为您对接 OneDrive 授权通道..."
                        })
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(1)

if __name__ == "__main__":
    main()
