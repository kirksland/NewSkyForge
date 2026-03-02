@echo off
setlocal

REM ====== Houdini install path ======
set "HFS=C:\Program Files\Side Effects Software\Houdini 21.0.440"

REM ====== Python include/lib from Houdini ======
set "PYINC=%HFS%\toolkit\include\python3.11"
set "PYLIB=%HFS%\python311\libs"

REM ====== Project paths ======
set "MODDIR=%~dp0"
set "SRC=%MODDIR%src\skyforge_core.cpp"
set "BUILDDIR=%MODDIR%build"
set "OUTPYD=%MODDIR%..\..\python\skyforge\skyforge_core.pyd"

if not exist "%BUILDDIR%" mkdir "%BUILDDIR%"

pushd "%BUILDDIR%"

cl /nologo /LD /MD /O2 /EHsc ^
  /I "%PYINC%" ^
  "%SRC%" ^
  /link /nologo /LIBPATH:"%PYLIB%" python311.lib ^
  /OUT:"%BUILDDIR%\skyforge_core.pyd"

if errorlevel 1 (
  echo BUILD FAILED
  popd
  pause
  exit /b 1
)

copy /Y "%BUILDDIR%\skyforge_core.pyd" "%OUTPYD%"
if errorlevel 1 (
  echo COPY FAILED: close Houdini (it locks the .pyd), then re-run.
  popd
  pause
  exit /b 2
)

popd
echo OK: %OUTPYD%
pause