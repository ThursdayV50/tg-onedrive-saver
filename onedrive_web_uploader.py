import logging
import os
import re
import time
import json
from pathlib import Path

import requests
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
ONEDRIVE_FILES_URL = os.getenv(
    "ONEDRIVE_FILES_URL", "https://g1479169422163-my.sharepoint.com/my"
).strip()
SCAN_INTERVAL_SECONDS = int(os.getenv("ONEDRIVE_SCAN_INTERVAL_SECONDS", "15"))
AUTH_CHECK_INTERVAL_SECONDS = int(os.getenv("ONEDRIVE_AUTH_CHECK_INTERVAL_SECONDS", "600"))
HEADLESS = os.getenv("ONEDRIVE_HEADLESS", "true").strip().lower() == "true"
DEBUG_DIR = Path(os.getenv("ONEDRIVE_DEBUG_DIR", "/data/debug")).resolve()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_BOT_API_ORIGIN = os.getenv("TELEGRAM_BOT_API_ORIGIN", "http://telegram-bot-api:8081").strip()

SUPPORTED_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def _iter_pending_files() -> list[Path]:
    if not QUEUE_ROOT.exists():
        QUEUE_ROOT.mkdir(parents=True, exist_ok=True)
        return []
    candidates = [p for p in QUEUE_ROOT.rglob("*") if p.is_file()]
    video_files = [p for p in candidates if p.suffix.lower() in SUPPORTED_SUFFIXES]
    return sorted(video_files, key=lambda p: p.stat().st_mtime)


def _meta_path_for(file_path: Path) -> Path:
    return file_path.with_name(f"{file_path.name}.meta.json")


def _load_meta(file_path: Path) -> dict:
    meta_path = _meta_path_for(file_path)
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _notify_upload_success(file_path: Path) -> None:
    meta = _load_meta(file_path)
    chat_id = meta.get("chat_id")
    if not chat_id or not TELEGRAM_BOT_TOKEN:
        return

    origin_name = meta.get("origin_name", file_path.name)
    queued_name = file_path.name
    text = (
        "OneDrive 上传完成\n"
        f"原始文件名: {origin_name}\n"
        f"云端文件名: {queued_name}"
    )
    url = f"{TELEGRAM_BOT_API_ORIGIN}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=15)
        if resp.status_code != 200:
            logger.warning("上传完成通知发送失败: HTTP %s %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.warning("上传完成通知发送异常: %s", exc)


def _cleanup_meta(file_path: Path) -> None:
    meta_path = _meta_path_for(file_path)
    try:
        meta_path.unlink(missing_ok=True)
    except Exception:
        pass


def _save_debug_snapshot(page, reason: str) -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe_reason = re.sub(r"[^a-zA-Z0-9_-]+", "_", reason)[:40]
    png_path = DEBUG_DIR / f"{ts}_{safe_reason}.png"
    html_path = DEBUG_DIR / f"{ts}_{safe_reason}.html"
    try:
        page.screenshot(path=str(png_path), full_page=True)
        html_path.write_text(page.content(), encoding="utf-8")
        logger.info("已保存调试快照: %s , %s", png_path, html_path)
    except Exception as exc:
        logger.warning("保存调试快照失败: %s", exc)


def _is_login_page(page) -> bool:
    current = page.url.lower()
    if "login.live.com" in current or "microsoftonline.com" in current:
        return True
    if page.locator('input[type="email"]').count() > 0:
        return True
    return False


def _perform_login(page) -> None:
    if not LOGIN_EMAIL or not LOGIN_PASSWORD:
        raise RuntimeError("未登录且缺少 ONEDRIVE_LOGIN_EMAIL/ONEDRIVE_LOGIN_PASSWORD。")

    logger.info("开始执行 OneDrive 网页登录。")
    try:
        # 兼容“选择账户”页面：优先点击“使用其他账户”
        for txt in ["使用其他账户", "Use another account", "Sign in with another account"]:
            if page.get_by_text(txt, exact=False).count() > 0:
                page.get_by_text(txt, exact=False).first.click()
                page.wait_for_timeout(1200)
                break

        email_inputs = [
            'input[type="email"]',
            'input[name="loginfmt"]',
            'input#i0116',
        ]
        filled = False
        for sel in email_inputs:
            if page.locator(sel).count() > 0:
                page.fill(sel, LOGIN_EMAIL, timeout=20000)
                filled = True
                break
        if filled:
            # 下一步/继续
            for sel in ['input[type="submit"]', 'button[type="submit"]', 'input#idSIButton9']:
                if page.locator(sel).count() > 0:
                    page.locator(sel).first.click()
                    break
            page.wait_for_timeout(1500)
        else:
            logger.warning("未捕获到邮箱输入框，继续尝试密码页或其他流程。")
    except PlaywrightTimeoutError:
        logger.warning("邮箱步骤超时，继续尝试后续步骤。")

    try:
        pwd_selectors = [
            'input[type="password"]',
            'input[name="passwd"]',
            'input#i0118',
        ]
        filled_pwd = False
        for sel in pwd_selectors:
            if page.locator(sel).count() > 0:
                page.fill(sel, LOGIN_PASSWORD, timeout=20000)
                filled_pwd = True
                break
        if not filled_pwd:
            _save_debug_snapshot(page, "password_input_not_found")
            raise RuntimeError("未找到密码输入框，可能触发了额外验证/账户选择。")

        for sel in ['input[type="submit"]', 'button[type="submit"]', 'input#idSIButton9']:
            if page.locator(sel).count() > 0:
                page.locator(sel).first.click()
                break
    except PlaywrightTimeoutError as exc:
        _save_debug_snapshot(page, "password_step_timeout")
        raise RuntimeError("密码步骤超时，可能触发了额外验证。") from exc

    page.wait_for_timeout(2000)
    if page.locator('input[id="idBtn_Back"]').count() > 0:
        page.click('input[id="idBtn_Back"]')

    page.wait_for_load_state("domcontentloaded")
    logger.info("登录流程执行完毕，等待进入 OneDrive。")
    page.goto(ONEDRIVE_FILES_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)


def _login_if_needed(page) -> None:
    # 先尝试进入目标文件页，再判断是否需要登录，避免误判“已有登录态”
    page.goto(ONEDRIVE_FILES_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    if _is_login_page(page):
        _perform_login(page)
        return

    logger.info("检测到已有登录态，跳过登录。")


def _ensure_files_page(page) -> None:
    candidates = [
        ONEDRIVE_FILES_URL,
        "https://www.office.com/launch/onedrive",
        "https://onedrive.live.com/?v=files",
    ]
    for url in candidates:
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            current = page.url.lower()
            if _is_login_page(page):
                logger.info("检测到登录页，尝试自动登录。")
                _perform_login(page)
                current = page.url.lower()
            if "microsoft.com/microsoft-365/onedrive/online-cloud-storage" in current:
                # 营销页时尝试点“登录/转到OneDrive”
                for btn_pat in [
                    re.compile(r"sign in|login|log in|登录", re.IGNORECASE),
                    re.compile(r"go to onedrive|open onedrive|转到 onedrive|打开 onedrive", re.IGNORECASE),
                ]:
                    try:
                        btn = page.get_by_role("link", name=btn_pat)
                        if btn.count() > 0:
                            btn.first.click()
                            page.wait_for_timeout(2500)
                            break
                    except Exception:
                        pass
            # 能看到上传控件或新建按钮，视为已进入文件页
            if page.locator('input[type="file"]').count() > 0:
                logger.info("已进入文件页面（检测到 file input）: %s", page.url)
                return
            if page.get_by_role("button", name=re.compile(r"new|新建", re.IGNORECASE)).count() > 0:
                logger.info("已进入文件页面（检测到新建按钮）: %s", page.url)
                return
            if "sharepoint.com" in page.url.lower() or "onedrive.live.com" in page.url.lower():
                logger.info("已进入 OneDrive/SharePoint 页面: %s", page.url)
                return
        except Exception:
            continue

    _save_debug_snapshot(page, "not_in_files_page")
    raise RuntimeError(
        f"未能进入 OneDrive 文件页面，当前页面: {page.url}。"
        "请检查 ONEDRIVE_FILES_URL 或账号权限。"
    )


def _try_upload_by_input(page, file_path: Path) -> bool:
    selectors = [
        'input[type="file"]',
        'input[data-automationid="UploadInput"]',
        'input[aria-label*="upload" i]',
    ]
    for sel in selectors:
        inputs = page.locator(sel)
        if inputs.count() > 0:
            try:
                inputs.first.set_input_files(str(file_path), timeout=3000)
                return True
            except Exception:
                pass
    return False


def _try_upload_by_button(page, file_path: Path) -> bool:
    patterns = [
        re.compile(r"upload", re.IGNORECASE),
        re.compile(r"file upload", re.IGNORECASE),
        re.compile(r"上传"),
        re.compile(r"上载"),
        re.compile(r"文件上传"),
    ]

    for pat in patterns:
        # 直接点击“上传”按钮，若触发 file chooser 则上传
        try:
            with page.expect_file_chooser(timeout=3000) as fc_info:
                page.get_by_role("button", name=pat).first.click(timeout=3000)
            chooser = fc_info.value
            chooser.set_files(str(file_path), timeout=3000)
            return True
        except Exception:
            pass

        # 某些 UI 先点“新建”，再点“上传文件”
        try:
            new_btn = page.get_by_role("button", name=re.compile(r"new|新建", re.IGNORECASE))
            if new_btn.count() > 0:
                new_btn.first.click(timeout=3000)
                page.wait_for_timeout(800)
        except Exception:
            pass

        try:
            with page.expect_file_chooser(timeout=3000) as fc_info:
                page.get_by_role("menuitem", name=pat).first.click(timeout=3000)
            chooser = fc_info.value
            chooser.set_files(str(file_path), timeout=3000)
            return True
        except Exception:
            pass

    # 针对 OneDrive 中文界面：菜单项可能是 span.ms-ContextualMenu-itemText，不带 role=menuitem
    text_selectors = [
        'span.ms-ContextualMenu-itemText:has-text("文件上传")',
        'span.ms-ContextualMenu-itemText:has-text("上载文件")',
        'span.ms-ContextualMenu-itemText:has-text("Upload files")',
    ]
    for sel in text_selectors:
        try:
            text_node = page.locator(sel).first
            if text_node.count() == 0:
                continue
            with page.expect_file_chooser(timeout=3000) as fc_info:
                # 文本节点常为 generic，不可直接触发上传，优先点击其父级可点击菜单项
                clickable = text_node.locator(
                    "xpath=ancestor::*[contains(@class,'ms-ContextualMenu-link')][1]"
                )
                if clickable.count() > 0:
                    clickable.click(timeout=3000)
                else:
                    text_node.click(timeout=3000)
            chooser = fc_info.value
            chooser.set_files(str(file_path), timeout=3000)
            return True
        except Exception:
            # 有些 UI 不弹 file chooser，但会在 DOM 中动态插入 input[type=file]
            try:
                text_node = page.locator(sel).first
                if text_node.count() == 0:
                    continue
                clickable = text_node.locator(
                    "xpath=ancestor::*[contains(@class,'ms-ContextualMenu-link')][1]"
                )
                if clickable.count() > 0:
                    clickable.click(timeout=3000)
                else:
                    text_node.click(timeout=3000)
                page.wait_for_timeout(800)
                dynamic_input = page.locator('input[type="file"]')
                if dynamic_input.count() > 0:
                    dynamic_input.last.set_input_files(str(file_path), timeout=3000)
                    return True
            except Exception:
                pass

    return False


def _upload_one_file(page, file_path: Path) -> None:
    logger.info("准备上传文件: %s", file_path)
    _ensure_files_page(page)
    logger.info("已进入 OneDrive 页面: %s", page.url)

    uploaded = _try_upload_by_input(page, file_path)
    if uploaded:
        logger.info("通过 input[type=file] 触发上传。")
    if not uploaded:
        uploaded = _try_upload_by_button(page, file_path)
        if uploaded:
            logger.info("通过按钮/菜单触发上传。")
    if not uploaded:
        _save_debug_snapshot(page, "upload_control_not_found")
        raise RuntimeError(
            f"未找到文件上传控件，当前页面: {page.url}。"
            "已输出调试截图与HTML，请检查账号权限或页面结构。"
        )

    logger.info("已触发网页上传: %s", file_path.name)

    # 保守确认策略：只在页面中明确看到文件名时才视为上传成功。
    # 大文件给更长确认窗口，避免过早误判后删除本地文件。
    file_size = file_path.stat().st_size
    is_large_file = file_size >= 200 * 1024 * 1024
    upload_start_ts = time.time()
    deadline = upload_start_ts + (7200 if is_large_file else 1800)
    last_progress_log = 0.0
    last_seen_name_ts = 0.0
    last_recover_ts = 0.0
    file_name = file_path.name
    file_name_short = file_name[:32]

    def _name_visible() -> bool:
        found = False
        for sel in [
            f'[data-automationid="FieldRenderer-name"]:has-text("{file_name_short}")',
            f'[data-automation-key="name"]:has-text("{file_name_short}")',
        ]:
            if page.locator(sel).count() > 0:
                found = True
                break
        if not found:
            for role in ["link", "button", "row", "gridcell"]:
                try:
                    if page.get_by_role(role, name=re.compile(re.escape(file_name_short))).count() > 0:
                        found = True
                        break
                except Exception:
                    pass
        if not found:
            if page.get_by_text(file_name, exact=False).count() > 0 or page.get_by_text(file_name_short, exact=False).count() > 0:
                found = True
        return found

    def _is_uploading_ui() -> bool:
        if page.get_by_role("progressbar").count() > 0:
            return True
        for kw in ["正在上载", "正在上传", "上载中", "上传中", "Uploading"]:
            if page.get_by_text(kw).count() > 0:
                return True
        return False

    while time.time() < deadline:
        try:
            if _is_uploading_ui():
                now = time.time()
                if now - last_progress_log >= 20:
                    logger.info("上传传输中: %s (检测到进度条或上传提示，浏览器正在发包)", file_name)
                    last_progress_log = now
                page.wait_for_timeout(5000)
                continue

            if _name_visible():
                last_seen_name_ts = time.time()
                elapsed = int(time.time() - upload_start_ts)
                logger.info("检测到云端列表出现文件名: %s (已等待 %ss)", file_name, elapsed)

                # 大文件网络传输需要时间，即使 UI 上传提示消失，也再给一定缓冲
                if is_large_file and elapsed < 60:
                    logger.info("大文件上传保护：等待时长不足60秒，继续观察。")
                    page.wait_for_timeout(5000)
                    continue

                # 稳定确认：避免刚触发上传就 reload 导致列表瞬时丢失，改为多次采样确认。
                stable_seen = 0
                confirm_rounds = 5 if is_large_file else 4
                for i in range(confirm_rounds):
                    page.wait_for_timeout(2000)
                    if _is_uploading_ui():
                        break
                    if _name_visible():
                        stable_seen += 1
                        if stable_seen >= 2:
                            logger.info("上传确认通过（多次可见）: %s", file_name)
                            return
                    else:
                        stable_seen = 0

                    # 大文件低频刷新；普通文件仅在最后一轮兜底刷新一次。
                    should_reload = False
                    if is_large_file and i in (2, 4):
                        should_reload = True
                    if (not is_large_file) and i == confirm_rounds - 1:
                        should_reload = True
                    if should_reload:
                        try:
                            page.reload(wait_until="domcontentloaded")
                            page.wait_for_timeout(1200)
                        except Exception:
                            pass
        except Exception:
            pass

        now = time.time()
        if now - last_progress_log >= 20:
            logger.info(
                "上传确认中: %s（等待页面出现文件名，%s，url=%s）",
                file_name,
                "大文件模式" if is_large_file else "普通模式",
                page.url,
            )
            last_progress_log = now

        # 若之前见过文件名，但随后长期看不到，尝试重新回到文件页继续确认，避免卡在非目标页面。
        if (
            is_large_file
            and last_seen_name_ts > 0
            and (now - last_seen_name_ts) >= 120
            and (now - last_recover_ts) >= 60
        ):
            try:
                logger.info("长时间未再次匹配文件名，尝试重新定位文件页面后继续确认。")
                _ensure_files_page(page)
                page.wait_for_timeout(1500)
            except Exception as exc:
                logger.warning("重新定位文件页失败，继续等待: %s", exc)
            last_recover_ts = now

        page.wait_for_timeout(3000)
        # 大文件确认阶段降低刷新频率，避免干扰浏览器上传流程
        if is_large_file and int(now) % 60 < 3:
            try:
                page.reload(wait_until="domcontentloaded")
            except Exception:
                pass

    _save_debug_snapshot(page, "upload_confirm_timeout")
    raise RuntimeError(f"上传超时，未确认文件出现在云端列表: {file_name}")


def run() -> None:
    QUEUE_ROOT.mkdir(parents=True, exist_ok=True)
    Path(PROFILE_DIR).mkdir(parents=True, exist_ok=True)
    logger.info("启动 OneDrive 网页上传器，队列目录: %s", QUEUE_ROOT)

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=HEADLESS,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        last_auth_check_ts = 0.0

        while True:
            pending = _iter_pending_files()
            now = time.time()
            need_auth_check = (now - last_auth_check_ts) >= AUTH_CHECK_INTERVAL_SECONDS

            # 仅在定时周期到达时进行登录态检查，减少无效日志
            if need_auth_check:
                try:
                    _login_if_needed(page)
                    _ensure_files_page(page)
                    last_auth_check_ts = now
                except Exception as exc:
                    logger.exception("登录或页面初始化失败，稍后重试: %s", exc)
                    time.sleep(10)
                    continue

            if not pending:
                time.sleep(SCAN_INTERVAL_SECONDS)
                continue

            for file_path in pending:
                try:
                    _upload_one_file(page, file_path)
                    _notify_upload_success(file_path)
                    file_path.unlink(missing_ok=True)
                    _cleanup_meta(file_path)
                    logger.info("上传完成并删除本地文件: %s", file_path)
                except Exception as exc:
                    logger.exception("上传失败，稍后重试: %s", exc)
                    time.sleep(5)


if __name__ == "__main__":
    run()
