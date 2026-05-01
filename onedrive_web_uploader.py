import logging
import os
import re
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
ONEDRIVE_FILES_URL = os.getenv(
    "ONEDRIVE_FILES_URL", "https://g1479169422163-my.sharepoint.com/my"
).strip()
SCAN_INTERVAL_SECONDS = int(os.getenv("ONEDRIVE_SCAN_INTERVAL_SECONDS", "15"))
AUTH_CHECK_INTERVAL_SECONDS = int(os.getenv("ONEDRIVE_AUTH_CHECK_INTERVAL_SECONDS", "600"))
HEADLESS = os.getenv("ONEDRIVE_HEADLESS", "true").strip().lower() == "true"
DEBUG_DIR = Path(os.getenv("ONEDRIVE_DEBUG_DIR", "/data/debug")).resolve()

SUPPORTED_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def _iter_pending_files() -> list[Path]:
    if not QUEUE_ROOT.exists():
        QUEUE_ROOT.mkdir(parents=True, exist_ok=True)
        return []
    candidates = [p for p in QUEUE_ROOT.rglob("*") if p.is_file()]
    video_files = [p for p in candidates if p.suffix.lower() in SUPPORTED_SUFFIXES]
    return sorted(video_files, key=lambda p: p.stat().st_mtime)


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
            inputs.first.set_input_files(str(file_path))
            return True
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
                page.get_by_role("button", name=pat).first.click()
            chooser = fc_info.value
            chooser.set_files(str(file_path))
            return True
        except Exception:
            pass

        # 某些 UI 先点“新建”，再点“上传文件”
        try:
            new_btn = page.get_by_role("button", name=re.compile(r"new|新建", re.IGNORECASE))
            if new_btn.count() > 0:
                new_btn.first.click()
                page.wait_for_timeout(800)
        except Exception:
            pass

        try:
            with page.expect_file_chooser(timeout=3000) as fc_info:
                page.get_by_role("menuitem", name=pat).first.click()
            chooser = fc_info.value
            chooser.set_files(str(file_path))
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
                    clickable.click()
                else:
                    text_node.click()
            chooser = fc_info.value
            chooser.set_files(str(file_path))
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
                    clickable.click()
                else:
                    text_node.click()
                page.wait_for_timeout(800)
                dynamic_input = page.locator('input[type="file"]')
                if dynamic_input.count() > 0:
                    dynamic_input.last.set_input_files(str(file_path))
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

    # 轮询确认上传结果：文件名命中 / 成功提示 / 上传进度结束
    deadline = time.time() + 1200
    last_progress_log = 0.0
    seen_uploading = False
    no_progress_rounds = 0
    while time.time() < deadline:
        try:
            if page.get_by_text(file_path.name, exact=False).count() > 0:
                logger.info("检测到云端列表出现文件名: %s", file_path.name)
                return
        except Exception:
            pass

        # OneDrive 多语言成功提示（toast）检测
        success_patterns = [
            "已上传",
            "上传完成",
            "uploaded",
            "upload complete",
            "all done",
        ]
        for text in success_patterns:
            try:
                if page.get_by_text(text, exact=False).count() > 0:
                    logger.info("检测到上传成功提示: %s", text)
                    return
            except Exception:
                pass

        # 上传进行中状态检测
        uploading_now = False
        uploading_patterns = ["正在上传", "上传中", "uploading", "upload in progress"]
        for text in uploading_patterns:
            try:
                if page.get_by_text(text, exact=False).count() > 0:
                    uploading_now = True
                    break
            except Exception:
                pass
        try:
            if page.locator('[role="progressbar"]').count() > 0:
                uploading_now = True
        except Exception:
            pass

        if uploading_now:
            seen_uploading = True
            no_progress_rounds = 0
        else:
            if seen_uploading:
                no_progress_rounds += 1
                if no_progress_rounds >= 3:
                    logger.info("检测到上传进度结束，判定上传完成: %s", file_path.name)
                    return

        now = time.time()
        if now - last_progress_log >= 20:
            logger.info("上传确认中: %s（等待页面出现文件名）", file_path.name)
            last_progress_log = now
        page.wait_for_timeout(3000)

    _save_debug_snapshot(page, "upload_confirm_timeout")
    raise RuntimeError(f"上传超时，未确认成功: {file_path.name}")


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
                    file_path.unlink(missing_ok=True)
                    logger.info("上传完成并删除本地文件: %s", file_path)
                except Exception as exc:
                    logger.exception("上传失败，稍后重试: %s", exc)
                    time.sleep(5)


if __name__ == "__main__":
    run()
