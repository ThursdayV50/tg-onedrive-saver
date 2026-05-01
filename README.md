# Telegram 大视频自动上传 OneDrive（自动清理本地）

这个方案使用：
- 自建 `telegram-bot-api`（支持大文件）
- `abraunegg/onedrive` 容器负责同步上传
- 上传成功后自动删除本地源文件（防止磁盘涨满）

## 1. 一次性部署

```bash
git clone https://github.com/ThursdayV50/tg-onedrive-saver.git
cd tg-onedrive-saver
cp .env.example .env
mkdir -p data/onedrive-conf data/onedrive-sync data/tg-bot-api
```

## 2. 填写 `.env`

至少填写：

```env
TELEGRAM_BOT_TOKEN=你的BotFather机器人token
TELEGRAM_API_ID=你的telegram_api_id
TELEGRAM_API_HASH=你的telegram_api_hash
ONEDRIVE_UID=1000
ONEDRIVE_GID=1000
```

## 3. 首次授权 OneDrive（必须）

```bash
docker compose run --rm onedrive
```

看到登录链接后：
1. 浏览器打开链接并登录微软账号
2. 授权后会跳转空白页
3. 把浏览器地址栏完整 URL 粘贴回终端

完成后按 `Ctrl+C` 退出一次性容器。

## 4. 启动服务

```bash
docker compose up -d --build
docker compose logs -f
```

## 5. 使用方式

1. Telegram 打开机器人发送 `/start`
2. 发送视频（或视频文件）
3. 机器人提示“已加入同步队列”
4. `onedrive` 容器上传成功后自动删除本地源文件

## 6. 常用命令

```bash
docker compose logs -f tg-onedrive-bot
docker compose logs -f onedrive-sync
docker compose restart
docker compose down
```

## 7. 关键说明

- 默认会保留云端文件并清理本地源文件
- 若手动删除 `./data/onedrive-sync` 中尚未上传完成的文件，会导致该文件不再上传
- 机器人接收路径在 `./data/onedrive-sync/TelegramVideos`
