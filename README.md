# Wechat-Message

**Wechat-Message** 是一个微信机器人，专注于保存微信聊天记录，无自动回复功能。适用于需要存储单聊和群聊消息的场景。

## 特性
- **单聊记录**：保存一对一聊天消息。
- **群聊记录**：保存群聊消息，包括发送者和群信息。
- **简单易用**：安装依赖后，即可运行。

## 安装步骤

确保你已经安装了 Python 3.x 环境，并按照以下步骤操作：

1. 克隆项目
   ```bash
   git clone https://github.com/your-repo/wechat-message.git
   cd wechat-message
   ```

2. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```

## 运行项目

在项目目录下运行以下命令启动项目：

```bash
python app.py
```

## 数据结构

**单聊消息**：
- `is_group`: `false`
- `from_user_id`: 发送者 ID（必填）
- `from_user_nickname`: 发送者昵称
- `to_user_id`: 接收者 ID（必填）
- `to_user_nickname`: 接收者昵称

**群聊消息**：
- `is_group`: `true`
- `actual_user_id`: 发送者 ID
- `actual_user_name`: 发送者昵称
- `other_user_id`: 群 ID
- `other_user_nickname`: 群昵称

## 项目参考

本项目参考了 [chatgpt-on-wechat](https://github.com/zhayujie/chatgpt-on-wechat.git)，感谢其开源贡献。