import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import msal
import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("tg-onedrive-bot")


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID", "").strip()
ONEDRIVE_TARGET_DIR = os.getenv("ONEDRIVE_TARGET_DIR", "TelegramVideos").strip("/")
TOKEN_CACHE_FILE = os.getenv("MSAL_CACHE_FILE", "msal_token_cache.bin")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID", "").strip()

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
SCOPES = ["Files.ReadWrite.All", "offline_access", "User.Read"]
CHUNK_SIZE = 3_276_800  # 320KB 的整数倍，适配 OneDrive 分块上传要求


class OneDriveUploader:
    def __init__(self, client_id: str, cache_file: str):
        self.client_id = client_id
        self.cache_file = cache_file
        self.token_cache = msal.SerializableTokenCache()
        self._load_cache()
        self.app = msal.PublicClientApplication(
            client_id=self.client_id,
            authority="https://login.microsoftonline.com/consumers",
            token_cache=self.token_cache,
        )

    def _load_cache(self) -> None:
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r", encoding="utf-8") as f:
                self.token_cache.deserialize(f.read())

    def _save_cache(self) -> None:
        if self.token_cache.has_state_changed:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                f.write(self.token_cache.serialize())

    def get_access_token(self) -> str:
        accounts = self.app.get_accounts()
        result = None
        if accounts:
            result = self.app.acquire_token_silent(SCOPES, account=accounts[0])

        if not result or "access_token" not in result:
            flow = self.app.initiate_device_flow(scopes=SCOPES)
            if "user_code" not in flow:
                raise RuntimeError(f"设备码初始化失败: {flow}")

            logger.info("请在浏览器打开: %s", flow["verification_uri"])
            logger.info("输入设备码: %s", flow["user_code"])
            logger.info("完成登录后脚本将自动继续...")
            result = self.app.acquire_token_by_device_flow(flow)

        self._save_cache()

        if "access_token" not in result:
            raise RuntimeError(f"获取微软访问令牌失败: {result}")
        return result["access_token"]

    def _authorized_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.get_access_token()}"}

    def upload_file(self, local_file: str, remote_rel_path: str) -> dict:
        file_size = os.path.getsize(local_file)
        if file_size <= 4 * 1024 * 1024:
            return self._upload_small_file(local_file, remote_rel_path)
        return self._upload_large_file(local_file, remote_rel_path, file_size)

    def _upload_small_file(self, local_file: str, remote_rel_path: str) -> dict:
        encoded = quote(remote_rel_path, safe="/")
        url = f"{GRAPH_ROOT}/me/drive/root:/{encoded}:/content"
        headers = self._authorized_headers()
        headers["Content-Type"] = "application/octet-stream"
        with open(local_file, "rb") as f:
            resp = requests.put(url, headers=headers, data=f, timeout=120)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"小文件上传失败: {resp.status_code} {resp.text}")
        return resp.json()

    def _upload_large_file(self, local_file: str, remote_rel_path: str, file_size: int) -> dict:
        encoded = quote(remote_rel_path, safe="/")
        session_url = f"{GRAPH_ROOT}/me/drive/root:/{encoded}:/createUploadSession"
        session_resp = requests.post(
            session_url,
            headers={**self._authorized_headers(), "Content-Type": "application/json"},
            json={"item": {"@microsoft.graph.conflictBehavior": "rename"}},
            timeout=120,
        )
        if session_resp.status_code not in (200, 201):
            raise RuntimeError(
                f"创建分块上传会话失败: {session_resp.status_code} {session_resp.text}"
            )

        upload_url = session_resp.json()["uploadUrl"]
        with open(local_file, "rb") as f:
            start = 0
            while start < file_size:
                end = min(start + CHUNK_SIZE, file_size) - 1
                chunk = f.read(end - start + 1)
                headers = {
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                }
                chunk_resp = requests.put(upload_url, headers=headers, data=chunk, timeout=300)
                if chunk_resp.status_code in (200, 201):
                    return chunk_resp.json()
                if chunk_resp.status_code != 202:
                    raise RuntimeError(
                        f"分块上传失败: {chunk_resp.status_code} {chunk_resp.text}"
                    )
                start = end + 1

        raise RuntimeError("分块上传未返回最终完成状态")


def build_remote_path(file_name: str) -> str:
    safe_name = file_name.replace("/", "_").replace("\\", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ONEDRIVE_TARGET_DIR}/{timestamp}_{safe_name}"


def check_allowed_chat(chat_id: int) -> bool:
    if not ALLOWED_CHAT_ID:
        return True
    try:
        return int(ALLOWED_CHAT_ID) == chat_id
    except ValueError:
        logger.warning("ALLOWED_CHAT_ID 不是有效整数，已忽略限制。")
        return True


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "发送视频给我，我会自动上传到你的 OneDrive。\n"
        "首次运行时请查看控制台提示，完成微软设备码登录。"
    )


async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    chat_id = update.effective_chat.id if update.effective_chat else 0
    if not check_allowed_chat(chat_id):
        await update.message.reply_text("当前聊天未授权。")
        return

    video = update.message.video
    document = update.message.document
    if not video and not (document and document.mime_type and document.mime_type.startswith("video/")):
        return

    if video:
        telegram_file_id = video.file_id
        file_size = video.file_size or 0
        origin_name = video.file_name or f"video_{video.file_unique_id}.mp4"
    else:
        telegram_file_id = document.file_id  # type: ignore[union-attr]
        file_size = document.file_size or 0  # type: ignore[union-attr]
        origin_name = document.file_name or f"video_{document.file_unique_id}.mp4"  # type: ignore[union-attr]

    uploader: OneDriveUploader = context.application.bot_data["onedrive_uploader"]
    remote_path = build_remote_path(origin_name)

    await update.message.reply_text("收到视频，开始下载并上传到 OneDrive...")
    logger.info("开始处理视频: name=%s size=%s chat_id=%s", origin_name, file_size, chat_id)

    suffix = Path(origin_name).suffix or ".mp4"
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_file_path = tmp_file.name
    tmp_file.close()

    try:
        tg_file = await context.bot.get_file(telegram_file_id)
        await tg_file.download_to_drive(custom_path=tmp_file_path)
        upload_result = uploader.upload_file(tmp_file_path, remote_path)
        web_url = upload_result.get("webUrl", "(无返回链接)")
        await update.message.reply_text(f"上传成功。\nOneDrive 链接：{web_url}")
        logger.info("上传成功: %s", web_url)
    except Exception as exc:
        logger.exception("处理视频失败")
        await update.message.reply_text(f"上传失败：{exc}")
    finally:
        try:
            os.remove(tmp_file_path)
        except OSError:
            pass


def validate_env() -> None:
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not MS_CLIENT_ID:
        missing.append("MS_CLIENT_ID")
    if missing:
        raise RuntimeError(f"缺少环境变量: {', '.join(missing)}")


def main() -> None:
    validate_env()

    uploader = OneDriveUploader(MS_CLIENT_ID, TOKEN_CACHE_FILE)
    uploader.get_access_token()
    logger.info("微软账号授权成功，启动 Telegram Bot...")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.bot_data["onedrive_uploader"] = uploader

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(
        MessageHandler(
            filters.VIDEO | filters.Document.VIDEO,
            video_handler,
        )
    )

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
