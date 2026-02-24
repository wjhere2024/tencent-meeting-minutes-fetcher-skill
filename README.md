# Tencent Meeting Minutes Fetcher Skill

从腾讯会议录制分享链接中提取转写/纪要文本，导出为结构化 `JSON` 与可读 `TXT`。

## 中文说明

### 仓库内容

- `SKILL.md`：Skill 元信息与调用流程。
- `scripts/fetch_minutes.py`：核心抓取脚本。
- `references/api-notes.md`：接口链路说明与排查笔记。

### 功能特性

- 支持以下链接格式：
  - `https://meeting.tencent.com/crm/<code>`
  - `https://meeting.tencent.com/cw/<code>`
  - `https://meeting.tencent.com/meeting-record/shares?id=<uuid>`
- 自动解析 `share_id`、`meeting_id`、`recording_id`。
- 支持全量分页抓取与去重，避免只抓到前半段。
- 导出结果：
  - `<prefix>.json`：完整结构数据
  - `<prefix>.txt`：时间戳 + 发言人 + 文本

### 快速开始

#### 环境要求

- Python 3.9+
- `requests`

安装依赖：

```bash
pip install requests
```

执行示例：

```bash
python scripts/fetch_minutes.py \
  --url "https://meeting.tencent.com/crm/EXAMPLE1234" \
  --password "DEMO_PASS" \
  --outdir "./output" \
  --prefix "minutes"
```

### 输出文件

- `output/minutes.json`
- `output/minutes.txt`

### 示例输出（`minutes.txt`）

```text
Title: 示例会议（虚拟数据）
Meeting ID: 12345678901234567890
Recording ID: 2099000000000000000

[00:00:00 - 00:00:11] Speaker_A
大家好，我们开始今天的演示会议。

[00:00:16 - 00:00:20] Speaker_B
收到，录制已开启，可以继续。
```

### 参数说明

- `--url`（必填）：腾讯会议录制分享链接。
- `--password`（必填）：访问密码。
- `--outdir`（可选）：输出目录，默认 `output`。
- `--lang`（可选）：语言，默认 `zh`。
- `--limit`（可选）：单次请求分页大小，默认 `50`。
- `--prefix`（可选）：输出文件前缀，默认 `minutes`。

### 合规与注意事项

- 本项目基于录制分享页背后的 Web 接口实现，接口行为可能变动。
- 仅用于抓取你有权限访问的会议数据。
- 请勿将私密会议链接、密码、敏感内容提交到公开仓库。

## English Summary

Extract Tencent Meeting shared-recording transcript/minutes from share URL + password, and export to JSON/TXT.

- Supports `crm/cw/shares?id=` links.
- Resolves share context automatically.
- Fetches full pages with deduplication.
- Outputs `minutes.json` and `minutes.txt`.

## Repository Structure

```text
.
├─ SKILL.md
├─ scripts/
│  └─ fetch_minutes.py
└─ references/
   └─ api-notes.md
```

## 版本发布

- `v0.1.0`：首个公开版本，包含：
  - 完整分页抓取与去重
  - `crm/cw/shares?id=` 三种链接解析
  - 中英双语 README
