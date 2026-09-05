#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小袁翻译 - 牛来版 Floating Translator
选中文字 -> 鼠标左下角弹出牛来头像 -> 点击牛来 -> 文字上方悬浮翻译卡片
支持 中英互译 自动识别 | 双喇叭朗读原文/译文

运行: pip install -r requirements.txt ; python main.py
打包: pyinstaller --noconsole --onefile --icon=niulai.ico --add-data "niulai.png;." main.py
"""

import re
import time
import threading
import ctypes
import tkinter as tk
from tkinter import font as tkfont

# DPI 感知，解决高分屏坐标偏移
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass

try:
    import requests
except ImportError:
    requests = None

try:
    from pynput import mouse as pynput_mouse, keyboard as pynput_keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

# ---------- 工具函数 ----------

def is_chinese(text: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def _log(*args):
    # 线程/打包exe(noconsole)下 print 可能抛异常，用这个包一层
    try:
        print(*args, flush=True)
    except:
        pass

def _silent_proc_kwargs():
    # 起 powershell 不弹黑窗口（CREATE_NO_WINDOW + 隐藏）
    try:
        import subprocess
        import os as _os
        if _os.name == "nt":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return {"creationflags": subprocess.CREATE_NO_WINDOW, "startupinfo": si}
    except:
        pass
    return {}

def detect_tts_lang(text: str) -> str:
    """朗读用语言检测：假名优先判日语，避免日语汉字被误判成中文拿 Huihui 去读"""
    if not text:
        return "en"
    if re.search(r'[\u3040-\u309f\u30a0-\u30ff\uff61-\uff9f]', text):
        return "ja"  # 平假名/片假名/半角假名
    if re.search(r'[\uac00-\ud7af\u1100-\u11ff]', text):
        return "ko"
    if re.search(r'[\u1800-\u18af]', text):
        return "mn"  # 传统蒙古文
    if re.search(r'[\u0400-\u04ff]', text):
        # 哈萨克特有：ӘҒҚҢӨҰҮҺ；乌克兰特有：ЄєҐґ（Іі 两边都有，放后）
        if re.search(r'[\u04d8\u04d9\u0492\u0493\u049a\u049b\u04a2\u04a3\u04e8\u04e9\u04b0\u04b1\u04ae\u04af\u04ba\u04bb]', text):
            return "kk"
        if re.search(r'[\u0404\u0454\u0490\u0491]', text):
            return "uk"
        return "ru"
    if re.search(r'[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff]', text):
        # 维吾尔特有字符优先，和翻译 guess_lang 保持一致
        if re.search(r'[\u0626\u0649\u06c6\u06c7\u06cb\u06d0]', text):
            return "ug"
        return "ar"
    if re.search(r'[\u0e00-\u0e7f]', text):
        return "th"
    if re.search(r'[\u0900-\u097f]', text):
        return "hi"
    if re.search(r'[\u0f00-\u0fff]', text):
        return "bo"
    if re.search(r'[\u4e00-\u9fff]', text):
        return "zh"
    return "en"

# 朗读嗓音匹配表：名称关键字 / SAPI Language ID / 系统语音 Culture 前缀
TTS_VOICE_TABLE = {
    "zh": {"names": ("Huihui", "Yaoyao", "Kangkang", "Xiaoxiao", "Yunjian", "Chinese"), "langs": ("804", "2052", "3076", "5124", "4100"), "culture": "zh", "label": "中文"},
    "ja": {"names": ("Haruka", "Ayumi", "Ichiro", "Naoki", "Keita", "Nanami", "Japanese", "日本語"), "langs": ("411",), "culture": "ja", "label": "日语"},
    "ko": {"names": ("Heami", "Seoyeon", "SunHi", "Korean", "한국어"), "langs": ("412",), "culture": "ko", "label": "韩语"},
    "en": {"names": ("Zira", "David", "Hazel", "Mark", "Susan", "George", "English"), "langs": ("409", "809", "C09", "1009", "1809"), "culture": "en", "label": "英语"},
    "fr": {"names": ("Hortense", "Julie", "Paul", "French", "Français"), "langs": ("40C",), "culture": "fr", "label": "法语"},
    "de": {"names": ("Katja", "Conrad", "Stefan", "German", "Deutsch"), "langs": ("407",), "culture": "de", "label": "德语"},
    "es": {"names": ("Helena", "Sabina", "Pablo", "Spanish", "Español"), "langs": ("40A", "C0A"), "culture": "es", "label": "西班牙语"},
    "ru": {"names": ("Irina", "Pavel", "Russian", "Русский"), "langs": ("419",), "culture": "ru", "label": "俄语"},
    "it": {"names": ("Elsa", "Cosimo", "Italian", "Italiano"), "langs": ("410",), "culture": "it", "label": "意大利语"},
    "pt": {"names": ("Maria", "Daniel", "Portuguese", "Português"), "langs": ("416", "816"), "culture": "pt", "label": "葡萄牙语"},
    "ar": {"names": ("Naayf", "Sayed", "Laila", "Arabic"), "langs": ("401",), "culture": "ar", "label": "阿拉伯语"},
    "th": {"names": ("Pattara", "Thai"), "langs": ("41E",), "culture": "th", "label": "泰语"},
    "hi": {"names": ("Kalpana", "Hemant", "Madhur", "Hindi"), "langs": ("439",), "culture": "hi", "label": "印地语"},
    "ur": {"names": ("Asad", "Urdu"), "langs": ("420",), "culture": "ur", "label": "乌尔都语"},
    "fa": {"names": ("Dalia", "Persian", "Farsi"), "langs": ("429",), "culture": "fa", "label": "波斯语"},
    "uk": {"names": ("Oleksandr", "Ukrainian"), "langs": ("422",), "culture": "uk", "label": "乌克兰语"},
    "kk": {"names": ("Kazakh",), "langs": ("43F",), "culture": "kk", "label": "哈萨克语"},
    "mn": {"names": ("Mongolian",), "langs": ("450",), "culture": "mn", "label": "蒙古语"},
    "bo": {"names": ("Tibetan",), "langs": ("451",), "culture": "bo", "label": "藏语"},
    "ug": {"names": ("Uyghur",), "langs": (), "culture": "ug", "label": "维吾尔语"},
}
# 在线免费 TTS（Google translate_tts）不支持的语言：直接走安装指引，不浪费请求
ONLINE_TTS_SKIP = ("ug", "bo", "mn")
# 在线 TTS 的 tl 参数映射
ONLINE_TTS_TL = {"zh": "zh-CN", "en": "en", "ja": "ja", "ko": "ko", "fr": "fr",
                 "de": "de", "es": "es", "ru": "ru", "it": "it", "pt": "pt",
                 "ar": "ar", "th": "th", "hi": "hi", "ur": "ur", "fa": "fa",
                 "uk": "uk", "kk": "kk"}

def pick_sapi_voice(speaker, tts_lang):
    """按语言挑 SAPI 嗓音，返回 voice 或 None（供朗读线程调用）"""
    try:
        table = TTS_VOICE_TABLE.get(tts_lang, TTS_VOICE_TABLE["en"])
        voices = speaker.GetVoices()
        items = []
        for i in range(voices.Count):
            try:
                items.append(voices.Item(i))
            except:
                continue
        for v in items:  # 名称关键字优先
            try:
                desc = v.GetDescription()
            except:
                continue
            for kw in table["names"]:
                if kw.lower() in desc.lower():
                    return v
        for v in items:  # Language ID 兜底
            try:
                lang = str(v.GetAttribute("Language")).upper()
            except:
                lang = ""
            if lang and lang in [x.upper() for x in table["langs"]]:
                return v
    except:
        pass
    return None

def get_cursor_pos():
    """获取鼠标坐标，兼容多显示器"""
    try:
        pt = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y
    except:
        return 0, 0

def get_clipboard_text(root: tk.Tk):
    """多方案取剪贴板，支持文本/文件，带重试避免剪贴板被占用"""
    # 方案1: win32clipboard 多格式（重试3次）
    for attempt in range(3):
        try:
            import win32clipboard
            # 尝试打开，失败则短暂等待重试
            try:
                win32clipboard.OpenClipboard()
            except:
                time.sleep(0.02)
                continue
            try:
                # 优先 UNICODETEXT
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                        data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                        if data:
                            return data
                except:
                    pass
                # CF_TEXT 兼容
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_TEXT):
                        data = win32clipboard.GetClipboardData(win32clipboard.CF_TEXT)
                        if data:
                            return data.decode('gbk', errors='ignore') if isinstance(data, bytes) else str(data)
                except:
                    pass
                # 文件列表 CF_HDROP (选中文件时)
                try:
                    import win32con
                    if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                        files = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                        if files:
                            import os
                            names = [os.path.basename(f) for f in files]
                            return " ".join(names)
                except:
                    pass
            finally:
                try:
                    win32clipboard.CloseClipboard()
                except:
                    pass
            # 如果到这里未返回，跳出重试
            break
        except:
            time.sleep(0.02)
            continue
    # 方案2: tkinter
    try:
        return root.clipboard_get()
    except:
        return ""

# ---------- UIA 无副作用取词（有道同原理：不碰剪贴板、不模拟按键） ----------
# CAD 画布等图形区没有文本选区，自然返回 None，所以任何软件都不会被打扰，
# 也不需要维护黑名单。极少数不支持无障碍的老控件取不到，可用主窗口手动粘贴。

_uia_local = threading.local()


def _uia_desktop_obj():
    # Desktop 按线程缓存：COM 对象必须在创建线程使用
    d = getattr(_uia_local, "desk", None)
    if d is None:
        try:
            from pywinauto import Desktop
            d = Desktop(backend="uia")
            _uia_local.desk = d
        except:
            return None
    return d


def _uia_selection_text(el):
    """单个 UIA 节点的选中文本；无选区/无模式返回 None"""
    try:
        iface = el.iface_text
    except Exception:
        return None
    try:
        sel = iface.GetSelection()
    except Exception:
        return None
    try:
        if sel.Length < 1:
            return None
    except Exception:
        return None
    try:
        txt = sel.GetElement(0).GetText(-1)
    except Exception:
        return None
    if not txt:
        return None
    return str(txt)


def uia_get_selection(x, y, max_chars=1800):
    """用 UI Automation 读坐标处的选中文本；不碰剪贴板、不模拟按键。
    从落点元素向上找 6 层祖先：链接词等碎片节点常无文本模式，
    选区挂在段落/文档节点上。CAD 画布等图形区没有文本选区，
    自然返回 None（有道们不捣乱的原理）。
    极少数不支持无障碍的老控件会返回 None，可用主窗口手动粘贴翻译。"""
    try:  # 工作线程需自带 COM 初始化，否则取不到任何东西
        import pythoncom
        try:
            pythoncom.CoInitialize()
        except:
            pass
    except:
        pass
    try:
        desk = _uia_desktop_obj()
        if desk is None:
            return None
        try:
            el = desk.from_point(int(x), int(y))
        except Exception:
            return None
        seen = set()
        for _ in range(7):  # 自身 + 6 层祖先
            if el is None:
                break
            try:
                txt = _uia_selection_text(el)
            except:
                txt = None
            if txt:
                txt = txt.strip()
                if txt:
                    return txt[:max_chars] if len(txt) > max_chars else txt
            try:
                nxt = el.parent()
            except:
                break
            if nxt is None:
                break
            try:
                pid = id(nxt.element_info.element)
            except:
                pid = None
            if pid is not None:
                if pid in seen:
                    break
                seen.add(pid)
            el = nxt
    except:
        pass
    return None

def set_clipboard_text(root: tk.Tk, text: str):
    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
    except:
        pass
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
    except:
        pass

# ---------- 语言配置 ----------
LANGUAGES = [
    ("auto", "自动检测"),
    ("zh", "中文"),
    ("en", "English"),
    ("ja", "日本語"),
    ("ko", "한국어"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("es", "Español"),
    ("ru", "Русский"),
    ("pt", "Português"),
    ("it", "Italiano"),
    ("ar", "العربية"),
    ("th", "ไทย"),
    ("vi", "Tiếng Việt"),
    ("id", "Indonesia"),
    ("ms", "Melayu"),
    ("nl", "Nederlands"),
    ("pl", "Polski"),
    ("tr", "Türkçe"),
    ("hi", "हिन्दी"),
    ("uk", "Українська"),
    ("ug", "维吾尔语"),
    ("bo", "བོད་སྐད"),
    ("kk", "Қазақша"),
    ("ky", "Кыргызча"),
    ("mn", "Монгол"),
    ("fa", "فارسی"),
    ("ur", "اردو"),
]
LANG_CODE_TO_NAME = {c: n for c, n in LANGUAGES}
LANG_NAME_TO_CODE = {n: c for c, n in LANGUAGES}
GOOGLE_LANG_MAP = {"zh": "zh", "en": "en", "ja": "ja", "ko": "ko", "fr": "fr", "de": "de", "es": "es", "ru": "ru", "pt": "pt", "it": "it", "ar": "ar", "th": "th", "vi": "vi", "id": "id", "ms": "ms", "nl": "nl", "pl": "pl", "tr": "tr", "hi": "hi", "uk": "uk", "ug": "ug", "bo": "bo", "kk": "kk", "ky": "ky", "mn": "mn", "fa": "fa", "ur": "ur", "auto": "auto"}

def pick_font_for_text(text: str, size=10, bold=False):
    """根据文字脚本自动选最合适的字体，避免维吾尔语等显示为方框"""
    if not text:
        return ("Microsoft YaHei UI", size, "bold" if bold else "normal")
    # 检测是否含阿拉伯/维吾尔字符 (U+0600-06FF, 0750-077F, FB50-FDFF, FE70-FEFF)
    has_arabic = any(0x0600 <= ord(c) <= 0x06FF or 0x0750 <= ord(c) <= 0x077F or 0xFB50 <= ord(c) <= 0xFDFF or 0xFE70 <= ord(c) <= 0xFEFF for c in text)
    has_thai = any(0x0E00 <= ord(c) <= 0x0E7F for c in text)
    has_tibetan = any(0x0F00 <= ord(c) <= 0x0FFF for c in text)
    has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in text)
    # 优先专用字体
    if has_arabic:
        # 维吾尔语/阿拉伯语用 Microsoft Uighur 最全，其次 Arial Unicode MS
        for fam in ("Microsoft Uighur", "Arial Unicode MS", "Segoe UI", "Microsoft YaHei UI"):
            try:
                # 测试字体是否存在（创建Font对象不抛异常即存在）
                import tkinter.font as tkfont
                f = tkfont.Font(family=fam, size=size)
                # 简单检查：若字体名能创建则认为可用
                return (fam, size, "bold" if bold else "normal")
            except:
                continue
        return ("Microsoft Uighur", size, "bold" if bold else "normal")
    if has_thai:
        return ("Leelawadee UI", size, "bold" if bold else "normal")
    if has_tibetan:
        return ("Microsoft Himalaya", size, "bold" if bold else "normal")
    if has_devanagari:
        return ("Nirmala UI", size, "bold" if bold else "normal")
    # 默认中文/英文/日韩等用雅黑+Segoe UI混合
    return ("Microsoft YaHei UI", size, "bold" if bold else "normal")

# ---------- 翻译引擎 ----------

class Translator:
    def __init__(self):
        self.session = requests.Session() if requests else None
        if self.session:
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
        self._cache = {}
        self._last_google_ts = 0.0
        self._tts_cache = {}

    def _throttle_google(self, interval=0.3):
        # Google 系接口限流保护：两次调用至少间隔 interval 秒，防 429
        try:
            now = time.time()
            wait = interval - (now - self._last_google_ts)
            if wait > 0:
                time.sleep(wait)
            self._last_google_ts = time.time()
        except:
            pass

    def detect_target(self, text: str):
        # 旧逻辑保留兼容
        if is_chinese(text):
            return "zh", "en"
        else:
            return "en", "zh"

    def translate(self, text: str, src="auto", tgt="zh"):
        text = text.strip()
        if not text:
            return ""
        if len(text) > 2000:
            text = text[:2000]
        # 规范化
        src = GOOGLE_LANG_MAP.get(src, src)
        tgt = GOOGLE_LANG_MAP.get(tgt, tgt)
        if tgt == "auto":
            tgt = "zh"  # 目标不能是auto
        if src == tgt and src != "auto":
            return text  # 同语言无需翻译

        # 缓存命中直接返回
        cache_key = (text, src, tgt)
        try:
            if cache_key in self._cache:
                return self._cache[cache_key]
        except:
            pass

        # 长文本分段，避免单次请求过长被拒
        chunks = self._split_chunks(text, limit=800)
        if len(chunks) > 1:
            parts = []
            for ch in chunks:
                r = self._translate_single(ch, src, tgt)
                if r is None or r.startswith("[翻译失败"):
                    return r or "[翻译失败，点击左下🔁重试]"
                parts.append(r)
            sep = "" if tgt in ("zh", "ja", "ko", "bo") else " "
            final = sep.join(parts)
            try:
                self._cache[cache_key] = final
                if len(self._cache) > 200:
                    self._cache.clear()
            except:
                pass
            return final

        res = self._translate_single(text, src, tgt)
        if res is None:
            return "[翻译失败，点击左下🔁重试]"
        try:
            self._cache[cache_key] = res
        except:
            pass
        return res

    def _split_chunks(self, text, limit=800):
        if len(text) <= limit:
            return [text]
        # 按句子边界切分
        sentences = re.split(r'(?<=[。！？!?\n；;])', text)
        chunks, cur = [], ""
        for s in sentences:
            if len(cur) + len(s) <= limit:
                cur += s
            else:
                if cur:
                    chunks.append(cur)
                # 单句超长则硬切
                while len(s) > limit:
                    chunks.append(s[:limit])
                    s = s[limit:]
                cur = s
        if cur:
            chunks.append(cur)
        return chunks or [text]

    def _translate_single(self, text, src, tgt):
        # 链路1: dict-chrome-ex (clients5, 实测不吃 429, 支持 auto)
        res = self._dict_chrome(text, src, tgt)
        if res:
            return res
        # 链路2: Google GTX
        res = self._google_gtx(text, src, tgt)
        if res:
            return res
        # 链路3: MyMemory (不支持auto，需精准猜测源语言，避免日语被误判为中文导致 zh|zh)
        def guess_lang(t):
            # 按脚本特征精准猜测，避免日语假名被当中文
            if re.search(r'[\u3040-\u309F\u30A0-\u30FF]', t):
                return "ja"  # 平假名/片假名 -> 日语
            if re.search(r'[\uAC00-\uD7AF\u1100-\u11FF]', t):
                return "ko"
            if re.search(r'[\u0400-\u04FF]', t):
                return "ru"
            if re.search(r'[\u0E00-\u0E7F]', t):
                return "th"
            if re.search(r'[\u0600-\u06FF\u0750-\u077F]', t):
                # 阿拉伯/维吾尔/波斯等，含维吾尔特有字符则ug
                if re.search(r'[\u0626\u0649\u06C6\u06C7\u06CB\u06D0]', t):
                    return "ug"
                return "ar"
            if re.search(r'[\u0900-\u097F]', t):
                return "hi"
            if re.search(r'[\u0F00-\u0FFF]', t):
                return "bo"
            if re.search(r'[\u4E00-\u9FFF]', t):
                return "zh"
            return "en"
        if src == "auto":
            guess = guess_lang(text)
            # 若猜测和目标相同，说明无需翻译或MyMemory会报"SELECT TWO DISTINCT"，跳过回退
            if guess == tgt:
                return "[无需翻译：检测为目标语言]"
            res = self._mymemory(text, guess, tgt)
        else:
            if src != tgt:
                res = self._mymemory(text, src, tgt)
            else:
                res = None
        if res:
            # 过滤 MyMemory 的错误提示
            if "PLEASE SELECT TWO DISTINCT" in res.upper():
                return "[无需翻译：源与目标相同]"
            if "MYMEMORY WARNING" in res.upper():
                return None
            return res
        return "[翻译失败，请检查网络或稍后重试]"

    def _dict_chrome(self, text, src, tgt):
        # clients5 dict-chrome-ex: 返回 [["译文","检测到的源语言"]], 不限流
        if not self.session:
            return None
        try:
            self._throttle_google(0.25)
            url = "https://clients5.google.com/translate_a/t"
            params = {"client": "dict-chrome-ex", "sl": src, "tl": tgt, "q": text}
            r = self.session.get(url, params=params, timeout=7)
            if r.status_code == 200:
                try:
                    data = r.json()
                except:
                    return None
                # 格式: [["译文","ja"]] 或 [[["译文","原文",...]],...]
                try:
                    if isinstance(data, list) and data:
                        first = data[0]
                        if isinstance(first, list) and first:
                            if isinstance(first[0], str):
                                result = first[0].strip()
                                if result and result != text:
                                    return result
                                if result and result == text and src == "auto":
                                    det = first[1] if len(first) > 1 and isinstance(first[1], str) else ""
                                    if det == tgt:
                                        return "[无需翻译：检测为目标语言]"
                                    if result == text:
                                        return result  # 同语言原文返回，避免报失败
                            elif isinstance(first[0], list) and first[0]:
                                parts = [seg[0] for seg in first if seg and isinstance(seg, list) and seg and isinstance(seg[0], str)]
                                result = "".join(parts).strip()
                                if result and result != text:
                                    return result
                except:
                    pass
        except:
            pass
        return None

    def _google_gtx(self, text, src, tgt):
        if not self.session:
            return None
        # 重试一次，处理429
        for attempt in range(2):
            try:
                self._throttle_google(0.3)
                url = "https://translate.googleapis.com/translate_a/single"
                params = {
                    "client": "gtx",
                    "sl": src,
                    "tl": tgt,
                    "dt": "t",
                    "q": text
                }
                r = self.session.get(url, params=params, timeout=7)
                if r.status_code == 200:
                    data = r.json()
                    if data and data[0]:
                        parts = [seg[0] for seg in data[0] if seg and seg[0]]
                        result = "".join(parts).strip()
                        if result and result != text:
                            return result
                        # 检测到同语言时 Google 可能返回原文，此时若 src==auto 且结果==原文，视为无需翻译但不报错
                        if result and result == text and src == "auto":
                            # 尝试用检测到的语言判断，若检测为tgt则无需翻译
                            try:
                                detected = data[2] if len(data) > 2 and data[2] else ""
                                if detected == tgt:
                                    return "[无需翻译：检测为目标语言]"
                            except:
                                pass
                elif r.status_code == 429:
                    time.sleep(0.6)
                    continue
            except Exception as e:
                time.sleep(0.3)
                continue
        return None

    def tts_fetch(self, chunk, tl):
        """免费在线 TTS 取 MP3（单段 ≤200 字符），失败返回 None"""
        chunk = (chunk or "").strip()
        if not chunk or not self.session:
            return None
        key = (chunk, tl)
        try:
            if key in self._tts_cache:
                return self._tts_cache[key]
        except:
            pass
        try:
            self._throttle_google(0.25)
            r = self.session.get(
                "https://translate.googleapis.com/translate_tts",
                params={"ie": "UTF-8", "client": "gtx", "tl": tl, "q": chunk},
                timeout=8,
                headers={"Referer": "https://translate.google.com/"},
            )
            ct = r.headers.get("Content-Type", "")
            if r.status_code == 200 and "audio" in ct and len(r.content) > 1000:
                try:
                    self._tts_cache[key] = r.content
                    if len(self._tts_cache) > 100:
                        self._tts_cache.clear()
                except:
                    pass
                return r.content
        except:
            pass
        return None

    def _mymemory(self, text, src, tgt):
        if not self.session:
            return None
        # MyMemory 免费接口单次 ~450 字符，超长直接跳过（上层已分段）
        if len(text) > 450:
            return None
        try:
            langpair = f"{src}|{tgt}"
            url = "https://api.mymemory.translated.net/get"
            r = self.session.get(url, params={"q": text, "langpair": langpair}, timeout=7)
            if r.status_code == 200:
                j = r.json()
                trans = (j.get("responseData", {}) or {}).get("translatedText", "")
                if trans:
                    up = trans.upper()
                    if "PLEASE SELECT TWO DISTINCT" in up:
                        return "[无需翻译：源与目标相同]"
                    if "MYMEMORY WARNING" in up or "QUERY LENGTH LIMIT" in up:
                        return None
                    if trans != text:
                        return trans
        except:
            pass
        return None

# ---------- 星星悬浮窗 ----------

class StarWindow:
    def __init__(self, root: tk.Tk, on_click_callback):
        self.root = root
        self.on_click = on_click_callback
        self.win = None
        self.hide_timer = None
        self.current_text = ""
        self.current_pos = (0, 0)
        self.visible = False

    def _create(self):
        if self.win:
            try:
                self.win.destroy()
            except:
                pass
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        # 透明背景 - 用品红做透明键，牛来图里没有此色；
        # 之前用 #000001 极暗色，圆形边缘抗锯齿像素与黑底混合形成黑边
        self.win.attributes("-transparentcolor", "#FF00FF")
        self.win.config(bg="#FF00FF")
        # 牛来画布 56x56 更大更清晰（用户要求更大）
        self.canvas = tk.Canvas(self.win, width=56, height=56, bg="#FF00FF", highlightthickness=0, bd=0)
        self.canvas.pack()
        # 先初始化引用再画图：否则 _draw_star 存的 PhotoImage 会被下一行清掉导致头像空白
        self._photo_ref = None
        self._draw_star(normal=True)
        # 绑定
        self.canvas.bind("<Button-1>", lambda e: self._clicked())
        self.canvas.bind("<Enter>", lambda e: self._draw_star(normal=False))
        self.canvas.bind("<Leave>", lambda e: self._draw_star(normal=True))
        # 防止牛来抢焦点导致失去选区
        self.win.bind("<Button-1>", lambda e: self._clicked())
        self.canvas.bind("<ButtonRelease-1>", lambda e: self._clicked())
        self.win.attributes("-alpha", 0.0)

    def _draw_star(self, normal=True):
        """牛来头像 - 优先加载同目录 niulai.png/jpg，无则用矢量牛头"""
        self.canvas.delete("all")
        # --- 尝试加载自定义牛来图片 ---
        try:
            import os, sys
            # exe/源码同目录查找
            base = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
            # 兼容 PyInstaller 打包后的路径
            candidates = []
            if getattr(sys, 'frozen', False):
                exe_dir = os.path.dirname(sys.executable)
                meipass = getattr(sys, '_MEIPASS', exe_dir)
                # 优先外部可替换的图片（exe同级）
                candidates += [os.path.join(exe_dir, n) for n in ("niulai.png","niulai.jpg","niulai.jpeg","牛来.png","牛来.jpg")]
                # 再检查 MEIPASS 内置（打包时 --add-data）
                candidates += [os.path.join(meipass, n) for n in ("niulai.png","niulai.jpg","牛来.png")]
                # 再检查 base 和上级
                candidates += [os.path.join(base, n) for n in ("niulai.png","niulai.jpg","牛来.png")]
                candidates += [os.path.join(os.path.dirname(exe_dir), "悬浮翻译小星星", n) for n in ("niulai.png","niulai.jpg","牛来.png")]
            else:
                candidates = [os.path.join(base, n) for n in ("niulai.png","niulai.jpg","niulai.jpeg","牛来.png","牛来.jpg")]
                candidates.append(os.path.join(os.getcwd(), "niulai.png"))
            img_path = None
            for p in candidates:
                if os.path.exists(p):
                    img_path = p
                    break
            if img_path:
                from PIL import Image, ImageTk, ImageDraw
                # 整图用 PIL 一次合成：品红底(透明键)+白底金圈+牛来圆图，
                # 不再用 canvas 画阴影/边框椭圆——那些抗锯齿边缘就是黑边来源；
                # 牛来外圈用二值硬边缘，窗口透明键才能干净抠掉
                S = 56
                size = 46 if normal else 50
                cow_src = Image.open(img_path).convert("RGBA")
                # 去黑边关键1：原图透明像素 RGB 是黑色，LANCZOS 会把黑混进圆边缘；
                # 先在原尺寸把透明区垫成白色再缩放，边缘晕染就是白色而非黑色
                cow_src = Image.alpha_composite(
                    Image.new("RGBA", cow_src.size, (255, 255, 255, 255)), cow_src)
                cow = cow_src.resize((size, size), Image.LANCZOS)
                mask = Image.new("L", (size, size), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
                mask = mask.point(lambda p: 255 if p > 128 else 0)  # 硬边缘
                try:
                    from PIL import ImageFilter
                    # 内缩2px：原图自带的软描边晕影较宽，1px切不干净
                    mask = mask.filter(ImageFilter.MinFilter(3))
                    mask = mask.filter(ImageFilter.MinFilter(3))
                except:
                    pass
                cow.putalpha(mask)
                base = Image.new("RGBA", (S, S), (255, 0, 255, 255))  # 与透明键同色
                bd = ImageDraw.Draw(base)
                bd.ellipse((3, 3, S - 4, S - 4), fill="white")
                bd.ellipse((3, 3, S - 4, S - 4), outline="#FFB800", width=2)
                base.paste(cow, ((S - size) // 2, (S - size) // 2), cow)
                photo = ImageTk.PhotoImage(base)
                self.canvas.create_image(28, 28, image=photo)
                self._photo_ref = photo
                return
        except Exception as e:
            # print("load niulai fail", e)
            pass
        # --- 矢量牛来兜底（无图片时）--- 56画布，放大版
        cx, cy = 28, 28
        scale = 1.35 if not normal else 1.22  # 整体比原来大30%
        # 悬停放大+发光（无阴影椭圆，避免透明键下出现深色描边）
        bg_circle = "#FFE8A0" if not normal else "#FFF4CC"
        border_col = "#FFB800" if not normal else "#E8A800"
        # 外圈底色
        self.canvas.create_oval(cx-17*scale, cy-17*scale, cx+17*scale, cy+17*scale, fill=bg_circle, outline=border_col, width=1.8)
        # 耳朵（左右）
        self.canvas.create_oval(cx-18*scale, cy-6, cx-9*scale, cy+4, fill="#3B2314", outline=border_col, width=1)  # 左耳深棕
        self.canvas.create_oval(cx+9*scale, cy-6, cx+18*scale, cy+4, fill="#3B2314", outline=border_col, width=1)
        self.canvas.create_oval(cx-15*scale, cy-3, cx-10*scale, cy+1, fill="#FFB6C1", outline="", width=0)  # 耳内粉
        self.canvas.create_oval(cx+10*scale, cy-3, cx+15*scale, cy+1, fill="#FFB6C1", outline="", width=0)
        #  horns 小牛角
        self.canvas.create_polygon(cx-9*scale, cy-13*scale, cx-7*scale, cy-18*scale, cx-4*scale, cy-13*scale, fill="#FFD700", outline="#B8860B", width=1, smooth=False)
        self.canvas.create_polygon(cx+9*scale, cy-13*scale, cx+7*scale, cy-18*scale, cx+4*scale, cy-13*scale, fill="#FFD700", outline="#B8860B", width=1, smooth=False)
        # 脸主色 白
        self.canvas.create_oval(cx-13*scale, cy-9*scale, cx+13*scale, cy+11*scale, fill="white", outline="#E8A800", width=1)
        # 额头棕色块
        self.canvas.create_oval(cx-11*scale, cy-9*scale, cx+11*scale, cy+0*scale, fill="#8B4513", outline="", width=0)
        self.canvas.create_oval(cx-7*scale, cy-6*scale, cx+7*scale, cy+1*scale, fill="#A0522D", outline="", width=0)
        # 黑色斑点
        self.canvas.create_oval(cx-10*scale, cy-1*scale, cx-6*scale, cy+5*scale, fill="#2B1B0E", outline="", width=0)
        self.canvas.create_oval(cx+7*scale, cy-3*scale, cx+10*scale, cy+1*scale, fill="#2B1B0E", outline="", width=0)
        # 眼睛
        self.canvas.create_oval(cx-7*scale, cy-1*scale, cx-2*scale, cy+5*scale, fill="white", outline="#2B1B0E", width=1)
        self.canvas.create_oval(cx+2*scale, cy-1*scale, cx+7*scale, cy+5*scale, fill="white", outline="#2B1B0E", width=1)
        self.canvas.create_oval(cx-5.5*scale, cy+1*scale, cx-2.5*scale, cy+4*scale, fill="black", outline="", width=0)
        self.canvas.create_oval(cx+2.5*scale, cy+1*scale, cx+5.5*scale, cy+4*scale, fill="black", outline="", width=0)
        self.canvas.create_oval(cx-5*scale, cy+1.5*scale, cx-3.5*scale, cy+2.5*scale, fill="white", outline="", width=0)
        self.canvas.create_oval(cx+3*scale, cy+1.5*scale, cx+4.5*scale, cy+2.5*scale, fill="white", outline="", width=0)
        # 鼻子粉色大鼻头
        self.canvas.create_oval(cx-7*scale, cy+6*scale, cx+7*scale, cy+12*scale, fill="#FFC0CB", outline="#E68AA0", width=1)
        self.canvas.create_oval(cx-3*scale, cy+8*scale, cx-1*scale, cy+10*scale, fill="#8B4513", outline="", width=0)
        self.canvas.create_oval(cx+1*scale, cy+8*scale, cx+3*scale, cy+10*scale, fill="#8B4513", outline="", width=0)
        # 嘴巴微笑
        self.canvas.create_arc(cx-4*scale, cy+9*scale, cx+4*scale, cy+14*scale, start=200, extent=140, outline="#8B4513", width=1.2, style="arc")
        # 腮红
        self.canvas.create_oval(cx-12*scale, cy+4*scale, cx-8*scale, cy+7*scale, fill="#FFB6C1", outline="", width=0)
        self.canvas.create_oval(cx+8*scale, cy+4*scale, cx+12*scale, cy+7*scale, fill="#FFB6C1", outline="", width=0)
        # 头顶文字“牛来”小标签
        # 用白色小圆角矩形模拟
        self.canvas.create_oval(cx-10, cy+13, cx+10, cy+18, fill="#FF4757", outline="white", width=1)
        self.canvas.create_text(cx, cy+15.5, text="牛来", font=("Microsoft YaHei UI", 5, "bold"), fill="white")

    def show(self, text: str, x: int, y: int):
        self.current_text = text
        self.current_pos = (x, y)
        if not self.win:
            self._create()
        # 定位在鼠标左下角: x-4, y+14 (窗口56x56 更大)
        px = x - 4
        py = y + 14
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        if px + 56 > sw:
            px = sw - 60
        if py + 56 > sh:
            py = y - 62
        self.win.geometry(f"56x56+{px}+{py}")
        self.win.deiconify()
        self.win.lift()
        self.visible = True
        # 淡入
        self._fade_in()
        # 4秒自动隐藏
        if self.hide_timer:
            self.root.after_cancel(self.hide_timer)
        self.hide_timer = self.root.after(4000, self.hide)

    def _fade_in(self, alpha=0.0):
        if not self.win or not self.visible:
            return
        alpha += 0.22
        if alpha >= 1.0:
            alpha = 1.0
            self.win.attributes("-alpha", 1.0)
            # 轻微弹跳
            self._bounce(0)
            return
        try:
            self.win.attributes("-alpha", alpha)
            self.root.after(18, lambda: self._fade_in(alpha))
        except:
            pass

    def _bounce(self, step):
        if not self.win or not self.visible:
            return
        scales = [0, 1, 2, 1, 0]
        if step < len(scales):
            dy = scales[step]
            try:
                g = self.win.geometry()
                _, pos = g.split("+", 1)
                x, y = pos.split("+")
                self.win.geometry(f"56x56+{x}+{int(y)-dy}")
            except:
                pass
            self.root.after(45, lambda: self._bounce(step+1))

    def hide(self):
        self.visible = False
        if self.hide_timer:
            try:
                self.root.after_cancel(self.hide_timer)
            except:
                pass
            self.hide_timer = None
        if self.win:
            try:
                self.win.withdraw()
            except:
                pass

    def _clicked(self):
        # 点击星星 -> 回调
        text = self.current_text
        x, y = self.current_pos
        self.hide()
        if text and self.on_click:
            self.on_click(text, x, y)

# ---------- 可打断朗读引擎（悬浮卡片 + 主窗口共用） ----------

def _safe_set_widget(widget, **kw):
    try:
        if widget is not None and widget.winfo_exists():
            widget.config(**kw)
    except:
        pass


def _cow_photo(size=32):
    """牛来标题栏图标（主窗口用），找不到返回 None"""
    try:
        import os, sys
        base = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
        candidates = []
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            meipass = getattr(sys, '_MEIPASS', exe_dir)
            candidates += [os.path.join(exe_dir, "niulai.png"), os.path.join(meipass, "niulai.png")]
        candidates += [os.path.join(base, "niulai.png"), os.path.join(os.getcwd(), "niulai.png")]
        for p in candidates:
            if os.path.exists(p):
                from PIL import Image, ImageTk
                img = Image.open(p).convert("RGBA").resize((size, size), Image.LANCZOS)
                return ImageTk.PhotoImage(img)
    except:
        pass
    return None


class Speaker:
    """常驻朗读线程 + 指令队列（speak/stop），关窗即停。
    root: Tk 根；translator: 复用 Translator（含在线TTS）；on_restore(which, fb) 播完恢复按钮；
    on_missing(lang, which, fb) 所有链路失败时的指引。"""

    def __init__(self, root, translator, on_restore=None, on_missing=None):
        self.root = root
        self.translator = translator
        self._on_restore = on_restore
        self._on_missing = on_missing
        self._queue = None
        self._thread = None
        self._lock = threading.Lock()
        self._tmp = None
        self._net_tmp = None

    def speak(self, text, tts_lang, which, fallback_text):
        self._ensure()
        try:
            self._queue.put_nowait(("speak", text, tts_lang, which, fallback_text))
        except:
            pass

    def stop(self):
        try:
            if self._queue is not None:
                try:
                    while True:
                        self._queue.get_nowait()
                except:
                    pass
                self._queue.put_nowait(("stop",))
        except:
            pass

    def _restore(self, which, fallback_text):
        try:
            if self._on_restore:
                self._on_restore(which, fallback_text)
        except:
            pass

    def _missing(self, tts_lang, which, fallback_text):
        try:
            if self._on_missing:
                self._on_missing(tts_lang, which, fallback_text)
        except:
            pass

    def _ensure(self):
        try:
            with self._lock:
                if self._thread is not None and self._thread.is_alive():
                    return
                import queue as pyqueue
                self._queue = pyqueue.Queue()
                self._thread = threading.Thread(target=self._worker, daemon=True)
                self._thread.start()
        except:
            pass

    def _write_tmp(self, text):
        try:
            import tempfile, os
            self._cleanup_tmp()
            fd, tmp = tempfile.mkstemp(suffix=".txt", prefix="xy_tts_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text[:280])
            self._tmp = tmp
            return tmp
        except:
            return None

    def _cleanup_tmp(self):
        try:
            import os
            if self._tmp and os.path.exists(self._tmp):
                os.remove(self._tmp)
        except:
            pass
        self._tmp = None

    def _cleanup_net(self):
        try:
            import os
            if self._net_tmp and os.path.exists(self._net_tmp):
                os.remove(self._net_tmp)
        except:
            pass
        self._net_tmp = None

    def _split_online(self, text, limit=175):
        if len(text) <= limit:
            return [text]
        parts = re.split(r'(?<=[。！？!?…\n；;])', text)
        chunks, cur = [], ""
        for s in parts:
            if len(cur) + len(s) <= limit:
                cur += s
            else:
                if cur:
                    chunks.append(cur)
                while len(s) > limit:
                    chunks.append(s[:limit])
                    s = s[limit:]
                cur = s
        if cur:
            chunks.append(cur)
        return chunks or [text]

    def _fetch_all(self, text, tts_lang):
        """在线免费 TTS 拉全段 MP3；不支持/失败返回 None"""
        if tts_lang in ONLINE_TTS_SKIP:
            return None
        tl = ONLINE_TTS_TL.get(tts_lang, tts_lang)
        try:
            out = b""
            for ch in self._split_online(text.strip()[:320]):
                b = self.translator.tts_fetch(ch, tl)
                if not b:
                    return None
                out += b
            return out or None
        except:
            return None

    def _media_start(self, mp3bytes):
        """MediaPlayer播在线 MP3，返回 Popen 或 None"""
        try:
            import subprocess, tempfile, os
            self._cleanup_net()
            fd, tmp = tempfile.mkstemp(suffix=".mp3", prefix="xy_tts_")
            with os.fdopen(fd, "wb") as f:
                f.write(mp3bytes)
            self._net_tmp = tmp
            uri = "file:///" + tmp.replace("\\", "/")
            ps = ("Add-Type -AssemblyName PresentationCore; "
                  "$m=New-Object System.Windows.Media.MediaPlayer; $m.Volume=1.0; "
                  f"$m.Open('{uri}'); $m.Play(); $sw=0; "
                  "while (-not $m.NaturalDuration.HasTimeSpan -and $sw -lt 6) { Start-Sleep -Milliseconds 200; $sw+=0.2 }; "
                  "if (-not $m.NaturalDuration.HasTimeSpan) { exit 2 }; $sw=0; "
                  "while ($sw -lt 90) { Start-Sleep -Milliseconds 200; $sw+=0.2; "
                  "try { if ($m.Position.TotalSeconds + 0.4 -ge $m.NaturalDuration.TimeSpan.TotalSeconds) { break } } catch { break } }; "
                  "$m.Stop(); exit 0")
            return subprocess.Popen(["powershell", "-NoProfile", "-Command", ps],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    **_silent_proc_kwargs())
        except:
            self._cleanup_net()
            return None

    def _ps_has_voice(self, culture):
        try:
            import subprocess
            check = ("Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                     f"$v=$s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -like '{culture}*' }} | Select-Object -First 1; "
                     "if($v){Write-Output HASVOICE}")
            rc = subprocess.run(["powershell", "-NoProfile", "-Command", check], timeout=10, capture_output=True,
                                **_silent_proc_kwargs())
            return bool(rc.stdout and b"HASVOICE" in rc.stdout)
        except:
            return False

    def _ps_popen(self, tmp, culture):
        try:
            import subprocess
            ps = ("Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate=0; $s.Volume=100; "
                  f"$v=$s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -like '{culture}*' }} | Select-Object -First 1; "
                  "if($v){$s.SelectVoice($v.VoiceInfo.Name)}; "
                  f"$t=Get-Content -Encoding UTF8 -Raw '{tmp}'; $s.Speak($t)")
            return subprocess.Popen(["powershell", "-NoProfile", "-Command", ps],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    **_silent_proc_kwargs())
        except:
            return None

    def _worker(self):
        # 独占 SAPI 对象，speak 用异步+轮询，收到 stop 立刻 purge
        import queue as pyqueue
        try:  # COM 单元初始化：否则异步 Speak 的状态回调永远不推进
            import pythoncom
            pythoncom.CoInitialize()
        except:
            pass
        speaker = None
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
        except Exception:
            speaker = None
        proc = None
        speaking_sapi = False
        start_ts = 0.0
        deadline = 0.0
        active = None  # (which, fallback_text)
        q = self._queue

        def sapi_running():
            try:
                return bool(speaking_sapi and speaker is not None and speaker.Status.RunningState == 2)
            except:
                return False

        def ps_running():
            try:
                return proc is not None and proc.poll() is None
            except:
                return False

        def kill_all():
            nonlocal proc, speaking_sapi
            if speaker is not None:
                try:
                    speaker.Speak("", 2)  # purge，打断当前朗读
                except:
                    pass
            speaking_sapi = False
            if proc is not None:
                try:
                    proc.terminate()
                except:
                    pass
                try:
                    proc.wait(timeout=2)
                except:
                    try:
                        proc.kill()
                    except:
                        pass
                proc = None
            self._cleanup_tmp()
            self._cleanup_net()

        while True:
            try:
                cmd = q.get(timeout=0.1)
            except Exception:
                cmd = None
            try:  # 泵 COM 消息：SAPI 异步状态靠它推进，不泵会永远"播放中"
                import pythoncom
                pythoncom.PumpWaitingMessages()
            except:
                pass
            if cmd is not None:
                op = cmd[0]
                if op == "quit":
                    kill_all()
                    return
                if op == "stop":
                    kill_all()
                    if active is not None:
                        self._restore(*active)
                        active = None
                    continue
                if op == "speak":
                    _, text, tts_lang, which, fallback_text = cmd
                    kill_all()
                    active = (which, fallback_text)
                    started = False
                    # 1) 本地 SAPI（最快，离线可用）
                    if speaker is not None:
                        voice = pick_sapi_voice(speaker, tts_lang)
                        if voice is not None:
                            try:
                                speaker.Voice = voice
                                speaker.Rate = 0
                                speaker.Volume = 100
                                speaker.Speak(text, 1)  # 异步
                                speaking_sapi = True
                                start_ts = time.time()
                                deadline = start_ts + max(20.0, len(text) * 0.4)
                                started = True
                            except Exception as e:
                                _log("SAPI朗读失败:", e)
                                speaking_sapi = False
                    # 2) 在线免费语音（无本地包时兜底，如日语）
                    if not started:
                        mp3 = self._fetch_all(text, tts_lang)
                        if mp3 and q.empty():
                            proc = self._media_start(mp3)
                            if proc is not None:
                                start_ts = time.time()
                                deadline = start_ts + max(30.0, len(text) * 0.5)
                                started = True
                        elif mp3:
                            continue  # 有排队指令（stop/新speak），本次放弃
                    # 3) PowerShell 本地嗓音兜底（COM 不可用时）
                    if not started and q.empty():
                        culture = TTS_VOICE_TABLE.get(tts_lang, TTS_VOICE_TABLE["en"])["culture"]
                        if self._ps_has_voice(culture):
                            tmp = self._write_tmp(text)
                            if tmp is not None:
                                proc = self._ps_popen(tmp, culture)
                                if proc is not None:
                                    start_ts = time.time()
                                    deadline = start_ts + max(25.0, len(text) * 0.5)
                                    started = True
                    if started:
                        continue
                    if not q.empty():
                        continue  # 被新指令打断，不弹指引
                    self._missing(tts_lang, which, fallback_text)
                    self._restore(which, fallback_text)
                    active = None
                    continue
            # 无新指令：检查自然播完 / 超时强停
            if speaking_sapi or proc is not None:
                now = time.time()
                finished = False
                if now - start_ts > 0.6:
                    if speaking_sapi and not sapi_running():
                        finished = True
                    if proc is not None and not ps_running():
                        finished = True
                if not finished and deadline and now > deadline:
                    kill_all()
                    finished = True
                if finished:
                    speaking_sapi = False
                    if proc is not None:
                        try:
                            proc.wait(timeout=1)
                        except:
                            pass
                        proc = None
                    self._cleanup_tmp()
                    self._cleanup_net()
                    if active is not None:
                        self._restore(*active)
                        active = None


# ---------- 免费词典（音标/简明/例句，有道 jsonapi，无 key） ----------

class DictClient:
    """有道免费词典：音标/简明/例句。失败返回 None，由调用方降级为纯翻译。"""

    def __init__(self):
        self.session = requests.Session() if requests else None
        if self.session:
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
                "Referer": "https://www.youdao.com/",
            })
        self._cache = {}

    @staticmethod
    def _txt(x):
        # 有道字段形态多变：str / dict(#tran/#text/i) / list，统一成字符串
        if x is None:
            return ""
        if isinstance(x, str):
            return x.strip()
        if isinstance(x, dict):
            for k in ("#tran", "#text"):
                v = x.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            for k in ("l", "i"):
                v = x.get(k)
                if isinstance(v, list):
                    parts = [p for p in (DictClient._txt(i) for i in v) if p]
                    if parts:
                        return "；".join(parts)
                elif isinstance(v, str) and v.strip():
                    return v.strip()
            return ""
        if isinstance(x, list):
            parts = [p for p in (DictClient._txt(i) for i in x) if p]
            return "；".join(parts)
        try:
            return str(x).strip()
        except:
            return ""

    def lookup(self, query):
        q = (query or "").strip()
        if not q or len(q) > 200 or not self.session:
            return None
        try:
            if q in self._cache:
                return self._cache[q]
        except:
            pass
        try:
            r = self.session.get("https://dict.youdao.com/jsonapi", params={"q": q}, timeout=6)
            if r.status_code != 200:
                return None
            j = r.json()
        except:
            return None
        try:
            res = {"usphone": "", "ukphone": "", "phone": "", "defs": [], "examples": []}
            # 英汉 ec
            ec = j.get("ec") or {}
            words = ec.get("word") or []
            if words and isinstance(words, list) and isinstance(words[0], dict):
                w0 = words[0]
                res["usphone"] = (w0.get("usphone") or "").strip()
                res["ukphone"] = (w0.get("ukphone") or "").strip()
                for tr in (w0.get("trs") or [])[:8]:
                    if not isinstance(tr, dict):
                        continue
                    pos = (tr.get("pos") or "").strip()
                    t = self._txt(tr.get("tran"))
                    if t:
                        res["defs"].append(f"{pos} {t}".strip() if pos else t)
            # 汉英 ce / ce_new
            for cekey in ("ce", "ce_new"):
                ce = j.get(cekey) or {}
                cwords = ce.get("word") or []
                if cwords and isinstance(cwords, list) and isinstance(cwords[0], dict):
                    cw = cwords[0]
                    if not res["phone"]:
                        res["phone"] = (cw.get("phone") or "").strip()
                    for trs in (cw.get("trs") or [])[:4]:
                        if not isinstance(trs, dict):
                            continue
                        for tr in (trs.get("tr") or [])[:6]:
                            if not isinstance(tr, dict):
                                continue
                            t = self._txt(tr.get("l"))
                            if t and t not in res["defs"] and len(res["defs"]) < 10:
                                res["defs"].append(t)
            # simple 兜底读音
            try:
                sw = (j.get("simple") or {}).get("word") or []
                if sw and isinstance(sw[0], dict):
                    if not res["phone"] and not res["usphone"]:
                        res["phone"] = ((sw[0].get("phone") or "").strip()
                                        or (sw[0].get("usphone") or "").strip())
            except:
                pass
            # 双语例句
            try:
                pairs = ((j.get("blng_sents_part") or {}).get("sentence-pair")) or []
                for p in pairs[:8]:
                    if not isinstance(p, dict):
                        continue
                    a = (p.get("sentence") or "").strip()
                    b = (p.get("sentence-translation") or "").strip()
                    if a or b:
                        res["examples"].append((a, b))
            except:
                pass
            if not res["defs"] and not res["examples"] and not res["usphone"] and not res["phone"]:
                return None
            try:
                self._cache[q] = res
                if len(self._cache) > 100:
                    self._cache.clear()
            except:
                pass
            return res
        except:
            return None


# ---------- 翻译卡片悬浮窗 ----------

class TranslatePopup:
    def __init__(self, root: tk.Tk, translator: Translator):
        self.root = root
        self.translator = translator
        self.win = None
        self.src_lang = "auto"
        self.tgt_lang = "zh"
        self.original = ""
        self.translated = ""
        self.anchor_x = 0
        self.anchor_y = 0
        # 可打断朗读：共用 Speaker，关窗即停
        self.speaker = Speaker(root, translator,
                               on_restore=self._tts_restore_btn,
                               on_missing=self._missing_voice_hint)

    def _create_window(self):
        if self.win:
            try:
                self.win.destroy()
            except:
                pass
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.config(bg="#000001")
        self.win.attributes("-transparentcolor", "#000001")
        # 卡片容器 - 毛玻璃拟物风
        CARD = "#FDFDFE"
        self.card = tk.Frame(self.win, bg=CARD, bd=0, highlightthickness=0)
        self.card.pack(padx=7, pady=7)
        # 顶部标题栏 - 多语言选择（通栏胶囊）
        header = tk.Frame(self.card, bg="#F4F6FB")
        header.pack(fill="x", padx=12, pady=(12, 0))
        from tkinter import ttk
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except:
            pass
        style.configure("Lang.TCombobox", fieldbackground="white", background="white",
                        foreground="#334155", bordercolor="#E5E7EB", arrowcolor="#94A3B8", padding=3)
        self.var_src = tk.StringVar(value=LANG_CODE_TO_NAME.get(self.src_lang, "自动检测"))
        self.combo_src = ttk.Combobox(header, textvariable=self.var_src, values=[n for _, n in LANGUAGES], state="readonly", width=10, style="Lang.TCombobox", font=("Microsoft YaHei UI", 8))
        self.combo_src.pack(side="left", padx=(8, 0), pady=6)
        self.combo_src.bind("<<ComboboxSelected>>", lambda e: self._on_lang_change())
        tk.Label(header, text="→", font=("Microsoft YaHei UI", 9), fg="#94A3B8", bg="#F4F6FB").pack(side="left", padx=4)
        self.var_tgt = tk.StringVar(value=LANG_CODE_TO_NAME.get(self.tgt_lang, "中文"))
        tgt_names = [n for c, n in LANGUAGES if c != "auto"]
        self.combo_tgt = ttk.Combobox(header, textvariable=self.var_tgt, values=tgt_names, state="readonly", width=10, style="Lang.TCombobox", font=("Microsoft YaHei UI", 8))
        self.combo_tgt.pack(side="left")
        self.combo_tgt.bind("<<ComboboxSelected>>", lambda e: self._on_lang_change())
        # 切换按钮（圆角药丸）
        self.btn_switch = tk.Label(header, text="⇄", font=("Microsoft YaHei UI", 9), fg="#2563EB", bg="#DBEAFE", cursor="hand2", padx=8, pady=2)
        self.btn_switch.pack(side="left", padx=(6, 4))
        self.btn_switch.bind("<Button-1>", lambda e: self._switch_lang())
        self.btn_switch.bind("<Enter>", lambda e: self.btn_switch.config(bg="#BFDBFE"))
        self.btn_switch.bind("<Leave>", lambda e: self.btn_switch.config(bg="#DBEAFE"))
        # 状态标题（小字）
        self.lab_title = tk.Label(header, text="", font=("Microsoft YaHei UI", 7), fg="#94A3B8", bg="#F4F6FB", anchor="w")
        self.lab_title.pack(side="left", padx=(4, 0))
        # 关闭 X
        lab_close = tk.Label(header, text="✕", font=("Segoe UI", 10), fg="#94A3B8", bg="#F4F6FB", cursor="hand2", padx=6)
        lab_close.pack(side="right", padx=(0, 6))
        lab_close.bind("<Button-1>", lambda e: self.hide())
        lab_close.bind("<Enter>", lambda e: lab_close.config(fg="#EF4444"))
        lab_close.bind("<Leave>", lambda e: lab_close.config(fg="#94A3B8"))

        # 原文面板（柔和灰蓝，像磨砂玻璃底）
        self.frame_orig = tk.Frame(self.card, bg="#F5F7FA", bd=0)
        self.frame_orig.pack(fill="x", padx=12, pady=(12, 0))
        self.lab_orig = tk.Label(self.frame_orig, text="", font=("Microsoft YaHei UI", 9), fg="#475569", bg="#F5F7FA", wraplength=340, justify="left", anchor="w")
        self.lab_orig.pack(fill="x", padx=12, pady=9)

        # 译文面板（白底为主，拟物层次靠间距区分，不再用硬分割线）
        frame_trans = tk.Frame(self.card, bg=CARD)
        frame_trans.pack(fill="x", padx=12, pady=(10, 0))
        self.lab_trans = tk.Label(frame_trans, text="…", font=("Microsoft YaHei UI", 12, "bold"), fg="#0F172A", bg=CARD, wraplength=340, justify="left", anchor="w")
        self.lab_trans.pack(fill="x", padx=12, pady=(8, 4))

        # 底部操作栏（药丸按钮）
        footer = tk.Frame(self.card, bg=CARD)
        footer.pack(fill="x", padx=12, pady=(8, 12))
        pill = dict(font=("Microsoft YaHei UI", 8), cursor="hand2", padx=11, pady=5)
        # 复制
        self.btn_copy = tk.Label(footer, text="📋 复制译文", fg="#475569", bg="#F1F5F9", **pill)
        self.btn_copy.pack(side="left")
        self.btn_copy.bind("<Button-1>", lambda e: self._copy_trans())
        self.btn_copy.bind("<Enter>", lambda e: self.btn_copy.config(bg="#E2E8F0"))
        self.btn_copy.bind("<Leave>", lambda e: self.btn_copy.config(bg="#F1F5F9"))
        # 朗读原文
        self.btn_speak_orig = tk.Label(footer, text="🔊 原文", fg="#475569", bg="#F1F5F9", **pill)
        self.btn_speak_orig.pack(side="left", padx=(8, 0))
        self.btn_speak_orig.bind("<Button-1>", lambda e: self._speak(which="orig"))
        self.btn_speak_orig.bind("<Enter>", lambda e: self.btn_speak_orig.config(bg="#E2E8F0"))
        self.btn_speak_orig.bind("<Leave>", lambda e: self.btn_speak_orig.config(bg="#F1F5F9"))
        # 朗读译文（主按钮蓝，同色 hover 换色）
        self.btn_speak_trans = tk.Label(footer, text="🔊 译文", fg="#FFFFFF", bg="#2563EB", **pill)
        self.btn_speak_trans.pack(side="left", padx=(6, 0))
        self.btn_speak_trans.bind("<Button-1>", lambda e: self._speak(which="trans"))
        self.btn_speak_trans.bind("<Enter>", lambda e: self.btn_speak_trans.config(bg="#1D4ED8"))
        self.btn_speak_trans.bind("<Leave>", lambda e: self.btn_speak_trans.config(bg="#2563EB"))
        # 重试（仅失败显示）
        self.btn_retry = tk.Label(footer, text="🔁 重试", fg="#FFFFFF", bg="#EF4444", **pill)
        self.btn_retry.bind("<Button-1>", lambda e: self.retry())
        self.btn_retry.bind("<Enter>", lambda e: self.btn_retry.config(bg="#DC2626"))
        self.btn_retry.bind("<Leave>", lambda e: self.btn_retry.config(bg="#EF4444"))
        # 提示
        tk.Label(footer, text="ESC 关闭", font=("Microsoft YaHei UI", 7), fg="#CBD5E1", bg=CARD).pack(side="right", pady=4)

        # 阴影模拟：外层用 Frame border
        self.win.bind("<FocusOut>", lambda e: None)
        self.root.bind("<Escape>", lambda e: self.hide())

        # 拖动
        header.bind("<Button-1>", self._start_drag)
        header.bind("<B1-Motion>", self._on_drag)
        self.lab_title.bind("<Button-1>", self._start_drag)
        self.lab_title.bind("<B1-Motion>", self._on_drag)

    def _start_drag(self, e):
        self._drag_x = e.x_root - self.win.winfo_x()
        self._drag_y = e.y_root - self.win.winfo_y()

    def _on_drag(self, e):
        x = e.x_root - self._drag_x
        y = e.y_root - self._drag_y
        self.win.geometry(f"+{x}+{y}")

    def _on_lang_change(self):
        # 下拉改变后重新翻译
        try:
            src_name = self.var_src.get()
            tgt_name = self.var_tgt.get()
            self.src_lang = LANG_NAME_TO_CODE.get(src_name, "auto")
            self.tgt_lang = LANG_NAME_TO_CODE.get(tgt_name, "zh")
            if self.src_lang == self.tgt_lang and self.src_lang != "auto":
                self.lab_title.config(text="同语言无需翻译")
                return
            self.lab_title.config(text="翻译中…")
            self.lab_trans.config(text="翻译中…", fg="#6B7280")
            threading.Thread(target=self._do_translate, daemon=True).start()
        except:
            pass

    def show(self, text: str, x: int, y: int):
        self.original = text.strip()
        if not self.original:
            return
        self.anchor_x, self.anchor_y = x, y
        # 智能默认：自动检测 → 中文（用户需求2），若检测为中文且目标也是中文，自动切英文
        # 初次显示时保持 auto→zh，下拉可改
        # 若当前已是同语言，自动保持
        if not hasattr(self, 'src_lang') or not self.src_lang:
            self.src_lang = "auto"
        if not hasattr(self, 'tgt_lang') or not self.tgt_lang:
            self.tgt_lang = "zh"
        # 若上次用户选了非auto，保留；否则每次都auto→zh
        # 为满足“自动识别成中文”，默认 auto→zh
        if self.src_lang != "auto" and self.tgt_lang != "zh":
            # 保留用户上次选择
            pass
        else:
            self.src_lang = "auto"
            self.tgt_lang = "zh"

        self._create_window()
        # 同步下拉显示
        try:
            self.var_src.set(LANG_CODE_TO_NAME.get(self.src_lang, "自动检测"))
            self.var_tgt.set(LANG_CODE_TO_NAME.get(self.tgt_lang, "中文"))
        except:
            pass
        self.lab_title.config(text="自动检测 → 中文" if self.src_lang=="auto" else "")
        # 原文截断显示 + 字体自适应（维吾尔语等）
        display_orig = self.original if len(self.original) < 500 else self.original[:500] + "…"
        try:
            f_orig = pick_font_for_text(display_orig, 9)
            self.lab_orig.config(text=display_orig, font=f_orig)
        except:
            self.lab_orig.config(text=display_orig)
        self.lab_trans.config(text="翻译中…", fg="#6B7280", font=("Microsoft YaHei UI", 11))
        # 先定位再更新自适应高度
        self._position_window(x, y, initial=True)
        self.win.deiconify()
        self.win.lift()
        self.win.attributes("-alpha", 0.0)
        self._fade_in()
        # 异步翻译
        threading.Thread(target=self._do_translate, daemon=True).start()

    def _position_window(self, x, y, initial=False):
        self.win.update_idletasks()
        w = self.win.winfo_reqwidth()
        h = self.win.winfo_reqheight()
        # 限制宽度 380
        w = max(320, min(400, w))
        # 目标：鼠标选中文字上方 40px
        px = x - w // 2
        py = y - h - 48
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        if px < 12:
            px = 12
        if px + w > sw - 12:
            px = sw - w - 12
        if py < 12:
            # 放下方
            py = y + 32
        if py + h > sh - 12:
            py = sh - h - 12
        self.win.geometry(f"{w}x{h}+{px}+{py}")
        # 小三角指针（用label模拟）
        # 不额外画，保持简洁，卡片下方加阴影即可

    def _fade_in(self, alpha=0.0):
        alpha += 0.18
        if alpha >= 1.0:
            try:
                self.win.attributes("-alpha", 1.0)
            except:
                pass
            return
        try:
            self.win.attributes("-alpha", alpha)
            self.root.after(16, lambda: self._fade_in(alpha))
        except:
            pass

    def retry(self):
        try:
            try:
                self.btn_retry.pack_forget()
            except:
                pass
            self.lab_trans.config(text="翻译中…", fg="#6B7280")
            self.lab_title.config(text="重试中…")
            threading.Thread(target=self._do_translate, daemon=True).start()
        except:
            pass

    def _is_failure(self, text):
        return bool(text) and ("[翻译失败" in text or "翻译出错" in text)

    def _do_translate(self):
        try:
            result = self.translator.translate(self.original, src=self.src_lang if self.src_lang!="auto" else "auto", tgt=self.tgt_lang)
        except Exception as e:
            result = f"翻译出错: {e}"
        # 回主线程更新
        def update():
            self.translated = result
            try:
                # 译文字体也自适应
                f_trans = pick_font_for_text(result, 11)
                if self._is_failure(result):
                    self.lab_trans.config(text=result, fg="#DC2626", font=f_trans)
                    try:
                        self.btn_retry.pack(side="left", padx=(6, 0))
                    except:
                        pass
                else:
                    self.lab_trans.config(text=result, fg="#111827", font=f_trans)
                    try:
                        self.btn_retry.pack_forget()
                    except:
                        pass
                # 原文字体再确认一次（防止创建窗口后语言变化）
                try:
                    f_orig = pick_font_for_text(self.original, 9)
                    self.lab_orig.config(font=f_orig)
                except:
                    pass
                # 更新标题显示实际方向
                src_n = LANG_CODE_TO_NAME.get(self.src_lang, self.src_lang)
                tgt_n = LANG_CODE_TO_NAME.get(self.tgt_lang, self.tgt_lang)
                self.lab_title.config(text=f"{src_n} → {tgt_n}")
                # 重新定位以适应高度
                self._position_window(self.anchor_x, self.anchor_y)
            except:
                pass
        self.root.after(0, update)

    def _switch_lang(self):
        # 交换下拉值（auto不能作为目标，需处理）
        if self.src_lang == "auto":
            # auto→zh 交换变成 zh→auto 不合法，改为 zh→en
            self.src_lang = self.tgt_lang
            self.tgt_lang = "en" if self.src_lang == "zh" else "zh"
        else:
            self.src_lang, self.tgt_lang = self.tgt_lang, self.src_lang
            if self.tgt_lang == "auto":
                self.tgt_lang = "zh"
        # 同步下拉
        try:
            self.var_src.set(LANG_CODE_TO_NAME.get(self.src_lang, "自动检测"))
            self.var_tgt.set(LANG_CODE_TO_NAME.get(self.tgt_lang, "中文"))
        except:
            pass
        self.lab_title.config(text="已交换")
        # 交换原文译文显示并重新翻译
        if self.translated and self.translated != "翻译中…":
            tmp = self.original
            self.original = self.translated
            self.translated = tmp
            self.lab_orig.config(text=self.original[:500])
            self.lab_trans.config(text=self.translated)
            self._position_window(self.anchor_x, self.anchor_y)
        else:
            self.lab_trans.config(text="翻译中…", fg="#6B7280")
            threading.Thread(target=self._do_translate, daemon=True).start()

    def _copy_trans(self):
        if self.translated and self.translated != "翻译中…":
            set_clipboard_text(self.root, self.translated)
            orig = self.btn_copy.cget("text")
            self.btn_copy.config(text="✓ 已复制", fg="#059669", bg="#D1FAE5")
            self.root.after(1200, lambda: self.btn_copy.config(text=orig, fg="#374151", bg="#F3F4F6"))

    def _speak(self, which="trans"):
        # which: "orig" 朗读原文, "trans" 朗读译文
        if which == "orig":
            text = self.original
            btn = self.btn_speak_orig
            fallback_text = "🔊 原文"
        else:
            # 译文未就绪则用原文兜底，但按钮提示
            if not self.translated or self.translated in ("翻译中…", "…", ""):
                text = self.original
            else:
                text = self.translated
            btn = self.btn_speak_trans
            fallback_text = "🔊 译文"
        if not text or not text.strip():
            return
        text = text.strip()[:320]
        # 朗读时禁用文字过长检测
        if len(text) < 1:
            return
        tts_lang = detect_tts_lang(text)
        # 发指令给共用 Speaker（关窗自动停）
        try:
            self.speaker.speak(text, tts_lang, which, fallback_text)
        except:
            pass
        try:
            btn.config(text="▶ 播放中…")
        except:
            pass
        # 兜底恢复（正常播完由线程回调恢复，这里防线程异常卡死）
        try:
            self.root.after(30000, lambda b=btn, t=fallback_text: self._safe_set(b, text=t))
        except:
            pass

    def _safe_set(self, widget, **kw):
        try:
            if widget is not None and widget.winfo_exists():
                widget.config(**kw)
        except:
            pass

    def _missing_voice_hint(self, tts_lang, which, fallback_text):
        label = TTS_VOICE_TABLE.get(tts_lang, {}).get("label", tts_lang)
        btn = self.btn_speak_orig if which == "orig" else self.btn_speak_trans
        def show():
            try:
                try:
                    if self.win is None or not self.win.winfo_viewable():
                        return
                except:
                    return
                from tkinter import messagebox
                self._safe_set(btn, text=f"❌ {label}读失败")
                messagebox.showinfo(
                    "小袁翻译 - 朗读失败",
                    f"【{label}】读不出来，本地没嗓音、在线语音也没拿到。\n\n"
                    "办法1（离线用，1分钟）：\n"
                    "设置 → 时间和语言 → 语言和区域 → 添加语言\n"
                    f"→ 搜索“{label}”→ 下一步 → 勾选“语音”→ 安装\n\n"
                    "办法2：连上网后重试（自动用免费在线语音）。",
                    parent=self.win,
                )
            except:
                pass
            try:
                self.root.after(3000, lambda: self._safe_set(btn, text=fallback_text))
            except:
                pass
        try:
            self.root.after(0, show)
        except:
            pass

    def _tts_stop(self):
        # 关窗/重读时打断当前朗读
        try:
            self.speaker.stop()
        except:
            pass

    def _tts_restore_btn(self, which, fallback_text):
        try:
            btn = self.btn_speak_orig if which == "orig" else self.btn_speak_trans
            self.root.after(0, lambda: self._safe_set(btn, text=fallback_text))
        except:
            pass

    def hide(self):
        # 关窗即停读
        try:
            self._tts_stop()
        except:
            pass
        if self.win:
            try:
                self.win.withdraw()
            except:
                pass
        try:
            self._safe_set(getattr(self, "btn_speak_orig", None), text="🔊 原文")
            self._safe_set(getattr(self, "btn_speak_trans", None), text="🔊 译文")
        except:
            pass

# ---------- 主窗口（词典式自主互译） ----------

class MainWindow:
    """独立主窗口：语向选择 + 输入 + 音标 + 简明/例句 + 双喇叭 + 历史。
    经托盘菜单/双击打开，右上 X 为隐藏（不退出）。"""

    def __init__(self, root, translator, dict_client):
        self.root = root
        self.translator = translator
        self.dict_client = dict_client
        self.win = None
        self.speaker = Speaker(root, translator,
                               on_restore=self._on_speak_restore,
                               on_missing=self._on_speak_missing)
        self.src_lang = "auto"
        self.tgt_lang = "zh"
        self._tab = "brief"
        self._data = {"trans": "", "defs": [], "examples": [],
                      "usphone": "", "ukphone": "", "phone": "", "query": ""}
        self._busy = False
        self._history = []
        self._hist_file = self._hist_path()
        self._btns = {}
        self._topmost = True

    # ----- 历史持久化 -----
    def _hist_path(self):
        try:
            import os
            base = os.getenv("APPDATA") or os.path.expanduser("~")
            d = os.path.join(base, "XYTranslator")
            if not os.path.exists(d):
                os.makedirs(d)
            return os.path.join(d, "history.json")
        except:
            return None

    def _load_hist(self):
        if not self._hist_file:
            return
        try:
            import json, os
            if os.path.exists(self._hist_file):
                with open(self._hist_file, "r", encoding="utf-8") as f:
                    items = json.load(f)
                if isinstance(items, list):
                    self._history = [(str(a), str(b)) for a, b in items[:30]]
        except:
            pass

    def _save_hist(self):
        if not self._hist_file:
            return
        try:
            import json
            with open(self._hist_file, "w", encoding="utf-8") as f:
                json.dump(self._history[:30], f, ensure_ascii=False)
        except:
            pass

    # ----- 窗口 -----
    def _build(self):
        from tkinter import ttk
        self.win = tk.Toplevel(self.root)
        self.win.title("小袁翻译")
        try:
            _ic = _cow_photo(32)
            if _ic is not None:
                self.win.iconphoto(True, _ic)
                self._icon_photo = _ic  # 持有引用防回收
        except:
            pass
        self.win.attributes("-topmost", True)
        self.win.geometry("480x640")
        try:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            self.win.geometry(f"480x640+{(sw - 480) // 2}+{(sh - 640) // 2}")
        except:
            pass
        # 最小高度保证 读译文/历史 不被挤出可视区
        self.win.minsize(430, 600)
        self.win.protocol("WM_DELETE_WINDOW", self.hide)
        self.win.withdraw()

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except:
            pass
        style.configure("Lang.TCombobox", fieldbackground="white", background="white",
                        foreground="#334155", bordercolor="#E5E7EB", arrowcolor="#94A3B8", padding=3)

        CARD = "#FDFDFE"
        top = tk.Frame(self.win, bg=CARD)
        top.pack(fill="both", expand=True)

        # 语向栏（通栏胶囊）
        langbar = tk.Frame(top, bg="#F4F6FB")
        langbar.pack(fill="x", padx=14, pady=(12, 0))
        tk.Label(langbar, text="从", font=("Microsoft YaHei UI", 9), fg="#64748B", bg="#F4F6FB").pack(side="left", padx=(8, 0))
        self.var_src = tk.StringVar(value="自动检测")
        self.combo_src = ttk.Combobox(langbar, textvariable=self.var_src,
                                      values=[n for _, n in LANGUAGES], state="readonly",
                                      width=11, style="Lang.TCombobox", font=("Microsoft YaHei UI", 9))
        self.combo_src.pack(side="left", padx=(4, 0), pady=6)
        self.combo_src.bind("<<ComboboxSelected>>", lambda e: self._on_lang_ui())
        tk.Label(langbar, text="→", font=("Microsoft YaHei UI", 10), fg="#94A3B8", bg="#F4F6FB").pack(side="left", padx=6)
        tk.Label(langbar, text="到", font=("Microsoft YaHei UI", 9), fg="#64748B", bg="#F4F6FB").pack(side="left")
        self.var_tgt = tk.StringVar(value="中文")
        self.combo_tgt = ttk.Combobox(langbar, textvariable=self.var_tgt,
                                      values=[n for c, n in LANGUAGES if c != "auto"], state="readonly",
                                      width=11, style="Lang.TCombobox", font=("Microsoft YaHei UI", 9))
        self.combo_tgt.pack(side="left", padx=(4, 0), pady=6)
        self.combo_tgt.bind("<<ComboboxSelected>>", lambda e: self._on_lang_ui())
        self.btn_swap = tk.Label(langbar, text="⇄", font=("Microsoft YaHei UI", 10), fg="#2563EB",
                                 bg="#DBEAFE", cursor="hand2", padx=8, pady=2)
        self.btn_swap.pack(side="left", padx=(8, 0))
        self.btn_swap.bind("<Button-1>", lambda e: self._swap())
        self.btn_swap.bind("<Enter>", lambda e: self.btn_swap.config(bg="#BFDBFE"))
        self.btn_swap.bind("<Leave>", lambda e: self.btn_swap.config(bg="#DBEAFE"))
        self.btn_pin = tk.Label(langbar, text="📌", font=("Segoe UI", 10), fg="#64748B",
                                bg="#F4F6FB", cursor="hand2", padx=6)
        self.btn_pin.pack(side="right", padx=(0, 6))
        self.btn_pin.bind("<Button-1>", lambda e: self._toggle_pin())

        # 输入框（柔和灰蓝磨砂底）
        inframe = tk.Frame(top, bg="#F5F7FA")
        inframe.pack(fill="x", padx=14, pady=(10, 0))
        self.txt_in = tk.Text(inframe, height=4, font=("Microsoft YaHei UI", 13), fg="#0F172A",
                              bg="#F5F7FA", relief="flat", bd=0, padx=10, pady=10,
                              wrap="word", highlightthickness=0, insertbackground="#2563EB")
        self.txt_in.pack(side="left", fill="both", expand=True)
        self.txt_in.bind("<Control-Return>", lambda e: (self.translate(), "break")[1])
        sider = tk.Frame(inframe, bg="#F5F7FA")
        sider.pack(side="right", fill="y", padx=(0, 6), pady=6)
        self.btn_paste = tk.Label(sider, text="📋", font=("Segoe UI", 11), fg="#94A3B8",
                                  bg="#F5F7FA", cursor="hand2")
        self.btn_paste.pack(pady=2)
        self.btn_paste.bind("<Button-1>", lambda e: self._paste_in())
        self.btn_clear = tk.Label(sider, text="✕", font=("Segoe UI", 11), fg="#94A3B8",
                                  bg="#F5F7FA", cursor="hand2")
        self.btn_clear.pack(pady=2)
        self.btn_clear.bind("<Button-1>", lambda e: self._clear_in())
        self._placeholder()

        # 操作行
        act = tk.Frame(top, bg=CARD)
        act.pack(fill="x", padx=14, pady=(10, 0))
        self.btn_go = tk.Label(act, text="🔍 翻译  (Ctrl+Enter)", font=("Microsoft YaHei UI", 10, "bold"),
                               fg="white", bg="#2563EB", cursor="hand2", padx=18, pady=6)
        self.btn_go.pack(side="left")
        self.btn_go.bind("<Button-1>", lambda e: self.translate())
        self.btn_go.bind("<Enter>", lambda e: self.btn_go.config(bg="#1D4ED8"))
        self.btn_go.bind("<Leave>", lambda e: self.btn_go.config(bg="#2563EB"))
        self.btn_spk_in = tk.Label(act, text="🔊 读输入", font=("Microsoft YaHei UI", 9),
                                   fg="#475569", bg="#F1F5F9", cursor="hand2", padx=12, pady=6)
        self.btn_spk_in.pack(side="left", padx=(8, 0))
        self.btn_spk_in.bind("<Button-1>", lambda e: self._speak_in())
        self.btn_spk_in.bind("<Enter>", lambda e: self.btn_spk_in.config(bg="#E2E8F0"))
        self.btn_spk_in.bind("<Leave>", lambda e: self.btn_spk_in.config(bg="#F1F5F9"))
        self.lab_status = tk.Label(act, text="", font=("Microsoft YaHei UI", 8), fg="#94A3B8", bg=CARD)
        self.lab_status.pack(side="right")

        # 音标行
        self.frame_ph = tk.Frame(top, bg=CARD)
        self.frame_ph.pack(fill="x", padx=14, pady=(10, 0))
        self.lab_ph_us = tk.Label(self.frame_ph, text="", font=("Microsoft YaHei UI", 10),
                                  fg="#475569", bg=CARD)
        self.lab_ph_us.pack(side="left")
        self.btn_ph_us = tk.Label(self.frame_ph, text="🔊", font=("Segoe UI", 10), fg="#94A3B8",
                                  bg=CARD, cursor="hand2")
        self.btn_ph_us.bind("<Button-1>", lambda e: self._speak_query())
        self.lab_ph_uk = tk.Label(self.frame_ph, text="", font=("Microsoft YaHei UI", 10),
                                  fg="#475569", bg=CARD)
        self.btn_ph_uk = tk.Label(self.frame_ph, text="🔊", font=("Segoe UI", 10), fg="#94A3B8",
                                  bg=CARD, cursor="hand2")
        self.btn_ph_uk.bind("<Button-1>", lambda e: self._speak_query())
        self.frame_ph.pack_forget()  # 默认隐藏，有音标才显示

        # 选项卡
        tabbar = tk.Frame(top, bg=CARD)
        tabbar.pack(fill="x", padx=14, pady=(10, 0))
        self.tab_brief = tk.Label(tabbar, text="简明", font=("Microsoft YaHei UI", 10, "bold"),
                                  fg="#DC2626", bg=CARD, cursor="hand2", padx=4)
        self.tab_brief.pack(side="left")
        self.tab_brief.bind("<Button-1>", lambda e: self._switch_tab("brief"))
        self.tab_sents = tk.Label(tabbar, text="例句", font=("Microsoft YaHei UI", 10),
                                  fg="#64748B", bg=CARD, cursor="hand2", padx=4)
        self.tab_sents.pack(side="left", padx=(16, 0))
        self.tab_sents.bind("<Button-1>", lambda e: self._switch_tab("sents"))
        self.bar_brief = tk.Frame(tabbar, bg="#DC2626", height=2, width=36)
        self.bar_sents = tk.Frame(tabbar, bg=CARD, height=2, width=36)
        # 下划线跟随（放在选项卡下一行）
        underline = tk.Frame(top, bg=CARD)
        underline.pack(fill="x", padx=14, pady=0)
        self.bar_brief.place(in_=tabbar, relx=0, rely=1, anchor="sw")
        self._refresh_tabs()

        # 结果区
        resframe = tk.Frame(top, bg=CARD)
        resframe.pack(fill="both", expand=True, padx=14, pady=(6, 0))
        # 高度给小（默认24行会把底部按钮挤出窗外），expand 负责随窗口放大
        self.txt_out = tk.Text(resframe, height=7, font=("Microsoft YaHei UI", 11), fg="#0F172A", bg=CARD,
                               relief="flat", bd=0, padx=4, pady=4, wrap="word",
                               highlightthickness=0, state="disabled")
        sc = tk.Scrollbar(resframe, command=self.txt_out.yview)
        self.txt_out.config(yscrollcommand=sc.set)
        self.txt_out.pack(side="left", fill="both", expand=True)
        sc.pack(side="right", fill="y")

        # 结果操作
        act2 = tk.Frame(top, bg=CARD)
        act2.pack(fill="x", padx=14, pady=(8, 0))
        self.btn_spk_out = tk.Label(act2, text="🔊 读译文", font=("Microsoft YaHei UI", 9),
                                    fg="white", bg="#2563EB", cursor="hand2", padx=12, pady=5)
        self.btn_spk_out.pack(side="left")
        self.btn_spk_out.bind("<Button-1>", lambda e: self._speak_out())
        self.btn_spk_out.bind("<Enter>", lambda e: self.btn_spk_out.config(bg="#1D4ED8"))
        self.btn_spk_out.bind("<Leave>", lambda e: self.btn_spk_out.config(bg="#2563EB"))
        self.btn_copy = tk.Label(act2, text="📋 复制译文", font=("Microsoft YaHei UI", 9),
                                 fg="#475569", bg="#F1F5F9", cursor="hand2", padx=12, pady=5)
        self.btn_copy.pack(side="left", padx=(8, 0))
        self.btn_copy.bind("<Button-1>", lambda e: self._copy_out())
        self.btn_copy.bind("<Enter>", lambda e: self.btn_copy.config(bg="#E2E8F0"))
        self.btn_copy.bind("<Leave>", lambda e: self.btn_copy.config(bg="#F1F5F9"))

        # 历史
        histbar = tk.Frame(top, bg=CARD)
        histbar.pack(fill="x", padx=14, pady=(8, 0))
        tk.Label(histbar, text="历史（双击重查）", font=("Microsoft YaHei UI", 8), fg="#94A3B8", bg=CARD).pack(side="left")
        self.btn_hist_clear = tk.Label(histbar, text="清空", font=("Microsoft YaHei UI", 8), fg="#9CA3AF",
                                       bg="white", cursor="hand2")
        self.btn_hist_clear.pack(side="right")
        self.btn_hist_clear.bind("<Button-1>", lambda e: self._hist_clear())
        self.list_hist = tk.Listbox(top, height=3, font=("Microsoft YaHei UI", 9), fg="#374151",
                                    relief="flat", bd=0, highlightthickness=1,
                                    highlightbackground="#E5E7EB", activestyle="none")
        self.list_hist.pack(fill="x", padx=14, pady=(2, 12))
        self.list_hist.bind("<Double-Button-1>", lambda e: self._hist_reuse())
        self._load_hist_ui()
        self.register_buttons()

    # ----- 显示/隐藏 -----
    def show(self, text=None):
        if self.win is None:
            self._build()
        if text:
            self._set_input(text)
        self.win.deiconify()
        self.win.lift()
        try:
            self.win.attributes("-topmost", self._topmost)
        except:
            pass
        try:
            self.txt_in.focus_set()
        except:
            pass

    def hide(self):
        try:
            self.speaker.stop()
        except:
            pass
        if self.win is not None:
            try:
                self.win.withdraw()
            except:
                pass

    def _toggle_pin(self):
        self._topmost = not self._topmost
        try:
            self.win.attributes("-topmost", self._topmost)
            self.btn_pin.config(fg="#2563EB" if self._topmost else "#9CA3AF")
        except:
            pass

    # ----- 输入区 -----
    def _placeholder(self):
        try:
            if not self.txt_in.get("1.0", "end").strip():
                self.txt_in.insert("1.0", "输入要翻译的文字…")
                self.txt_in.config(fg="#9CA3AF")
                self._ph_on = True
            self.txt_in.bind("<FocusIn>", lambda e: self._ph_off())
            self.txt_in.bind("<FocusOut>", lambda e: self._placeholder())
        except:
            pass

    def _ph_off(self):
        try:
            if getattr(self, "_ph_on", False):
                self.txt_in.delete("1.0", "end")
                self.txt_in.config(fg="#111827")
                self._ph_on = False
        except:
            pass

    def _set_input(self, text):
        try:
            self._ph_on = False
            self.txt_in.delete("1.0", "end")
            self.txt_in.insert("1.0", text)
            self.txt_in.config(fg="#111827")
        except:
            pass

    def _get_input(self):
        try:
            if getattr(self, "_ph_on", False):
                return ""
            return self.txt_in.get("1.0", "end").strip()
        except:
            return ""

    def _clear_in(self):
        try:
            self.txt_in.delete("1.0", "end")
            self._placeholder()
        except:
            pass

    def _paste_in(self):
        try:
            t = get_clipboard_text(self.root) or ""
            if t.strip():
                self._set_input(t.strip()[:1500])
        except:
            pass

    # ----- 语向 -----
    def _on_lang_ui(self):
        try:
            self.src_lang = LANG_NAME_TO_CODE.get(self.var_src.get(), "auto")
            self.tgt_lang = LANG_NAME_TO_CODE.get(self.var_tgt.get(), "zh")
        except:
            pass
        if self._get_input():
            self.translate()

    def _swap(self):
        if self.src_lang == "auto":
            self.src_lang = self.tgt_lang
            self.tgt_lang = "en" if self.src_lang == "zh" else "zh"
        else:
            self.src_lang, self.tgt_lang = self.tgt_lang, self.src_lang
            if self.tgt_lang == "auto":
                self.tgt_lang = "zh"
        try:
            self.var_src.set(LANG_CODE_TO_NAME.get(self.src_lang, "自动检测"))
            self.var_tgt.set(LANG_CODE_TO_NAME.get(self.tgt_lang, "中文"))
        except:
            pass
        if self._get_input():
            self.translate()

    # ----- 翻译 -----
    def translate(self, query=None):
        q = query if query is not None else self._get_input()
        q = (q or "").strip()
        if not q or self._busy:
            return
        if len(q) > 1500:
            q = q[:1500]
        self._busy = True
        src, tgt = self.src_lang, self.tgt_lang
        try:
            self.lab_status.config(text="翻译中…")
        except:
            pass
        threading.Thread(target=self._do_work, args=(q, src, tgt), daemon=True).start()

    def _do_work(self, q, src, tgt):
        try:
            trans = self.translator.translate(q, src=src, tgt=tgt)
        except Exception as e:
            trans = f"翻译出错: {e}"
        info = None
        if len(q) <= 200:
            try:
                info = self.dict_client.lookup(q)
            except:
                info = None
        self.root.after(0, lambda: self._render(q, src, tgt, trans, info))

    def _render(self, q, src, tgt, trans, info):
        self._busy = False
        d = {"trans": trans or "", "defs": [], "examples": [],
             "usphone": "", "ukphone": "", "phone": "", "query": q}
        if info:
            for k in ("usphone", "ukphone", "phone", "defs", "examples"):
                try:
                    d[k] = info.get(k) or d[k]
                except:
                    pass
        self._data = d
        try:
            src_n = LANG_CODE_TO_NAME.get(src, src)
            tgt_n = LANG_CODE_TO_NAME.get(tgt, tgt)
            self.lab_status.config(text=f"{src_n} → {tgt_n}")
        except:
            pass
        self._render_phonetic()
        self._tab = "brief"
        self._refresh_tabs()
        self._render_tab()
        self._hist_add(q, trans)

    # ----- 音标行 -----
    def _render_phonetic(self):
        try:
            has = False
            if self._data.get("usphone"):
                self.lab_ph_us.config(text=f"美 /{self._data['usphone']}/")
                self.lab_ph_us.pack(side="left")
                self.btn_ph_us.pack(side="left", padx=(2, 10))
                has = True
            else:
                self.lab_ph_us.pack_forget()
                self.btn_ph_us.pack_forget()
            if self._data.get("ukphone"):
                self.lab_ph_uk.config(text=f"英 /{self._data['ukphone']}/")
                self.lab_ph_uk.pack(side="left")
                self.btn_ph_uk.pack(side="left", padx=(2, 10))
                has = True
            else:
                self.lab_ph_uk.pack_forget()
                self.btn_ph_uk.pack_forget()
            if not has and self._data.get("phone"):
                self.lab_ph_us.config(text=f"拼音 {self._data['phone']}")
                self.lab_ph_us.pack(side="left")
                self.btn_ph_us.pack(side="left", padx=(2, 10))
                has = True
            if has:
                self.frame_ph.pack(fill="x", padx=14, pady=(10, 0))
            else:
                self.frame_ph.pack_forget()
        except:
            pass

    # ----- 选项卡 -----
    def _refresh_tabs(self):
        try:
            if self._tab == "brief":
                self.tab_brief.config(fg="#DC2626", font=("Microsoft YaHei UI", 10, "bold"))
                self.tab_sents.config(fg="#6B7280", font=("Microsoft YaHei UI", 10))
                self.bar_brief.place(in_=self.tab_brief, relx=0, rely=1, anchor="sw", width=36)
                self.bar_sents.place_forget()
            else:
                self.tab_sents.config(fg="#DC2626", font=("Microsoft YaHei UI", 10, "bold"))
                self.tab_brief.config(fg="#6B7280", font=("Microsoft YaHei UI", 10))
                self.bar_sents.place(in_=self.tab_sents, relx=0, rely=1, anchor="sw", width=36)
                self.bar_brief.place_forget()
        except:
            pass

    def _switch_tab(self, which):
        self._tab = which
        self._refresh_tabs()
        self._render_tab()

    def _set_out(self, text):
        try:
            self.txt_out.config(state="normal")
            self.txt_out.delete("1.0", "end")
            self.txt_out.insert("1.0", text)
            self.txt_out.config(state="disabled")
        except:
            pass

    def _render_tab(self):
        try:
            if self._tab == "brief":
                lines = []
                if self._data.get("trans"):
                    lines.append(self._data["trans"])
                    lines.append("")
                for i, d in enumerate(self._data.get("defs", [])[:10], 1):
                    lines.append(f"{i}. {d}")
                self._set_out("\n".join(lines).strip() or "暂无释义")
            else:
                ex = self._data.get("examples", [])
                if not ex:
                    self._set_out("暂无例句")
                    return
                lines = []
                for i, (a, b) in enumerate(ex, 1):
                    if a:
                        lines.append(f"{i}. {a}")
                    if b:
                        lines.append(f"   {b}")
                    lines.append("")
                self._set_out("\n".join(lines).strip())
        except:
            pass

    # ----- 朗读（共用 Speaker） -----
    def _speak_btn(self, text, which, fallback):
        if not text or not text.strip():
            return
        text = text.strip()[:320]
        tts_lang = detect_tts_lang(text)
        try:
            btn = self._btns[which][0]
            btn.config(text="▶ 播放中…")
        except:
            pass
        try:
            self.speaker.speak(text, tts_lang, which, fallback)
        except:
            pass
        try:
            self.root.after(30000, lambda w=which, f=fallback: self._on_speak_restore(w, f))
        except:
            pass

    def _speak_in(self):
        q = self._get_input()
        if q:
            self._speak_btn(q, "m_in", "🔊 读输入")

    def _speak_out(self):
        t = self._data.get("trans") or ""
        if t and not t.startswith("[翻译失败") and not t.startswith("翻译出错"):
            self._speak_btn(t, "m_out", "🔊 读译文")
        elif self._get_input():
            self._speak_btn(self._get_input(), "m_out", "🔊 读译文")

    def _speak_query(self):
        q = self._data.get("query") or self._get_input()
        if q:
            self._speak_btn(q.split("\n")[0][:120], "m_ph", "🔊")

    def _on_speak_restore(self, which, fallback):
        try:
            btn = self._btns.get(which, (None,))[0]
            _safe_set_widget(btn, text=fallback)
        except:
            pass

    def _on_speak_missing(self, tts_lang, which, fallback):
        label = TTS_VOICE_TABLE.get(tts_lang, {}).get("label", tts_lang)
        def show():
            try:
                try:
                    if self.win is None or not self.win.winfo_viewable():
                        return
                except:
                    return
                from tkinter import messagebox
                try:
                    btn = self._btns.get(which, (None,))[0]
                    _safe_set_widget(btn, text=f"❌ {label}读失败")
                except:
                    pass
                messagebox.showinfo(
                    "小袁翻译 - 朗读失败",
                    f"【{label}】读不出来，本地没嗓音、在线语音也没拿到。\n\n"
                    "办法1（离线用，1分钟）：\n"
                    "设置 → 时间和语言 → 语言和区域 → 添加语言\n"
                    f"→ 搜索“{label}”→ 下一步 → 勾选“语音”→ 安装\n\n"
                    "办法2：连上网后重试（自动用免费在线语音）。",
                    parent=self.win,
                )
            except:
                pass
            try:
                self.root.after(3000, lambda: self._on_speak_restore(which, fallback))
            except:
                pass
        try:
            self.root.after(0, show)
        except:
            pass

    # ----- 复制 -----
    def _copy_out(self):
        try:
            t = self._data.get("trans") or ""
            if t and not t.startswith("[翻译失败"):
                set_clipboard_text(self.root, t)
                self.btn_copy.config(text="✓ 已复制")
                self.root.after(1200, lambda: self.btn_copy.config(text="📋 复制译文"))
        except:
            pass

    # ----- 历史 -----
    def _hist_add(self, q, trans):
        try:
            disp = (q[:26] + "…") if len(q) > 26 else q
            self._history = [(a, b) for a, b in self._history if a != q][:29]
            self._history.insert(0, (q, trans if isinstance(trans, str) else ""))
            self._save_hist()
            self._load_hist_ui()
        except:
            pass

    def _load_hist_ui(self):
        try:
            if not self._history:
                self._load_hist()
            self.list_hist.delete(0, "end")
            for q, t in self._history[:30]:
                short_t = (t[:20] + "…") if len(t) > 20 else t
                self.list_hist.insert("end", f"{q[:24]}  →  {short_t}")
        except:
            pass

    def _hist_reuse(self):
        try:
            sel = self.list_hist.curselection()
            if not sel:
                return
            q = self._history[sel[0]][0]
            self._set_input(q)
            self.translate(q)
        except:
            pass

    def _hist_clear(self):
        try:
            self._history = []
            self._save_hist()
            self.list_hist.delete(0, "end")
        except:
            pass

    def register_buttons(self):
        # _build 后调用：朗读按钮映射（恢复/失败提示用）
        try:
            self._btns = {
                "m_in": (self.btn_spk_in, "🔊 读输入"),
                "m_out": (self.btn_spk_out, "🔊 读译文"),
                "m_ph": (self.btn_ph_us, "🔊"),
            }
        except:
            pass


# ---------- 主程序：选词监听 ----------

class FloatingTranslatorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # 隐藏主窗口
        self.root.attributes("-topmost", True)
        # 保持主循环
        self.translator = Translator()
        self.dict_client = DictClient()
        self.star = StarWindow(self.root, self.on_star_click)
        self.popup = TranslatePopup(self.root, self.translator)
        self.mainwin = None  # 主窗口按需创建

        self.mouse_down_pos = None
        self.mouse_down_time = 0
        self.is_dragging = False
        self.last_clipboard = ""
        self.last_release_time = 0
        self.last_release_pos = (0, 0)
        self.last_try_time = 0
        self._ctrl_down = False
        self._ctrl_a_armed = False
        self.listener = None
        self.running = True

        # 托盘提示窗口
        self._setup_hint()

        # 捕获全局 Esc 关闭弹窗
        self.root.bind_all("<Escape>", lambda e: (self.star.hide(), self.popup.hide()))

    def _setup_hint(self):
        hint = tk.Toplevel(self.root)
        hint.overrideredirect(True)
        hint.attributes("-topmost", True)
        hint.config(bg="#111827")
        hint.attributes("-alpha", 0.92)
        tk.Label(hint, text="🐮 小袁翻译已启动", font=("Microsoft YaHei UI", 10, "bold"), fg="white", bg="#111827").pack(padx=16, pady=(10,2))
        tk.Label(hint, text="选中任意文字 → 鼠标左下角出现牛来 → 点击翻译", font=("Microsoft YaHei UI", 8), fg="#D1D5DB", bg="#111827").pack(padx=16, pady=(0,2))
        tk.Label(hint, text="ESC 关闭弹窗  |  右键托盘打开主窗口/退出", font=("Microsoft YaHei UI", 7), fg="#9CA3AF", bg="#111827").pack(padx=16, pady=(0,10))
        sw = self.root.winfo_screenwidth()
        hint.update_idletasks()
        w = hint.winfo_reqwidth()
        h = hint.winfo_reqheight()
        hint.geometry(f"{w}x{h}+{sw-w-18}+{18}")
        hint.after(3500, lambda: self._fade_out_hint(hint))

    def _fade_out_hint(self, win, alpha=0.92):
        try:
            alpha -= 0.08
            if alpha <= 0:
                win.destroy()
                return
            win.attributes("-alpha", alpha)
            self.root.after(40, lambda: self._fade_out_hint(win, alpha))
        except:
            pass

    def on_star_click(self, text, x, y):
        self.popup.show(text, x, y)

    def _maybe_show_star(self, text, x, y):
        """取词后统一过滤+弹星（鼠标/键盘两路共用）"""
        try:
            t = (text or "").strip()
            # 宽松过滤：允许文件名、短句等；仅排除纯符号
            if not (1 <= len(t) <= 1800):
                return
            # 只要有一个字母/汉字/数字就显示
            if not re.search(r'[\u4e00-\u9fffA-Za-z0-9]', t):
                return
            # 去除多余空白但保留换行语义为空格
            t = re.sub(r'\s+', ' ', t).strip()
            # 太长截断
            if len(t) > 600:
                t = t[:600]
            if t:
                self.root.after(0, lambda: self.star.show(t, x, y))
        except:
            pass

    def _point_in_own_windows(self, x, y):
        """点是否落在自家窗口（星星/卡片/主窗口）内——是则不弹星，避免自扰"""
        try:
            if self._is_click_in_star(x, y) or self._is_click_in_popup(x, y):
                return True
        except:
            pass
        try:
            mw = self.mainwin
            if mw is not None and mw.win is not None and mw.win.winfo_exists():
                try:
                    if not mw.win.winfo_viewable():
                        return False
                except:
                    return False
                wx, wy = mw.win.winfo_x(), mw.win.winfo_y()
                ww, wh = mw.win.winfo_width(), mw.win.winfo_height()
                if wx <= x <= wx + ww and wy <= y <= wy + wh:
                    return True
        except:
            pass
        return False

    def _fire_ctrl_a(self):
        """Ctrl+A 全选：纯键盘操作鼠标监听看不到，用 UIA 在光标处读选区"""
        try:
            now = time.time()
            if now - self.last_try_time < 0.28:
                return
            try:
                mx, my = get_cursor_pos()
            except:
                return
            if (mx == 0 and my == 0) or self._point_in_own_windows(mx, my):
                return
            self.last_try_time = now
            def delayed_key(mx=mx, my=my):
                time.sleep(0.15)
                try:
                    text = uia_get_selection(mx, my)
                except:
                    text = None
                if text:
                    self._maybe_show_star(text, mx, my)
            threading.Thread(target=delayed_key, daemon=True).start()
        except:
            pass

    def show_main(self, text=None):
        # 托盘菜单/双击打开主窗口
        try:
            if self.mainwin is None:
                self.mainwin = MainWindow(self.root, self.translator, self.dict_client)
            self.mainwin.show(text)
        except Exception as e:
            _log("打开主窗口失败:", e)

    def _is_click_in_popup(self, x, y):
        """判断点击是否在翻译卡片内"""
        try:
            if self.popup.win and self.popup.win.winfo_exists() and self.popup.win.winfo_viewable():
                wx = self.popup.win.winfo_x()
                wy = self.popup.win.winfo_y()
                ww = self.popup.win.winfo_width()
                wh = self.popup.win.winfo_height()
                # 加一点边距
                if wx - 4 <= x <= wx + ww + 4 and wy - 4 <= y <= wy + wh + 4:
                    return True
        except:
            pass
        return False

    def _is_click_in_star(self, x, y):
        if not self.star.visible:
            return False
        try:
            sx, sy = self.star.current_pos
            star_x = sx - 4
            star_y = sy + 14
            # 牛来窗口 56x56
            if star_x - 4 <= x <= star_x + 58 and star_y - 4 <= y <= star_y + 58:
                return True
        except:
            pass
        return False

    def _on_mouse_press(self, x, y, button, pressed):
        try:
            if button == pynput_mouse.Button.left:
                if pressed:
                    self.mouse_down_pos = (x, y)
                    self.mouse_down_time = time.time()
                    self.is_dragging = False
                    # 点其他地方自动关闭弹窗（修复1）
                    in_popup = self._is_click_in_popup(x, y)
                    in_star = self._is_click_in_star(x, y)
                    if in_popup or in_star:
                        return  # 点在星星或弹窗内，不隐藏
                    # 点空白处：同时隐藏星星和弹窗
                    if self.star.visible:
                        self.root.after(0, lambda: self.star.hide())
                    if self.popup.win and self.popup.win.winfo_exists():
                        try:
                            if self.popup.win.winfo_viewable():
                                self.root.after(0, lambda: self.popup.hide())
                        except:
                            pass
                else:
                    # left release
                    if self.mouse_down_pos is None:
                        return
                    x0, y0 = self.mouse_down_pos
                    dx = abs(x - x0)
                    dy = abs(y - y0)
                    dt = time.time() - self.mouse_down_time
                    now = time.time()
                    # 双击/三击检测（用于选中单词/整行）
                    is_double = (now - self.last_release_time < 0.45 and
                                 abs(x - self.last_release_pos[0]) < 12 and
                                 abs(y - self.last_release_pos[1]) < 12)
                    # 记录本次释放
                    self.last_release_time = now
                    self.last_release_pos = (x, y)

                    # 防抖：距离上次尝试 <0.28s 跳过
                    if now - self.last_try_time < 0.28:
                        self.mouse_down_pos = None
                        return

                    should_try = False
                    # 拖选：>4px 即算（1个汉字也约6-8px）
                    if dx > 4 or dy > 4:
                        if 0.03 < dt < 2.6:
                            should_try = True
                    # 双击/三击选中单词或整句（dx很小但有选区；三击按得快，下限放宽）
                    elif is_double and 0.03 < dt < 1.5:
                        should_try = True
                    # 单击且在弹窗/星星内已在按下时return，不会到这里

                    if should_try:
                        self.last_try_time = now
                        # 延迟一点再取词，避免选区未稳定；UIA 无副作用，任何软件都安全
                        def delayed(rx=x, ry=y, px0=x0, py0=y0):
                            time.sleep(0.12)
                            text = uia_get_selection(rx, ry)
                            if not text and (abs(rx - px0) > 4 or abs(ry - py0) > 4):
                                # 松手落在行尾空白边距，回读选中起点
                                try:
                                    text = uia_get_selection(px0, py0)
                                except:
                                    text = None
                            if text:
                                self._maybe_show_star(text, rx, ry)
                            # 无有效文字不显示
                        threading.Thread(target=delayed, daemon=True).start()
                    self.mouse_down_pos = None
            elif button == pynput_mouse.Button.right and not pressed:
                # 右键隐藏星星和弹窗
                self.root.after(0, lambda: (self.star.hide(), self.popup.hide()))
            # 滚轮隐藏
            elif button in (pynput_mouse.Button.middle,):
                pass
        except Exception as e:
            # print("mouse error", e)
            pass

    def _on_scroll(self, x, y, dx, dy):
        # 滚轮时隐藏星星，弹窗轻微下移或隐藏？这里选择隐藏星星，弹窗保留但若滚远也隐藏
        self.root.after(0, lambda: self.star.hide())
        # 若弹窗已显示且滚动幅度大，也隐藏，避免遮挡
        if abs(dy) >= 1 or abs(dx) >= 1:
            try:
                if self.popup.win and self.popup.win.winfo_viewable():
                    # 不立刻隐藏，给用户机会；改为 1.2秒后若再次滚动则隐藏
                    pass
            except:
                pass

    def start_mouse_listener(self):
        if not HAS_PYNPUT:
            # 降级：提示
            print("未安装 pynput，无法监听鼠标。请 pip install pynput")
            return
        self.listener = pynput_mouse.Listener(
            on_click=self._on_mouse_press,
            on_scroll=self._on_scroll
        )
        self.listener.start()
        # 键盘监听：Esc 关闭 + Ctrl+A 全选取词（纯键盘操作鼠标看不到）
        try:
            _ctrl_keys = (pynput_keyboard.Key.ctrl, pynput_keyboard.Key.ctrl_l,
                          pynput_keyboard.Key.ctrl_r)

            def _is_a(k):
                try:
                    c = getattr(k, "char", None)
                    return c in ("a", "A", "")
                except:
                    return False

            def on_key_press(key):
                if key == pynput_keyboard.Key.esc:
                    self.root.after(0, lambda: (self.star.hide(), self.popup.hide()))
                    return
                try:
                    if key in _ctrl_keys:
                        self._ctrl_down = True
                        return
                    if _is_a(key) and self._ctrl_down:
                        self._ctrl_a_armed = True
                except:
                    pass

            def on_key_release(key):
                try:
                    if key in _ctrl_keys:
                        if self._ctrl_a_armed:
                            self._ctrl_a_armed = False
                            self._fire_ctrl_a()
                        self._ctrl_down = False
                        return
                    if _is_a(key) and (self._ctrl_down or self._ctrl_a_armed):
                        self._ctrl_a_armed = False
                        self._fire_ctrl_a()
                except:
                    pass

            self.k_listener = pynput_keyboard.Listener(on_press=on_key_press,
                                                       on_release=on_key_release)
            self.k_listener.start()
        except:
            pass

    def run(self):
        # 检查依赖
        if not HAS_PYNPUT:
            # 弹窗提示
            err = tk.Toplevel(self.root)
            err.title("缺少依赖")
            err.geometry("380x160+600+400")
            err.attributes("-topmost", True)
            tk.Label(err, text="缺少依赖", font=("Microsoft YaHei UI", 11, "bold"), fg="#DC2626").pack(pady=12)
            tk.Label(err, text="请先运行：\npip install -r requirements.txt", font=("Consolas", 10), justify="left").pack(pady=6)
            tk.Label(err, text="安装后重新运行 main.py", font=("Microsoft YaHei UI", 9), fg="#6B7280").pack(pady=4)
            self.root.deiconify()
            self.root.mainloop()
            return

        if not requests:
            print("requests 未安装，翻译功能将不可用；请 pip install requests")

        # 启动监听
        self.start_mouse_listener()

        # 后台预热 UIA（首次选中不卡）；缺 pywinauto 则自动取词不可用，主窗口可用
        def _warm():
            try:
                import pywinauto  # noqa
            except:
                pass
        threading.Thread(target=_warm, daemon=True).start()

        # 系统托盘（可选）
        self._try_tray()

        # 保持运行
        try:
            self.root.mainloop()
        finally:
            self.running = False
            try:
                if self.listener:
                    self.listener.stop()
            except:
                pass

    def _try_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
            # 托盘图标 - 直接用你的黄牛照片
            def create_image():
                import os, sys
                # 优先加载你的原图 niulai.png
                candidates = []
                base = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
                if getattr(sys, 'frozen', False):
                    exe_dir = os.path.dirname(sys.executable)
                    meipass = getattr(sys, '_MEIPASS', exe_dir)
                    candidates += [os.path.join(exe_dir, "niulai.png"), os.path.join(meipass, "niulai.png")]
                candidates += [os.path.join(base, "niulai.png"), os.path.join(os.getcwd(), "niulai.png")]
                for p in candidates:
                    try:
                        if os.path.exists(p):
                            im = Image.open(p).convert("RGBA")
                            # 托盘 64x64，直接用你的照片
                            im = im.resize((64, 64), Image.LANCZOS)
                            return im
                    except:
                        continue
                # 兜底矢量
                img = Image.new("RGBA", (64, 64), (0,0,0,0))
                d = ImageDraw.Draw(img)
                d.ellipse([2,2,62,62], fill="#FFF4CC", outline="#FFB800", width=2)
                d.ellipse([4,14,18,28], fill="#3B2314")
                d.ellipse([46,14,60,28], fill="#3B2314")
                d.polygon([(18,12),(22,4),(26,12)], fill="#FFD700", outline="#B8860B", width=1)
                d.polygon([(38,12),(42,4),(46,12)], fill="#FFD700", outline="#B8860B", width=1)
                d.ellipse([14,16,50,48], fill="white", outline="#E8A800", width=1)
                d.ellipse([16,16,48,30], fill="#8B4513")
                d.ellipse([20,28,28,36], fill="white", outline="#2B1B0E", width=1)
                d.ellipse([36,28,44,36], fill="white", outline="#2B1B0E", width=1)
                d.ellipse([23,31,27,35], fill="black")
                d.ellipse([37,31,41,35], fill="black")
                d.ellipse([24,38,40,48], fill="#FFC0CB", outline="#E68AA0", width=1)
                return img
            def on_quit(icon, item):
                icon.stop()
                self.root.after(0, self.root.quit)
            def on_open(icon, item):
                self.root.after(0, self.show_main)
            menu = pystray.Menu(
                pystray.MenuItem("打开主窗口", on_open, default=True),
                pystray.MenuItem("退出小袁翻译", on_quit),
            )
            icon = pystray.Icon("xiaoyuan_translator", create_image(), "小袁翻译", menu)
            threading.Thread(target=icon.run, daemon=True).start()
        except:
            print("提示：关闭窗口或 Ctrl+C 退出。安装 pystray+ pillow 可启用系统托盘。")

if __name__ == "__main__":
    import sys as _sys
    app = FloatingTranslatorApp()
    if len(_sys.argv) > 1 and _sys.argv[1].lower() in ("--main", "-m", "main"):
        # 快捷方式目标加 --main 可直接打开主窗口
        app.root.after(800, lambda: app.show_main())
    app.run()
