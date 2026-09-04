@echo off
chcp 65001 >nul
title 小袁翻译
echo 🐮 正在启动小袁翻译...
echo.
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+ 并勾选 Add to PATH
    pause
    exit /b
)
pip show pynput >nul 2>&1
if errorlevel 1 (
    echo [提示] 首次运行，正在安装依赖...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)
echo.
echo 已启动！去选中任意文字试试，鼠标左下角会出现牛来
echo 右键托盘可打开主窗口；按 Ctrl+C 或关闭此窗口可退出（若有托盘请右键退出）
echo.
python main.py
pause
