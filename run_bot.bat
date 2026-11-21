@echo off
title Khamsat Telegram Alert Bot
chcp 65001 > nul
echo ========================================================
echo Starting Khamsat Telegram Alert Bot...
echo ========================================================
cd /d "%~dp0"
python bot.py
pause
