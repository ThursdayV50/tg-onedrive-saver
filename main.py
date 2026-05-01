import logging
import os
import asyncio
import shutil
import json
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

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
TELEGRAM_BOT_API_BASE_URL = os.getenv(
    "TELEGRAM_BOT_API_BASE_URL", "http://telegram-bot-api:8081/bot"
).strip()
TELEGRAM_BOT_API_BASE_FILE_URL = os.getenv(
    "TELEGRAM_BOT_API_BASE_FILE_URL", "http://telegram-bot-api:8081/file/bot"
).strip()
TELEGRAM_BOT_API_ORIGIN = os.getenv("TELEGRAM_BOT_API_ORIGIN", "http://telegram-bot-api:8081").strip()
TELEGRAM_LOCAL_MODE = os.getenv("TELEGRAM_LOCAL_MODE", "true").strip().lower() == "true"
TELEGRAM_REQUEST_TIMEOUT = int(os.getenv("TELEGRAM_REQUEST_TIMEOUT", "1800"))

ONEDRIVE_LOCAL_SYNC_DIR = os.getenv("ONEDRIVE_LOCAL_SYNC_DIR", "/sync").strip()
ONEDRIVE_TARGET_DIR = os.getenv("ONEDRIVE_TARGET_DIR", "TelegramVideos").strip("/")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID", "").strip()

def build_storage_path(file_name: str) -> str:
    safe_name = file_name.replace("/", "_").replace("\\", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_dir = Path(ONEDRIVE_LOCAL_SYNC_DIR) / ONEDRIVE_TARGET_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return str(target_dir / f"{timestamp}_{safe_name}")



def check_allowed_chat(chat_id: int) -> bool:
    if not ALLOWED_CHAT_ID:
        return True
    try:
        return int(ALLOWED_CHAT_ID) == chat_id
    except ValueError:
        logger.warning("ALLOWED_CHAT_ID 不是有效整数，已忽略限制。")
        return True


def _download_from_local_bot_api(file_path: str, local_target_path: str) -> None:
    if file_path.startswith("/") and os.path.exists(file_path):
        shutil.copy2(file_path, local_target_path)
        return

    if file_path.startswith("http://") or file_path.startswith("https://"):
        url = file_path
    elif file_path.startswith("/"):
        url = f"{TELEGRAM_BOT_API_ORIGIN}{file_path}"
    else:
        # 兼容返回相对路径的情况
        url = (
            f"{TELEGRAM_BOT_API_BASE_FILE_URL}{TELEGRAM_BOT_TOKEN}/"
            f"{file_path.lstrip('/')}"
        )

    with urlopen(url, timeout=TELEGRAM_REQUEST_TIMEOUT) as resp:  # nosec B310
        if resp.status != 200:
            raise RuntimeError(f"下载失败，HTTP {resp.status}")
        with open(local_target_path, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "发送视频给我，我会先保存到上传队列，随后由网页版 OneDrive 上传器自动提交。"
    )


# 使用后台任务并发下载，避免阻塞主消息循环
async def _process_video_task(context: ContextTypes.DEFAULT_TYPE, chat_id: int, telegram_file_id: str, origin_name: str, file_size: int, local_target_path: str) -> None:
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            tg_file = await context.bot.get_file(
                telegram_file_id,
                read_timeout=TELEGRAM_REQUEST_TIMEOUT,
                write_timeout=120,
                connect_timeout=30,
                pool_timeout=30,
            )
            if tg_file.file_path:
                await asyncio.to_thread(
                    _download_from_local_bot_api, tg_file.file_path, local_target_path
                )
            else:
                await tg_file.download_to_drive(
                    custom_path=local_target_path,
                    read_timeout=TELEGRAM_REQUEST_TIMEOUT,
                    write_timeout=120,
                    connect_timeout=30,
                    pool_timeout=30,
                )
            meta_path = f"{local_target_path}.meta.json"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "chat_id": chat_id,
                        "origin_name": origin_name,
                        "queued_path": local_target_path,
                    },
                    f,
                    ensure_ascii=False,
                )
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"下载完成，文件已加入 OneDrive 网页上传队列。\n本地路径：{local_target_path}"
            )
            logger.info("文件已写入网页上传队列: %s", local_target_path)
            break
        except Exception as exc:
            err_msg = str(exc)
            logger.warning("处理视频失败 (尝试 %d/%d): %s", attempt, max_retries, err_msg)
            if "temporarily unavailable" in err_msg and attempt < max_retries:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"文件 {origin_name} 暂时不可用，等待 15 秒后进行第 {attempt + 1} 次重试..."
                )
                await asyncio.sleep(15)
                continue
            
            logger.exception("处理视频最终失败")
            if "File is too big" in err_msg:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"下载失败：文件过大 ({origin_name})。请确认自建 API 正常运行。"
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"下载失败 ({origin_name})：{err_msg}"
                )
            break

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

    local_target_path = build_storage_path(origin_name)

    await update.message.reply_text(f"收到视频 {origin_name}，开始后台下载并加入上传队列...")
    logger.info("开始处理视频: name=%s size=%s chat_id=%s", origin_name, file_size, chat_id)

    # 提交为后台任务，不阻塞当前 handler，允许并发处理多个文件
    asyncio.create_task(
        _process_video_task(
            context, chat_id, telegram_file_id, origin_name, file_size, local_target_path
        )
    )



def validate_env() -> None:
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if missing:
        raise RuntimeError(f"缺少环境变量: {', '.join(missing)}")
    Path(ONEDRIVE_LOCAL_SYNC_DIR).mkdir(parents=True, exist_ok=True)



def main() -> None:
    validate_env()
    logger.info("启动 Telegram Bot，队列目录: %s", ONEDRIVE_LOCAL_SYNC_DIR)

    builder = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .base_url(TELEGRAM_BOT_API_BASE_URL)
        .base_file_url(TELEGRAM_BOT_API_BASE_FILE_URL)
        .local_mode(TELEGRAM_LOCAL_MODE)
        .read_timeout(TELEGRAM_REQUEST_TIMEOUT)
        .write_timeout(120)
        .connect_timeout(30)
        .pool_timeout(30)
    )
    app = builder.build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, video_handler))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
