# 🐮 小袁翻译 xiaoyuan-translator

选中文字 → 鼠标左下角弹出牛来 → 点牛来 → 文字上方悬浮翻译卡片；另有词典式主窗口可自主互译。

28 种语言互译，默认自动检测 → 中文，开箱即用，无需 API Key。

![Windows](https://img.shields.io/badge/Windows-10%2F11-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-green)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ 功能

- **选中即现**：拖动/双击选中文字后，鼠标左下角淡入牛来头像（56px，无黑边），4 秒无操作自动消失
- **点击即译**：点牛来后在选中文字正上方弹出翻译卡片（自动避开屏幕边缘）
- **28 种语言**：自动检测 / 中 / 英 / 日 / 韩 / 法 / 德 / 西 / 俄 / 维吾尔 / 藏 / 哈萨克…，下拉可任意互换，`⇄` 一键反向
- **词典卡片**：音标（美/英）+ 简明释义 + 双语例句（有道免费词典，无 Key，失败自动降级为纯翻译）
- **双喇叭朗读**：`🔊 原文` / `🔊 译文`，本地 SAPI → 在线免费语音 → 装包指引三级兜底；关窗即停读
- **不劫持剪贴板**：取词后 85ms 内恢复你原来的复制内容，`复制A→选中B→粘贴` 可直接替换
- **主窗口**：托盘右键 → 打开主窗口（词典式：输入 + 音标 + 简明/例句 + 历史 30 条，`Ctrl+Enter` 翻译）
- **拟物毛玻璃风**：弹窗 + 主窗口统一浅色磨砂配色
- **高分屏适配**：`SetProcessDpiAwareness`，多显示器兼容

## 🚀 快速开始

### 1. 安装依赖

```powershell
pip install -r requirements.txt
```

### 2. 运行

```powershell
python main.py
# 直接打开主窗口：
python main.py --main
# 或双击 启动.bat
```

看到右上角 `🐮 小袁翻译已启动` 即成功。去浏览器 / Word / 微信里选中一段文字试试。

### 3. 打包为 exe（可选）

```powershell
pip install pyinstaller
pyinstaller --noconsole --onefile --name "小袁翻译" --icon "niulai.ico" --add-data "niulai.png;." main.py --hidden-import="pynput.keyboard._win32" --hidden-import="pynput.mouse._win32" --hidden-import="win32com.client" --hidden-import="pystray._win32" --hidden-import="PIL.ImageTk" --hidden-import="PIL.PngImagePlugin" --hidden-import="PIL.JpegImagePlugin" --exclude-module="numpy" --exclude-module="matplotlib" --exclude-module="scipy" --exclude-module="pandas" --exclude-module="sklearn" --exclude-module="IPython" --exclude-module="notebook"
```

> 需要 UPX 可再加 `--upx-dir`，本仓库 Release 的 21MB 版即此参数打出。exe 走 GitHub Release 分发，不进 git。

## 🎮 使用技巧

| 操作 | 效果 |
|---|---|
| 拖动/双击选中文字 | 左下角出牛来 |
| 点击牛来 | 上方出翻译卡片 |
| 卡片下拉 `从→到` | 任意语言互译 |
| `⇄` | 源/目标互换 |
| `📋 复制译文` | 复制到剪贴板 |
| `🔊 原文` / `🔊 译文` | 分别朗读 |
| `🔁 重试`（失败时出现） | 重新翻译 |
| `ESC` / 点空白 / 滚轮 | 关闭卡片 |
| 托盘右键 → 打开主窗口 | 词典式自主互译 |
| 主窗口 `Ctrl+Enter` | 翻译输入框内容 |

## 🔧 原理

```text
pynput.mouse.Listener 监听拖选/双击 → 模拟 Ctrl+C 取词 → 剪贴板 85ms 内恢复
    ↓
StarWindow (Toplevel, overrideredirect, transparentcolor + PIL 硬边缘抠图) 淡入
    ↓ 点击
TranslatePopup 异步翻译：
  翻译链路：clients5 dict-chrome-ex → google gtx → MyMemory（一节 0.3s 防 429，长文本分段 + 缓存）
  词典链路：dict.youdao.com/jsonapi（音标/简明/例句）
朗读链路：本地 SAPI（异步+COM 泵）→ 在线免费 TTS → 装包指引；Speaker 常驻线程 + 队列，stop 即 purge
```

## ❓ 常见问题

- **选中没反应？** 管理员权限运行的软件会拦截模拟按键，请同样以管理员身份运行；浏览器里请确保真正选中（蓝底）而非单击。
- **翻译失败？** 点卡片左下 `🔁 重试`；三链路都失败多为网络问题。
- **朗读没声？** 按喇叭后的指引装对应语言包即可；日语等无包语言联网会自动用在线语音。
- **牛来位置偏移？** `StarWindow.show()` 里微调 `px/py`。
- **自定义头像？** 把正方形图改名 `niulai.png` 放 exe 同级目录覆盖即可。

## 📁 目录

```text
.
├── main.py            # 单文件即全部功能
├── requirements.txt
├── README.md
├── LICENSE            # MIT
├── niulai.png         # 牛来头像（原图版权归原作者，矢量兜底见代码）
├── niulai.ico         # exe 图标
├── 启动.bat           # 双击启动
└── 使用说明.txt       # 中文使用说明
```

## ⚠️ 版权说明

`niulai.png` 为作者自备头像，版权归原作者所有，仅随本仓库分发用于演示；若你是版权方且不希望收录，请提 Issue，24 小时内替换为代码内置矢量牛头。

---

MIT 开源，随意魔改。提 Issue 请带 Windows 版本 + Python 版本 + 复现步骤。
