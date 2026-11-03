@echo off
REM Abre o sistema de estoque no navegador. Feche esta janela para encerrar.
cd /d "%~dp0"
python -m streamlit run app.py
pause
