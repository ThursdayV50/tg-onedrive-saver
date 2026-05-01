import logging
import os
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("onedrive-web-uploader")


QUEUE_ROOT = Path(os.getenv("ONEDRIVE_LOCAL_SYNC_DIR", "/sync")).resolve()
LOGIN_EMAIL = os.getenv("ONEDRIVE_LOGIN_EMAIL", "").strip()
LOGIN_PASSWORD = os.getenv("ONEDRIVE_LOGIN_PASSWORD", "").strip()
PROFILE_DIR = os.getenv("ONEDRIVE_BROWSER_PROFILE_DIR", "/data/browser-profile").strip()
ONEDRIVE_WEB_URL = os.getenv("ONEDRIVE_WEB_URL", "https://onedrive.live.com").strip()
SCAN_INTERVAL_SECONDS = int(os.getenv("ONEDRIVE_SCAN_INTERVAL_SECONDS", "15"))
HEADLESS = os.getenv("ONEDRIVE_HEADLESS", "true").strip().lower() == "true"

SUPPORTED_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def _iter_pending_files() -> list[Path]:
    if not QUEUE_ROOT.exists():
        QUEUE_ROOT.mkdir(parents=True, exist_ok=True)
        return []
    candidates = [p for p in QUEUE_ROOT.rglob("*") if p.is_file()]
    video_files = [p for p in candidates if p.suffix.lower() in SUPPORTED_SUFFIXES]
    return sorted(video_files, key=lambda p: p.stat().st_mtime)


def _login_if_needed(page) -> None:
    page.goto(ONEDRIVE_WEB_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    current = page.url.lower()
    if "login.live.com" not in current and "microsoftonline.com" not in current:
        logger.info("检测到已有登录态，跳过登录。")
        return

    if not LOGIN_EMAIL or not LOGIN_PASSWORD:
        raise RuntimeError("未登录且缺少 ONEDRIVE_LOGIN_EMAIL/ONEDRIVE_LOGIN_PASSWORD。")

    logger.info("开始执行 OneDrive 网页登录。")
    try:
        page.fill('input[type="email"]', LOGIN_EMAIL, timeout=20000)
        page.click('input[type="submit"]')
        page.wait_for_timeout(1000)
    except PlaywrightTimeoutError:
        logger.warning("未捕获到邮箱输入框，继续尝试后续步骤。")

    try:
        page.fill('input[type="password"]', LOGIN_PASSWORD, timeout=20000)
        page.click('input[type="submit"]')
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("未找到密码输入框，可能触发了额外验证。") from exc

    page.wait_for_timeout(2000)
    if page.locator('input[id="idBtn_Back"]').count() > 0:
        page.click('input[id="idBtn_Back"]')

    page.wait_for_load_state("domcontentloaded")
    logger.info("登录流程执行完毕，等待进入 OneDrive。")
    page.goto(ONEDRIVE_WEB_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)


def _upload_one_file(page, file_path: Path) -> None:
    logger.info("准备上传文件: %s", file_path)
    page.goto(ONEDRIVE_WEB_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    upload_inputs = page.locator('input[type="file"]')
    input_count = upload_inputs.count()
    if input_count == 0:
        raise RuntimeError("未找到文件上传控件，页面可能未完全加载或账号无权限。")

    upload_inputs.first.set_input_files(str(file_path))
    logger.info("已触发网页上传: %s", file_path.name)

    # 轮询确认页面上出现文件名，作为上传成功信号
    deadline = time.time() + 3600
    while time.time() < deadline:
        try:
            if page.get_by_text(file_path.name, exact=False).count() > 0:
                logger.info("检测到云端列表出现文件名: %s", file_path.name)
                return
        except Exception:
            pass
        page.wait_for_timeout(3000)
        page.reload(wait_until="domcontentloaded")

    raise RuntimeError(f"上传超时，未在网页中确认文件出现: {file_path.name}")


def run() -> None:
    QUEUE_ROOT.mkdir(parents=True, exist_ok=True)
    Path(PROFILE_DIR).mkdir(parents=True, exist_ok=True)
    logger.info("启动 OneDrive 网页上传器，队列目录: %s", QUEUE_ROOT)

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=HEADLESS,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        _login_if_needed(page)

        while True:
            pending = _iter_pending_files()
            if not pending:
                time.sleep(SCAN_INTERVAL_SECONDS)
                continue

            for file_path in pending:
                try:
                    _upload_one_file(page, file_path)
                    file_path.unlink(missing_ok=True)
                    logger.info("上传完成并删除本地文件: %s", file_path)
                except Exception as exc:
                    logger.exception("上传失败，稍后重试: %s", exc)
                    time.sleep(5)


if __name__ == "__main__":
    run()
