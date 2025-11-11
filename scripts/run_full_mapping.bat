@echo off
cd /d C:\Projetos
echo Iniciando mapeamento completo E-AGENDAS...
echo.
echo ATENCAO: Este processo pode levar varias horas!
echo Progresso sera salvo em: logs\map_eagendas_full.log
echo.

C:\Projetos\.venv\Scripts\python.exe scripts\map_eagendas_full.py > logs\map_eagendas_full.log 2>&1

echo.
echo Mapeamento concluido! Verifique: logs\map_eagendas_full.log
pause
