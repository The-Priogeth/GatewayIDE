@echo off
setlocal enabledelayedexpansion
pushd "%~dp0"

REM ========= Konfiguration =========
set "SLN=GatewayIDE.sln"
set "CSPROJ=src\GatewayIDE.App\GatewayIDE.App.csproj"
set "RUNTIME=win-x64"

REM Publish-Ziel in bin\win-x64
set "OUTDIR=%~dp0bin\win-x64"
set "EXE=%OUTDIR%\GatewayIDE.App.exe"

REM Link im Root
set "SHORTCUT=%~dp0GatewayIDE.lnk"
REM =================================

echo.
echo ==================================================
echo   GatewayIDE Installer / Builder (Windows, .NET)
echo ==================================================
echo   Solution:    %SLN%
echo   Projekt:     %CSPROJ%
echo   Runtime:     %RUNTIME%
echo   Ausgabedatei:%EXE%
echo   Shortcut:    %SHORTCUT%
echo --------------------------------------------------

REM 0) .NET SDK?
dotnet --version >nul 2>&1 || (echo [FEHLER] .NET SDK fehlt.& goto :wait)

REM 1) Solution
if not exist "%SLN%" (
  echo [INFO] Erzeuge Solution: %SLN%
  dotnet new sln -n GatewayIDE || goto :wait
) else ( echo [OK] Solution existiert: %SLN% )

REM 2) Projekt in Solution?
echo [CHECK] Pruefe Projekt-Eintrag in Solution ...
dotnet sln "%SLN%" list | findstr /i /c:"GatewayIDE.App" >nul || (
  echo [INFO] Fuege Projekt hinzu ...
  dotnet sln "%SLN%" add "%CSPROJ%" || goto :wait
)
echo [OK] Projekt ist eingetragen.

REM 3) Restore + Clean + Cache löschen
echo [INFO] dotnet restore ...
dotnet restore "%CSPROJ%" || goto :wait

echo [INFO] dotnet clean ...
dotnet clean "%CSPROJ%" || goto :wait

echo [INFO] Loesche bin/obj (hart) ...
if exist "src\GatewayIDE.App\bin" rmdir /s /q "src\GatewayIDE.App\bin"
if exist "src\GatewayIDE.App\obj" rmdir /s /q "src\GatewayIDE.App\obj"

REM 4) Zielordner sicherstellen
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

REM 5) Publish (Release, SingleFile, self-contained) -> bin\win-x64
echo [INFO] Build + Publish (Release, %RUNTIME%) ...
dotnet publish "%CSPROJ%" -c Release -r %RUNTIME% --self-contained true ^
  -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true ^
  -o "%OUTDIR%"
if errorlevel 1 (
  echo [FEHLER] dotnet publish fehlgeschlagen.
  goto :wait
)

REM 6) Shortcut im Root erstellen/überschreiben
echo [INFO] Erzeuge/aktualisiere Shortcut im Root ...
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%');" ^
  "$s.TargetPath='%EXE%';$s.WorkingDirectory='%~dp0';$s.WindowStyle=1;$s.IconLocation='%EXE%,0';$s.Save()" >nul

REM Optional: alte Root-EXE aufräumen (falls vorher mal reinpublisht)
REM if exist "%~dp0GatewayIDE.App.exe" del /q "%~dp0GatewayIDE.App.exe"

echo.
echo ==========================================
echo  Build fertig: "%EXE%"
echo  Shortcut:     "%SHORTCUT%"
echo  (Root bleibt clean; Artefakte liegen unter .\bin\win-x64)
echo ==========================================

:wait
echo.
set /p _="Druecke ENTER zum Schliessen ... "
popd
endlocal
exit /b
