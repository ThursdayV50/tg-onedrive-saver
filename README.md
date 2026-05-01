# Telegram 大视频自动上传 OneDrive（网页版自动化）

这个版本使用：
- 自建 `telegram-bot-api`（支持大文件下载）
- Playwright 自动登录 OneDrive 网页并上传
- 上传成功后自动删除本地队列文件

## 1. 一次性部署

```bash
git clone https://github.com/ThursdayV50/tg-onedrive-saver.git
cd tg-onedrive-saver
cp .env.example .env
mkdir -p data/queue data/browser-profile data/tg-bot-api
```

## 2. 填写 `.env`

至少填写：

```env
TELEGRAM_BOT_TOKEN=你的BotFather机器人token
TELEGRAM_API_ID=你的telegram_api_id
TELEGRAM_API_HASH=你的telegram_api_hash
ONEDRIVE_LOGIN_EMAIL=你的微软邮箱
ONEDRIVE_LOGIN_PASSWORD=你的微软密码
```

## 3. 启动服务

```bash
docker compose up -d --build
docker compose logs -f
```

## 4. 使用方式

1. 在 Telegram 打开机器人并发送 `/start`
2. 发送视频（或视频文件）
3. 机器人提示“已加入网页上传队列”
4. `onedrive-web-uploader` 上传成功后会自动删本地队列文件

## 5. 查看状态

```bash
docker compose logs -f tg-onedrive-bot
docker compose logs -f onedrive-web-uploader
```

## 6. 关键说明

- 上传队列目录：`./data/queue/TelegramVideos`
- 浏览器登录态目录：`./data/browser-profile`
- 如果企业策略要求二次验证，自动化可能失败，请查看 `onedrive-web-uploader` 日志
- 为避免本地盘占满，上传成功后会删除本地源文件

## 7. 常见问题

### 网页上传失败

- 检查账号密码是否正确
- 检查是否触发 MFA / 验证码
- 查看日志是否出现“未找到文件上传控件”

### 机器人提示 File is too big

- 确认 `telegram-bot-api` 容器已启动
- 确认 `docker-compose.yml` 里 `telegram-bot-api` 包含 `--local`
