@echo off
title Stop Khamsat Bot
chcp 65001 > nul
echo جاري إيقاف بوت خمسات...
taskkill /f /im python.exe /fi "WINDOWTITLE eq Khamsat*" 2>nul
wmic process where "commandline like '%%khamsat_bot%%bot.py%%'" call terminate 2>nul
echo تم إيقاف البوت بنجاح.
pause
