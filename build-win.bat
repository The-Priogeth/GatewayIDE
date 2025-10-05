@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ============================================
rem  GatewayIDE - Windows Build (Release | win-x64)
rem  Hält das Fenster IMMER offen (ENTER nötig)
rem ============================================

set "ROOT=%~dp0"
set "SRC=%ROOT%src\GatewayIDE.App"
set "SLN=%ROOT%GatewayIDE.sln"
set "CSPROJ=%SRC%\GatewayIDE.App.csproj"
set "OUTDIR=%SRC%\bin\Release"
set "RUNTIME=win-x64"
set "ERR=0"

echo.
echo ============================================
echo   BUILD START: GatewayIDE (Release ^| %RUNTIME%)
echo ============================================
echo.

rem --- .NET SDK vorhanden? ---
dotnet --version >nul 2>&1 || (
  echo [FEHLER] .NET SDK nicht gefunden. Bitte .NET 8 oder neuer installieren.
  set ERR=1
  goto :END
)

rem --- Clean obj/bin (projektlokal) ---
if exist "%SRC%\obj" (
  echo [INFO] Loesche obj ...
  rmdir /s /q "%SRC%\obj" || set ERR=1
)
if exist "%SRC%\bin" (
  echo [INFO] Loesche bin ...
  rmdir /s /q "%SRC%\bin" || set ERR=1
)
if not "%ERR%"=="0" goto :END

rem --- Solution anlegen/fixen ---
if not exist "%SLN%" (
  echo [INFO] Erzeuge Solution-Datei ...
  dotnet new sln -n GatewayIDE || (set ERR=1 & goto :END)
)

dotnet sln "%SLN%" list | findstr /i "GatewayIDE.App" >nul
if errorlevel 1 (
  echo [INFO] Fuege Projekt zur Solution hinzu ...
  dotnet sln "%SLN%" add "%CSPROJ%" || (set ERR=1 & goto :END)
)

echo.
echo [INFO] Restore NuGet ...
dotnet restore "%CSPROJ%" || (set ERR=1 & goto :END)

echo.
echo [INFO] Publish (Release, SingleFile, self-contained) ...
dotnet publish "%CSPROJ%" -c Release -r %RUNTIME% --self-contained true ^
  -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true ^
  -o "%OUTDIR%" || (set ERR=1 & goto :END)

echo.
echo ============================================
echo   ✅ BUILD ERFOLGREICH
echo   Ausgabe: "%OUTDIR%\GatewayIDE.App.exe"
echo ============================================
goto :END

:END
echo.
if "%ERR%"=="0" (
  echo [HINWEIS] Druecke ENTER, um das Fenster zu schliessen...
) else (
  echo ============================================
  echo   ❌ BUILD FEHLGESCHLAGEN
  echo   (siehe Meldungen oben)
)
pause >nul
endlocal
