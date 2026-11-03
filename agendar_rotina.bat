@echo off
REM Cria uma tarefa no Agendador do Windows que roda a rotina diaria todo dia as 18:00.
REM Para remover depois: schtasks /Delete /TN "Rotina Estoque" /F

REM Descobre o caminho real do python.exe (o Agendador nao usa o PATH do terminal)
for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)"') do set PYTHON_EXE=%%i

if "%PYTHON_EXE%"=="" (
    echo Python nao encontrado no PATH.
    pause
    exit /b 1
)

schtasks /Create /TN "Rotina Estoque" /SC DAILY /ST 18:00 /F ^
  /TR "\"%PYTHON_EXE%\" \"%~dp0main.py\" --rotina"

if %ERRORLEVEL%==0 (
    echo Tarefa "Rotina Estoque" criada: roda todo dia as 18:00 usando %PYTHON_EXE%
) else (
    echo Nao foi possivel criar a tarefa.
)
pause
