# Telegram 视频自动保存到 OneDrive（Docker / VPS）

把视频发给 Telegram 机器人后，机器人会自动下载并上传到你的 OneDrive。

## 功能

- 支持 Telegram `video` 和 `document(video/*)` 两种视频消息
- 自动上传到 OneDrive 指定目录
- 大文件自动分片上传（OneDrive Upload Session）
- 首次运行设备码登录，后续复用令牌缓存
- Docker Compose 一键部署，适合 VPS 常驻运行

## 项目结构

- `main.py`：机器人主逻辑（接收视频、上传 OneDrive）
- `requirements.txt`：Python 依赖
- `Dockerfile`：镜像构建
- `docker-compose.yml`：容器编排
- `.env.example`：环境变量模板

## 1. 前置准备

### 1.1 创建 Telegram Bot

1. 在 Telegram 搜索 `@BotFather`
2. 执行 `/newbot` 创建机器人
3. 记录 `Bot Token`（用于 `TELEGRAM_BOT_TOKEN`）

### 1.2 创建 Microsoft 应用（OneDrive 授权）

1. 打开 [Azure Portal](https://portal.azure.com/)
2. 进入 `Microsoft Entra ID` -> `应用注册` -> `新注册`
3. 应用类型建议选择支持个人账号（Microsoft 个人账户）
4. 创建后复制 `Application (client) ID`（用于 `MS_CLIENT_ID`）
5. 进入 `Authentication`
6. 启用 `Allow public client flows`（必须开启，设备码登录需要）
7. 进入 `API permissions`，添加 Microsoft Graph 委托权限：
8. `Files.ReadWrite.All`
9. `offline_access`
10. `User.Read`
11. 点击同意权限（若租户策略要求管理员同意，请先完成）

## 2. VPS 部署（Docker Compose）

### 2.1 克隆并进入项目

```bash
git clone <你的仓库地址>
cd <仓库目录>
```

### 2.2 准备配置文件

```bash
cp .env.example .env
mkdir -p data
```

编辑 `.env`，至少填这两个变量：

- `TELEGRAM_BOT_TOKEN=...`
- `MS_CLIENT_ID=...`

可选变量：

- `ONEDRIVE_TARGET_DIR=TelegramVideos`
- `ALLOWED_CHAT_ID=123456789`

### 2.3 启动服务

```bash
docker compose up -d --build
```

### 2.4 首次授权（必须）

查看日志：

```bash
docker compose logs -f
```

首次会看到类似提示：

- `请在浏览器打开: https://microsoft.com/devicelogin`
- `输入设备码: XXXXXXXX`

在任意设备浏览器完成登录后，容器会自动继续运行。

## 3. 使用方式

1. 在 Telegram 打开你的机器人并发送 `/start`
2. 发送视频（或作为文件发送视频）
3. 机器人会回复上传结果和 OneDrive 链接

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

- OneDrive 登录缓存保存在宿主机 `./data/msal_token_cache.bin`
- 容器重启不会丢失登录状态
- 删除 `./data/msal_token_cache.bin` 后会在下次启动重新要求设备码登录

## 6. 常见问题

### Q1: 为什么不建议跑在 GitHub Actions？

- Actions 适合 CI，不适合常驻机器人
- 存在任务时长限制，不能稳定 24/7 在线
- 临时环境导致令牌缓存难持久化
- 视频链路是双公网传输，速度和稳定性通常不如 VPS 常驻容器

### Q2: 上传失败提示权限不足怎么办？

- 检查 Azure 应用是否添加并生效以下权限：
- `Files.ReadWrite.All`
- `offline_access`
- `User.Read`
- 删除 `./data/msal_token_cache.bin` 后重启，重新授权一次

### Q3: 想限制只有自己可用？

设置 `.env`：

```env
ALLOWED_CHAT_ID=你的Telegram聊天ID
```

## 7. 安全建议

- 不要把 `.env` 提交到 Git 仓库
- 定期轮换 `TELEGRAM_BOT_TOKEN`
- 仅授予必要权限，生产中建议单独 Microsoft 账号用于机器人
