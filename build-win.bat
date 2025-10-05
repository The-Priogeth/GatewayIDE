@echo off
setlocal enabledelayedexpansion

rem ===========================================================
rem  GatewayIDE - Windows Build Script (clean & organized)
rem ===========================================================

set ROOT=%~dp0
set SRC=%ROOT%src\GatewayIDE.App
set SLN=%ROOT%GatewayIDE.sln
set CSPROJ=%SRC%\GatewayIDE.App.csproj
set OUTDIR=%SRC%\bin\Release
set RUNTIME=win-x64

echo.
echo ===========================================================
echo  🚀  BUILD START: GatewayIDE (Release | %RUNTIME%)
echo ===========================================================
echo.

rem --- Prüfen auf .NET SDK ---
dotnet --version >nul 2>&1
if errorlevel 1 (
  echo [FEHLER] .NET SDK nicht gefunden. Bitte .NET 8 oder neuer installieren.
  exit /b 1
)

rem --- Alte Build-Artefakte löschen ---
if exist "%SRC%\obj" (
  echo [INFO] Lösche obj-Verzeichnis ...
  rmdir /s /q "%SRC%\obj"
)
if exist "%SRC%\bin" (
  echo [INFO] Lösche bin-Verzeichnis ...
  rmdir /s /q "%SRC%\bin"
)

rem --- Solution prüfen / anlegen ---
if not exist "%SLN%" (
  echo [INFO] Erzeuge Solution-Datei ...
  dotnet new sln -n GatewayIDE
)
dotnet sln "%SLN%" list | findstr /i "GatewayIDE.App" >nul
if errorlevel 1 (
  echo [INFO] Füge Projekt zur Solution hinzu ...
  dotnet sln "%SLN%" add "%CSPROJ%"
)

rem --- Restore & Publish ---
echo.
echo [INFO] Wiederherstellung von NuGet-Paketen ...
dotnet restore "%CSPROJ%"
if errorlevel 1 (
  echo [FEHLER] Restore fehlgeschlagen.
  exit /b 1
)

echo.
echo [INFO] Erstelle Release Build ...
dotnet publish "%CSPROJ%" -c Release -r %RUNTIME% --self-contained true ^
  -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true ^
  -o "%OUTDIR%"
if errorlevel 1 (
  echo [FEHLER] Build fehlgeschlagen.
  exit /b 1
)

echo.
echo ===========================================================
echo  ✅  Build abgeschlossen!
echo -----------------------------------------------------------
echo  Ausgabe: %OUTDIR%\GatewayIDE.App.exe
echo ===========================================================
echo.
pause
endlocal
