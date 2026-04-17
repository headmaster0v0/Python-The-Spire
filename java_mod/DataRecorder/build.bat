@echo off
setlocal enabledelayedexpansion

set JAVA_HOME=C:\Program Files\Java\jdk-1.8
set JAVAC=%JAVA_HOME%\bin\javac.exe
set JAR_CMD=%JAVA_HOME%\bin\jar.exe

set STS_HOME=D:\steam\steamapps\common\SlayTheSpire
set WORKSHOP=D:\steam\steamapps\workshop\content\646570

set DESKTOP_JAR=%STS_HOME%\desktop-1.0.jar
set MTS_JAR=%WORKSHOP%\1605060445\ModTheSpire.jar
set BASEMOD_JAR=%WORKSHOP%\1605833019\BaseMod.jar
set STSLIB_JAR=%WORKSHOP%\1609158507\StSLib.jar

set SRC_DIR=src\main\java
set BUILD_DIR=build\classes
set OUTPUT_JAR=build\DataRecorder-0.1.0.jar

echo === Building DataRecorder Mod ===
echo.

echo Creating build directory...
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"

echo.
echo Compiling Java sources...

set CP=%DESKTOP_JAR%;%MTS_JAR%;%BASEMOD_JAR%;%STSLIB_JAR%

echo Finding Java files...
set JAVA_FILES=
for /r "%SRC_DIR%" %%f in (*.java) do (
    set "JAVA_FILES=!JAVA_FILES! "%%f""
)

echo Compiling...
"%JAVAC%" -encoding UTF-8 -source 1.8 -target 1.8 -cp "%CP%" -d "%BUILD_DIR%" %JAVA_FILES%

if errorlevel 1 (
    echo.
    echo === Compilation FAILED ===
    exit /b 1
)

echo Compilation successful

echo.
echo Creating JAR file with ModTheSpire.json...

if exist build\temp rmdir /s /q build\temp
mkdir build\temp
mkdir build\temp\META-INF

echo Manifest-Version: 1.0 > build\temp\META-INF\MANIFEST.MF

xcopy /y ModTheSpire.json build\temp\

xcopy /s /e /y "%BUILD_DIR%\*" build\temp\

cd build\temp
"%JAR_CMD%" cfm "..\DataRecorder-0.1.0.jar" META-INF\MANIFEST.MF .
cd ..\..

rmdir /s /q build\temp

if errorlevel 1 (
    echo.
    echo === JAR creation FAILED ===
    exit /b 1
)

echo.
echo === Build SUCCESS ===
echo Output: %OUTPUT_JAR%
echo.
echo To install, copy the JAR to your mods folder:
echo   copy "%OUTPUT_JAR%" "%STS_HOME%\mods\"
echo.

endlocal
