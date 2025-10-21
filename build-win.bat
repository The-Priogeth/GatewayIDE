@echo off
setlocal EnableExtensions EnableDelayedExpansion

title GatewayIDE Build Script

rem === Pfade (ohne "src") ===
set "ROOT=%~dp0"
set "APP=%ROOT%GatewayIDE.App"
set "SLN=%ROOT%GatewayIDE.sln"
set "CSPROJ=%APP%\GatewayIDE.App.csproj"

rem === Build-Parameter ===
set "RUNTIME=win-x64"
set "OUTDIR=%APP%\bin\Release"
set "OUTEXE=%OUTDIR%\GatewayIDE.App.exe"
set "ERR=0"

echo ============================================
echo   PRECHECKS
echo ============================================

rem --- 0) .NET SDK vorhanden? ---
dotnet --version >nul 2>&1 || (
  echo [ABORT] .NET SDK nicht gefunden. Bitte .NET 8+ installieren.
  set ERR=1
  goto :ABORT
)

rem --- 1) Docker erreichbar? ---
docker info >NUL 2>&1 || (
  echo [ABORT] Docker ist nicht erreichbar. Bitte Docker Desktop starten.
  pause
  exit /b 1
)

rem --- 2) Laufender Container bereinigen ---
set "CONTAINER_ID="
for /f "usebackq delims=" %%i in (`docker inspect -f "{{.Id}}" gateway-container 2^>NUL`) do set "CONTAINER_ID=%%i"

if not defined CONTAINER_ID (
  echo [OK] Kein Container vorhanden
  goto :AFTER_CONTAINER_CHECK
)

echo [INFO] Container 'gateway-container' gefunden (ID %CONTAINER_ID%)
echo [ACTION] Entferne Container automatisch ...
docker rm -f gateway-container >NUL 2>&1
if errorlevel 1 (
  echo [FEHLER] Container konnte nicht entfernt werden
  echo Bitte manuell mit: docker rm -f gateway-container
  pause
  exit /b 2
)
echo [OK] Container erfolgreich entfernt

:AFTER_CONTAINER_CHECK

echo ============================================
echo   CLEAN
echo ============================================
if exist "%APP%\obj" (
  echo [INFO] Loesche obj ...
  rmdir /s /q "%APP%\obj"
)
if exist "%APP%\bin" (
  echo [INFO] Loesche bin ...
  rmdir /s /q "%APP%\bin"
)

echo ============================================
echo   RESTORE + PUBLISH
echo ============================================

if not exist "%SLN%" (
  echo [INFO] Erzeuge Solution-Datei ...
  dotnet new sln -n GatewayIDE || goto :ABORT
)

dotnet sln "%SLN%" list | findstr /i "GatewayIDE.App" >nul
if errorlevel 1 (
  echo [INFO] Fuege Projekt zur Solution hinzu ...
  dotnet sln "%SLN%" add "%CSPROJ%" || goto :ABORT
)

dotnet restore "%CSPROJ%" || goto :ABORT

rem SingleFile, self-contained, Zielordner = %OUTDIR%
dotnet publish "%CSPROJ%" -c Release -r %RUNTIME% --self-contained true ^
  -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true ^
  -o "%OUTDIR%" || goto :ABORT

echo ============================================
echo   BUILD ERFOLGREICH
echo   Ausgabe: "%OUTEXE%"
echo ============================================

rem === Nach erfolgreichem Build: EXE starten ===
if exist "%OUTEXE%" (
  echo [RUN] Starte GatewayIDE ...
  pushd "%OUTDIR%"
  "GatewayIDE.App.exe"
  popd
  echo.
  echo [INFO] GatewayIDE wurde beendet. Druecke ENTER, um dieses Fenster zu schliessen...
  pause >nul
  goto :EOF
) else (
  echo [WARN] Konnte EXE nicht finden: "%OUTEXE%"
  goto :END
)

:ABORT
echo ============================================
echo   BUILD ABGEBROCHEN (ERR=%ERR%)
echo ============================================
echo [HINWEIS] Druecke ENTER, um das Fenster zu schliessen...
pause >nul
goto :EOF

:END
echo [HINWEIS] Druecke ENTER, um das Fenster zu schliessen...
pause >nul
endlocal
