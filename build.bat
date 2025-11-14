@echo off
TITLE Nuitka Packaging for DB Sync Tool

REM Clean Old Cache...
echo Cleaning up old build directories...
rmdir /s /q dist
rmdir /s /q db_sync_tool.build
rmdir /s /q db_sync_tool.onefile-build

echo.
echo Starting Nuitka packaging process...
echo This may take a few minutes, especially the first time.

REM Nuitka Package...
python -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-disable-console ^
    --enable-plugin=tk-inter ^
    --output-dir=dist ^
    --output-filename=MySQL_DB_Sync.exe ^
    --windows-icon-from-ico=app_icon.ico ^
    db_sync_tool.py

REM Check Build Result...
if errorlevel 1 (
    echo.
    echo =================================
    echo  An error occurred during packaging!
    echo  Please review the messages above.
    echo =================================
) else (
    echo.
    echo =================================
    echo  Packaging completed successfully!
    echo  Your file is located in the 'dist' folder:
    echo  dist\MySQL_DB_Sync.exe
    echo =================================
)

echo.
pause