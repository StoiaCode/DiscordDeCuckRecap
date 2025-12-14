@echo off
setlocal enabledelayedexpansion
title Discord Stats Analyzer
color 0B

:: Get the directory where the batch file is located (must be set early)
set SCRIPT_DIR=%~dp0

:: Configuration
set PYTHON_VERSION=3.11.9
set PYTHON_EMBED_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip
set PYTHON_DIR=%SCRIPT_DIR%python_portable
set PYTHON_EXE=%PYTHON_DIR%\python.exe
set GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py

:: Extract major.minor version for _pth file (e.g., 3.11.9 -> 311)
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do set PYTHON_PTH_VERSION=%%a%%b

:: Help option
if "%~1"=="--help" (
    echo Discord GDPR Data Analyzer - Command Line Options
    echo.
    echo Usage: start.bat [option]
    echo.
    echo Options:
    echo   --help               Show this help message
    echo   --debug-portable     Force using portable Python even if system Python exists
    echo   --reinstall-portable Delete and reinstall portable Python
    echo.
    echo The portable Python installation is located at:
    echo   %PYTHON_DIR%
    echo.
    exit /b 0
)

:: Debug mode - set to 1 to force portable Python even if system Python exists
:: Can also be enabled by passing --debug-portable as first argument
set DEBUG_PORTABLE=0
if "%~1"=="--debug-portable" (
    set DEBUG_PORTABLE=1
    echo [DEBUG] Forcing portable Python mode
    echo [DEBUG] Portable Python directory: %PYTHON_DIR%
    echo.
)
if "%~1"=="--reinstall-portable" (
    set DEBUG_PORTABLE=1
    echo [DEBUG] Reinstalling portable Python...
    echo [DEBUG] Removing: %PYTHON_DIR%
    if exist "%PYTHON_DIR%" (
        rmdir /s /q "%PYTHON_DIR%"
        echo [DEBUG] Portable Python directory removed
    ) else (
        echo [DEBUG] Portable Python directory does not exist
    )
    echo.
)

echo.
echo =====================================
echo   Discord GDPR Data Analyzer
echo =====================================
echo.

:: Check for portable Python first if debug mode is enabled
if %DEBUG_PORTABLE% EQU 1 (
    echo [DEBUG] Skipping system Python check
    goto :check_portable
)

:: Check if Python is already available in system PATH
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Python found in system PATH
    set PYTHON_CMD=python
    goto :check_scripts
)

:check_portable
if exist "%PYTHON_EXE%" (
    :: Verify portable Python actually works
    "%PYTHON_EXE%" --version >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo [OK] Portable Python found and working
        set PYTHON_CMD=%PYTHON_EXE%
        goto :check_scripts
    ) else (
        echo [!] Portable Python found but not working, will reinstall...
        rmdir /s /q "%PYTHON_DIR%"
    )
)

:: Python not found, offer to download portable version
echo.
echo [!] Python not found on your system
echo.
echo This script can download a portable Python installation
echo that doesn't require admin rights or affect your system.
echo.
echo Portable Python will be installed to: %PYTHON_DIR%
echo Size: ~40 MB
echo.
choice /C YN /M "Download and install portable Python"
if errorlevel 2 goto :no_python
if errorlevel 1 goto :install_python

:no_python
echo.
echo [X] Python is required to run this script.
echo.
echo You can:
echo   1. Install Python from https://www.python.org/downloads/
echo   2. Run this script again to use portable Python
echo.
pause
exit /b 1

:install_python
echo.
echo [*] Downloading portable Python %PYTHON_VERSION%...
echo.

:: Create directory
if not exist "%PYTHON_DIR%" mkdir "%PYTHON_DIR%"

:: Download Python embeddable package using PowerShell
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri '%PYTHON_EMBED_URL%' -OutFile '%PYTHON_DIR%\python.zip'}"

if %ERRORLEVEL% NEQ 0 (
    echo [X] Failed to download Python
    echo.
    pause
    exit /b 1
)

echo [*] Extracting Python...
powershell -Command "& {Expand-Archive -Path '%PYTHON_DIR%\python.zip' -DestinationPath '%PYTHON_DIR%' -Force}"

if %ERRORLEVEL% NEQ 0 (
    echo [X] Failed to extract Python
    echo.
    pause
    exit /b 1
)

:: Clean up zip file
del "%PYTHON_DIR%\python.zip"

:: Enable pip in embedded Python by uncommenting import site
echo [*] Configuring Python...
set PTH_FILE=%PYTHON_DIR%\python%PYTHON_PTH_VERSION%._pth
if not exist "%PTH_FILE%" (
    echo [X] Could not find %PTH_FILE%
    echo     Listing files in %PYTHON_DIR%:
    dir /b "%PYTHON_DIR%\*.pth" 2>nul || echo     No .pth files found
    echo.
    pause
    exit /b 1
)
powershell -Command "& {(Get-Content '%PTH_FILE%') -replace '#import site', 'import site' | Set-Content '%PTH_FILE%'}"

:: Download and install pip
echo [*] Installing pip...
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri '%GET_PIP_URL%' -OutFile '%PYTHON_DIR%\get-pip.py'}"

if not exist "%PYTHON_DIR%\get-pip.py" (
    echo [X] Failed to download get-pip.py
    echo.
    pause
    exit /b 1
)

"%PYTHON_EXE%" "%PYTHON_DIR%\get-pip.py" --no-warn-script-location
if %ERRORLEVEL% NEQ 0 (
    echo [X] Failed to install pip
    echo.
    pause
    exit /b 1
)
del "%PYTHON_DIR%\get-pip.py"

:: Verify pip works
"%PYTHON_EXE%" -m pip --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] Pip installation verification failed
    echo.
    pause
    exit /b 1
)

echo [OK] Portable Python installed successfully!
echo.
set PYTHON_CMD=%PYTHON_EXE%

:check_scripts
:: Show debug info about Python being used
if %DEBUG_PORTABLE% EQU 1 (
    echo [DEBUG] Using Python command: %PYTHON_CMD%
    for /f "tokens=*" %%v in ('"%PYTHON_CMD%" --version 2^>^&1') do echo [DEBUG] Python version: %%v
    echo.
)

echo [*] Checking for required scripts...
echo.

:: Find the analyzer script
set ANALYZER_SCRIPT=
for %%F in (discord_analyzer.py ExtractData_v*.py discord_analysis.py) do (
    if exist "%%F" (
        set ANALYZER_SCRIPT=%%F
        goto :found_analyzer
    )
)

:found_analyzer
if "%ANALYZER_SCRIPT%"=="" (
    echo [X] Analyzer script not found!
    echo.
    echo Please ensure one of these files exists:
    echo   - discord_analyzer.py
    echo   - ExtractData_v*.py
    echo.
    pause
    exit /b 1
)

echo [OK] Found analyzer: %ANALYZER_SCRIPT%

:: Find the website generator script
set WEBSITE_SCRIPT=
for %%F in (discord_stats_viewer.py CreateWebsite_v*.py stats_viewer.py) do (
    if exist "%%F" (
        set WEBSITE_SCRIPT=%%F
        goto :found_website
    )
)

:found_website
if "%WEBSITE_SCRIPT%"=="" (
    echo [X] Website generator script not found!
    echo.
    echo Please ensure one of these files exists:
    echo   - discord_stats_viewer.py
    echo   - CreateWebsite_v*.py
    echo.
    pause
    exit /b 1
)

echo [OK] Found website generator: %WEBSITE_SCRIPT%
echo.

:: Check for Messages directory
if not exist "Messages\" (
    echo [!] WARNING: Messages folder not found!
    echo.
    echo Please ensure your Discord GDPR data is extracted to a "Messages" folder
    echo in the same directory as this script.
    echo.
    choice /C YN /M "Continue anyway"
    if errorlevel 2 exit /b 1
    echo.
)

:: Prompt for Discord User ID
echo =====================================
echo   Your Discord User ID
echo =====================================
echo.
echo To get your Discord User ID:
echo   1. Open Discord
echo   2. Go to Settings (gear icon)
echo   3. Go to Advanced
echo   4. Enable "Developer Mode"
echo   5. Right-click your username anywhere
echo   6. Click "Copy User ID"
echo.
set /p USER_ID="Enter your Discord User ID: "

:: Validate that it's not empty and is numeric
if "%USER_ID%"=="" (
    echo.
    echo [X] User ID cannot be empty!
    echo.
    pause
    exit /b 1
)

:: Check if it's roughly the right format (17+ digits, numeric only)
echo %USER_ID%| powershell -Command "$input = $input.Trim(); if ($input -match '^\d{17,}$') { exit 0 } else { exit 1 }"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] WARNING: That doesn't look like a valid Discord User ID
    echo     Discord User IDs are typically 18-20 digit numbers
    echo.
    choice /C YN /M "Continue anyway"
    if errorlevel 2 exit /b 1
)

echo.
echo [OK] Using User ID: %USER_ID%
echo.

:: Run the analyzer
echo =====================================
echo   Step 1: Analyzing Discord Data
echo =====================================
echo.
echo [*] Running analyzer...
echo.

"%PYTHON_CMD%" "%ANALYZER_SCRIPT%" --user-id "%USER_ID%"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [X] Analyzer failed with error code %ERRORLEVEL%
    echo.
    pause
    exit /b 1
)

:: Check if database was created
if not exist "discord_analysis.db" (
    echo.
    echo [X] Database file not created. Analysis may have failed.
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Analysis complete!
echo.

:: Run the website generator
echo =====================================
echo   Step 2: Generating Stats Website
echo =====================================
echo.
echo [*] Creating website...
echo.

"%PYTHON_CMD%" "%WEBSITE_SCRIPT%" --user-id "%USER_ID%" --serve

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [X] Website generator failed with error code %ERRORLEVEL%
    echo.
    echo The database was created successfully. You can view it using:
    echo   %PYTHON_CMD% %ANALYZER_SCRIPT% --query
    echo.
    pause
    exit /b 1
)

echo.
echo =====================================
echo   Complete!
echo =====================================
echo.
echo Your stats website has been generated and should open in your browser.
echo If it doesn't open automatically, open: discord_stats.html
echo.
echo Press Ctrl+C to stop the web server when you're done viewing.
echo.
pause

endlocal