# Telegram 视频自动保存到 OneDrive（rclone 方案）

把视频发给 Telegram 机器人后，机器人会先下载到本地临时文件，再通过 `rclone` 上传到 OneDrive。

## 功能

- 支持 Telegram `video` 和 `document(video/*)` 两种视频消息
- 使用 `rclone copyto` 上传到 OneDrive 指定目录
- 上传成功后尝试返回 OneDrive 分享链接（失败时返回远端路径）
- Docker Compose 一键部署，适合 VPS 常驻运行

## 项目结构

- `main.py`：机器人主逻辑（接收视频、调用 rclone 上传）
- `requirements.txt`：Python 依赖
- `Dockerfile`：镜像构建（内置 rclone）
- `docker-compose.yml`：容器编排
- `.env.example`：环境变量模板

## 1. 前置准备

### 1.1 创建 Telegram Bot

1. 在 Telegram 搜索 `@BotFather`
2. 执行 `/newbot` 创建机器人
3. 记录 `Bot Token`（用于 `TELEGRAM_BOT_TOKEN`）

### 1.2 准备 OneDrive（rclone 授权）

使用 `rclone config` 创建一个 OneDrive 远端（例如命名为 `onedrive`），并将配置文件保存为 `./data/rclone.conf`。

> 你可以在本机完成后把 `rclone.conf` 拷贝到服务器，也可以按下文在容器内完成授权。

## 2. VPS 部署（Docker Compose）

### 2.1 克隆并进入项目

```bash
git clone git@github.com:ThursdayV50/tg-onedrive-saver.git
cd <仓库目录>
```

### 2.2 准备配置文件

```bash
cp .env.example .env
mkdir -p data
```

编辑 `.env`，至少填这两个变量：

- `TELEGRAM_BOT_TOKEN=...`
- `RCLONE_REMOTE=onedrive`

可选变量：

- `ONEDRIVE_TARGET_DIR=TelegramVideos`
- `ALLOWED_CHAT_ID=123456789`

### 2.3 首次生成 rclone 配置（如果你还没有 `./data/rclone.conf`）

```bash
docker compose run --rm tg-onedrive-bot rclone --config /data/rclone.conf config
```

按向导完成 OneDrive 授权后，确认宿主机存在 `./data/rclone.conf`。

### 2.4 启动服务

```bash
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f
```

## 3. 使用方式

1. 在 Telegram 打开你的机器人并发送 `/start`
2. 发送视频（或作为文件发送视频）
3. 机器人会回复上传结果（分享链接或远端路径）

文件默认保存到 OneDrive 的 `TelegramVideos` 目录（可通过 `ONEDRIVE_TARGET_DIR` 修改）。

## 4. 常用运维命令

查看日志：

```bash
docker compose logs -f
```

重启服务：

```bash
docker compose restart
```

更新代码后重建：

```bash
docker compose up -d --build
```

停止服务：

```bash
docker compose down
```

## 5. 持久化说明

- rclone 配置保存在宿主机 `./data/rclone.conf`
- 容器重启不会丢失 OneDrive 授权状态
- 删除 `./data/rclone.conf` 后需重新执行 `rclone config`

## 6. 常见问题

### Q1: 机器人提示找不到 rclone 配置怎么办？

- 确认宿主机存在 `./data/rclone.conf`
- 确认 `docker-compose.yml` 已挂载 `./data:/data`
- 确认环境变量 `RCLONE_CONFIG_FILE` 指向 `/data/rclone.conf`

### Q2: 上传成功但没有分享链接？

- 这是正常情况，取决于 OneDrive 与 rclone `link` 能否为该文件生成公开链接
- 机器人会回退显示远端路径，你仍可在 OneDrive 中找到该文件

### Q3: 想限制只有自己可用？

设置 `.env`：

```env
ALLOWED_CHAT_ID=你的Telegram聊天ID
```

## 7. 安全建议

- 不要把 `.env` 提交到 Git 仓库
- 不要把 `./data/rclone.conf` 提交到 Git 仓库
- 定期轮换 `TELEGRAM_BOT_TOKEN`
