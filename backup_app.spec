# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['backup_app.py'],  # Script principal da aplicação
    pathex=[r'C:/Users/55859/Desktop/My_codes/Meus projetos/APP_Backup/CXE'],  # Caminho onde o código está localizado
    binaries=[
        (r"C:\Users\55859\AppData\Local\Programs\Python\Python313\DLLs\_tkinter.pyd", '.'),  # Caminho para _tkinter.pyd
        (r"C:\Users\55859\AppData\Local\Programs\Python\Python313\DLLs\tcl86t.dll", '.'),    # Caminho para tcl86t.dll
        (r"C:\Users\55859\AppData\Local\Programs\Python\Python313\DLLs\tk86t.dll", '.')      # Caminho para tk86t.dll
    ],
    datas=[
        (r'backup_config.json', '.'),  # Inclui o arquivo de configuração no mesmo diretório
        (r'backup_history.db', '.')    # Inclui o arquivo de banco de dados no mesmo diretório
    ],
    hiddenimports=[
        'pystray',  # Inclui pystray
        'PIL',      # Inclui PIL (Python Imaging Library)
        'winreg',   # Inclui winreg para interação com o registro do Windows
        'tkinter',  # Inclui tkinter para interfaces gráficas
        'sqlite3',  # Inclui sqlite3 para banco de dados
        'shutil',   # Inclui shutil para manipulação de arquivos
        'logging',  # Inclui logging para gerenciamento de logs
        'json',     # Inclui json para manipulação de JSON
        'time',     # Inclui time para operações com tempo
        'datetime', # Inclui datetime para datas e horários
        'os',       # Inclui os para interações com o sistema operacional
        'sys',      # Inclui sys para manipulação do interpretador Python
        'subprocess' # Inclui subprocess para executar comandos externos
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],  # Nenhum módulo será explicitamente excluído
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,  # Sem criptografia personalizada
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # Excluir binários para serem adicionados na etapa de coleta
    name='backup_app',  # Nome do executável gerado
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # Não remover símbolos de depuração
    upx=True,     # Habilitar compressão com UPX
    upx_exclude=[],  # Sem exclusões específicas para UPX
    runtime_tmpdir=None,
    console=False,  # Define se o aplicativo será GUI (False) ou Console (True)
    icon=r'C:\Users\55859\Desktop\BIBLIOTECA LOCAL\BACKUP-CODE\1.CÓDIGO FONTE\logo.ico'  # Caminho para o ícone do aplicativo
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],  # Sem exclusões específicas para UPX
    name='backup_app',  # Nome da pasta gerada pelo PyInstaller
)
