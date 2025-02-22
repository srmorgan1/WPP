@echo off

set TRUE=
IF "%USERNAME%"=="Sandra" SET TRUE=1
IF "%USERNAME%"=="Angela" SET TRUE=1
IF DEFINED TRUE (
    SET ANACONDA_PATH="C:\Users\%USERNAME%\AppData\Local\Continuum\anaconda3"
) ELSE (
    SET ANACONDA_PATH="C:\ProgramData\Anaconda3"
)

call %ANACONDA_PATH%\Scripts\activate.bat %ANACONDA_PATH%

python \\SBS\public\qube\iSite\AutoBOSShelleyAngeAndSandra\Programs_DO_NOT_CHANGE\UpdateDatabase.py

pause

@echo on
