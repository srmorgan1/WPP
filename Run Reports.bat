@echo off

if "%USERNAME%"=="Sandra" (
    SET ANACONDA_PATH="C:\Users\sandra\AppData\Local\Continuum\anaconda3"
) ELSE (
    SET ANACONDA_PATH="C:\ProgramData\Anaconda3"
)
call %ANACONDA_PATH%\Scripts\activate.bat %ANACONDA_PATH%

python \\SBS\public\qube\iSite\AutoBOSShelleyAngeAndSandra\Programs_DO_NOT_CHANGE\RunReports.py

pause

@echo on
