import logging
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

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
ONEDRIVE_TARGET_DIR = os.getenv("ONEDRIVE_TARGET_DIR", "TelegramVideos").strip("/")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID", "").strip()
RCLONE_REMOTE = os.getenv("RCLONE_REMOTE", "onedrive").strip()
RCLONE_CONFIG_FILE = os.getenv("RCLONE_CONFIG_FILE", "/data/rclone.conf").strip()


class RcloneUploader:
    def __init__(self, remote_name: str, config_file: str):
        self.remote_name = remote_name
        self.config_file = config_file

    def _remote_target(self, remote_rel_path: str) -> str:
        return f"{self.remote_name}:{remote_rel_path}"

    def _base_command(self) -> list[str]:
        return ["rclone", "--config", self.config_file]

    def upload_file(self, local_file: str, remote_rel_path: str) -> str:
        target = self._remote_target(remote_rel_path)
        cmd = [*self._base_command(), "copyto", local_file, target]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "未知错误"
            raise RuntimeError(f"rclone 上传失败: {message}")
        return target

    def get_share_link(self, remote_rel_path: str) -> str:
        target = self._remote_target(remote_rel_path)
        cmd = [*self._base_command(), "link", target]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return ""
        return result.stdout.strip()


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
        "首次运行前请先完成 rclone OneDrive 授权配置。"
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

    uploader: RcloneUploader = context.application.bot_data["onedrive_uploader"]
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
        remote_target = uploader.upload_file(tmp_file_path, remote_path)
        share_link = uploader.get_share_link(remote_path)
        if share_link:
            await update.message.reply_text(f"上传成功。\nOneDrive 链接：{share_link}")
            logger.info("上传成功: %s", share_link)
        else:
            await update.message.reply_text(f"上传成功。\n远端路径：{remote_target}")
            logger.info("上传成功，但未获取分享链接: %s", remote_target)
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
    if not RCLONE_REMOTE:
        missing.append("RCLONE_REMOTE")
    if missing:
        raise RuntimeError(f"缺少环境变量: {', '.join(missing)}")
    if not os.path.exists(RCLONE_CONFIG_FILE):
        raise RuntimeError(f"找不到 rclone 配置文件: {RCLONE_CONFIG_FILE}")


def main() -> None:
    validate_env()
    probe = subprocess.run(["rclone", "version"], capture_output=True, text=True, check=False)
    if probe.returncode != 0:
        message = probe.stderr.strip() or probe.stdout.strip() or "未知错误"
        raise RuntimeError(f"rclone 不可用: {message}")

    uploader = RcloneUploader(RCLONE_REMOTE, RCLONE_CONFIG_FILE)
    logger.info("rclone 检查完成，启动 Telegram Bot...")

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
