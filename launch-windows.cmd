@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 -c "from PyQt6 import QtWidgets" >nul 2>nul
    if errorlevel 1 (
        echo PyQt6 is missing. Installing with Python pip...
        py -3 -m pip install PyQt6
        if errorlevel 1 goto :failed
    )
    py -3 -m studio_native
    goto :end
)
python -c "from PyQt6 import QtWidgets" >nul 2>nul
if errorlevel 1 (
    echo Install Python 3 and then run: python -m pip install PyQt6
    goto :failed
)
python -m studio_native
goto :end
:failed
echo Launch failed. Check the Python 3 / PyQt6 installation.
pause
exit /b 1
:end
endlocal
