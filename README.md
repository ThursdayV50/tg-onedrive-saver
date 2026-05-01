# Telegram 大视频自动上传 OneDrive（无需 rclone）

这个版本使用：
- 自建 `telegram-bot-api`（local mode）下载大视频
- Microsoft Graph API 上传到 OneDrive（网页端可直接查看）

## 1. 一次性部署

```bash
git clone https://github.com/ThursdayV50/tg-onedrive-saver.git
cd tg-onedrive-saver
cp .env.example .env
mkdir -p data
```

## 2. 填写 `.env`

至少填写这 4 项：

```env
TELEGRAM_BOT_TOKEN=你的BotFather机器人token
TELEGRAM_API_ID=你的telegram_api_id
TELEGRAM_API_HASH=你的telegram_api_hash
MS_CLIENT_ID=你的微软应用client_id
```

说明：
- `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` 在 [my.telegram.org](https://my.telegram.org) 创建应用获取
- `MS_CLIENT_ID` 在 Azure / Entra 应用注册中获取

## 3. 启动

```bash
docker compose up -d --build
docker compose logs -f
```

首次启动会在日志中提示：
- 打开 `https://microsoft.com/devicelogin`
- 输入设备码完成授权

授权成功后，机器人会自动继续运行。

## 4. 使用

1. 在 Telegram 打开机器人，发送 `/start`
2. 发送视频（或视频文件）
3. 机器人回复 OneDrive 网页链接或保存路径

## 5. 常用命令

```bash
docker compose logs -f
docker compose restart
docker compose down
docker compose up -d --build
```

## 6. 常见问题

### 报 `Invalid token`

- 去 `@BotFather` 重置 token
- 更新 `.env` 的 `TELEGRAM_BOT_TOKEN`
- 重启：`docker compose up -d --build`

### 上传失败提示微软授权错误

- 查看日志是否出现设备码
- 重新完成一次设备码登录

### 文件在 OneDrive 网页看不到

- 检查 `ONEDRIVE_TARGET_DIR` 配置
- 默认在 `TelegramVideos` 目录
