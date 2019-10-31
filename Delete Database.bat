@echo off

if "%USERNAME%"=="Sandra" (
    SET ANACONDA_PATH="C:\Users\sandra\AppData\Local\Continuum\anaconda3"
) ELSE (
    SET ANACONDA_PATH="C:\ProgramData\Anaconda3"
)
call %ANACONDA_PATH%\Scripts\activate.bat %ANACONDA_PATH%

SET WPP_ROOT=\\SBS\public\qube\iSite\AutoBOSShelleyAngeAndSandra

set TODAY=%date:~-4,4%%date:~-7,2%%date:~-10,2%

IF EXIST %WPP_ROOT%\Database\WPP_DB.db (
    IF NOT EXIST %WPP_ROOT%\Database\Previous\WPP_DB_%TODAY%.db (
        echo Backing up Database
        copy %WPP_ROOT%\Database\WPP_DB.db %WPP_ROOT%\Database\Previous\WPP_DB_%TODAY%.db
    )

    echo Deleting Database
    del %WPP_ROOT%\Database\WPP_DB.db
)

pause

@echo on
