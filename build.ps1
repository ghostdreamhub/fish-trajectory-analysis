$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name FishBehavior58 --add-data "assets;assets" --collect-all customtkinter --exclude-module matplotlib --exclude-module scipy --exclude-module openpyxl --exclude-module IPython --exclude-module pytest --exclude-module PyQt5 --exclude-module PySide6 app.py
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed' }
