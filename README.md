# Telegram 视频自动上传 OneDrive（极简部署）

给机器人发视频后，程序会自动下载并上传到 OneDrive（基于 `rclone`）。

## 1. 一次性部署（复制即用）

```bash
git clone git@github.com:ThursdayV50/tg-onedrive-saver.git
cd tg-onedrive-saver
cp .env.example .env
mkdir -p data
```

编辑 `.env`，至少改这两项：

```env
TELEGRAM_BOT_TOKEN=你的_bot_token
RCLONE_REMOTE=onedrive
```

首次授权 OneDrive（按向导操作）：

```bash
docker compose run --rm tg-onedrive-bot rclone --config /data/rclone.conf config
```

启动：

```bash
docker compose up -d --build
docker compose logs -f
```

## 2. 怎么用

1. 在 Telegram 找到你的机器人，发送 `/start`
2. 发送视频（或以文件形式发送视频）
3. 收到“上传成功”消息即完成

默认上传目录是 OneDrive 的 `TelegramVideos`（可在 `.env` 改 `ONEDRIVE_TARGET_DIR`）。

## 3. 常用命令

```bash
docker compose logs -f
docker compose restart
docker compose down
docker compose up -d --build
```

## 4. 最常见问题

### 找不到 rclone 配置

- 确认有文件：`./data/rclone.conf`
- 没有就重新执行授权命令：

```bash
docker compose run --rm tg-onedrive-bot rclone --config /data/rclone.conf config
```

### 想只允许自己使用机器人

在 `.env` 增加：

```env
ALLOWED_CHAT_ID=你的Telegram聊天ID
```
