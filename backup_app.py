import os
import shutil
import logging
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
from threading import Thread
import time
import json
import sqlite3
from tkinter import messagebox
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import winreg as reg

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG_FILE = "backup_config.json"
DB_FILE = "backup_history.db"

# Funções de configuração
def carregar_configuracao():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def salvar_configuracao(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# Funções de histórico
def inicializar_banco():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            origem TEXT,
            destino TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def adicionar_entrada_historico(origem, destino, status):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO historico (data, origem, destino, status)
        VALUES (?, ?, ?, ?)
    ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), origem, destino, status))
    conn.commit()
    conn.close()

def obter_historico():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM historico ORDER BY data DESC')
    historico = cursor.fetchall()
    conn.close()
    return historico

def excluir_historico():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM historico')
    conn.commit()
    conn.close()

# Inicializar o banco de dados
inicializar_banco()

# Funções de backup
def calcular_tamanho_total(origem):
    total_size = 0
    for dirpath, _, filenames in os.walk(origem):
        for filename in filenames:
            try:
                total_size += os.path.getsize(os.path.join(dirpath, filename))
            except (FileNotFoundError, PermissionError) as e:
                logging.warning(f"Erro ao acessar '{filename}': {e}. Ignorando...")
    return total_size

def verificar_espaco_suficiente(origem, destino):
    total_size = calcular_tamanho_total(origem)
    free_space = shutil.disk_usage(destino).free
    logging.info(f"Tamanho total do backup: {total_size / (1024 * 1024):.2f} MB")
    logging.info(f"Espaço livre no destino: {free_space / (1024 * 1024):.2f} MB")
    if free_space < total_size:
        logging.error(f"Espaço insuficiente para o backup. Necessário: {total_size / (1024 * 1024):.2f} MB, disponível: {free_space / (1024 * 1024):.2f} MB.")
        return False
    return True

def remover_backups_antigos(destino, dias_retencao):
    limite_data = datetime.now() - timedelta(days=dias_retencao)
    for root, dirs, files in os.walk(destino, topdown=False):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            try:
                file_data = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_data < limite_data:
                    os.remove(file_path)
                    logging.info(f"Arquivo antigo removido: {file_path}")
            except Exception as e:
                logging.warning(f"Erro ao remover arquivo '{file_path}': {e}")
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                backup_data = datetime.fromtimestamp(os.path.getmtime(dir_path))
                if backup_data < limite_data:
                    shutil.rmtree(dir_path)
                    logging.info(f"Backup antigo removido: {dir_path}")
            except Exception as e:
                logging.warning(f"Erro ao remover diretório '{dir_path}': {e}")

def backup_incremental(origem, destino, progress_callback):
    total_items = sum(len(files) for _, _, files in os.walk(origem))
    if total_items == 0:
        progress_callback(100)
        return
    items_copiados = 0
    for dirpath, _, filenames in os.walk(origem):
        for filename in filenames:
            src_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(src_path, origem)
            dest_path = os.path.join(destino, rel_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            if not os.path.exists(dest_path) or os.path.getmtime(src_path) > os.path.getmtime(dest_path):
                copiar_item(src_path, dest_path)
                items_copiados += 1
                progresso = (items_copiados / total_items) * 100
                progress_callback(progresso)
    progress_callback(100)  # Garantir que a barra de progresso atinja 100%

def copiar_item(src_path, dest_path):
    try:
        shutil.copy2(src_path, dest_path)
        logging.info(f"Arquivo copiado: {src_path}")
    except FileNotFoundError as e:
        logging.warning(f"Arquivo não encontrado '{src_path}': {e}. Ignorando...")
    except PermissionError as e:
        logging.warning(f"Erro de permissão ao acessar '{src_path}': {e}. Ignorando...")
    except Exception as e:
        logging.error(f"Erro inesperado ao copiar '{src_path}': {e}")

def backup_diario(origem, destino, progress_callback, log_callback, historico_callback, dias_retencao):
    if not os.path.exists(origem):
        log_callback(f"Erro: O caminho de origem '{origem}' não foi encontrado.")
        adicionar_entrada_historico(origem, destino, "Erro: Caminho de origem não encontrado")
        return

    data_atual = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = os.path.join(destino, f"backup_{data_atual}")
    os.makedirs(backup_path, exist_ok=True)

    # Verifica se há espaço suficiente e backups antigos para remover
    if not verificar_espaco_suficiente(origem, backup_path):
        log_callback("Espaço insuficiente para o backup.")
        adicionar_entrada_historico(origem, destino, "Erro: Espaço insuficiente")
        return
    remover_backups_antigos(destino, dias_retencao)

    log_callback(f"Iniciando o backup incremental diário para a data: {data_atual}")
    backup_incremental(origem, backup_path, progress_callback)
    log_callback("Backup diário concluído com sucesso!")
    historico_callback(f"Backup realizado em {data_atual} para {backup_path}")
    adicionar_entrada_historico(origem, destino, "Sucesso")

def agendar_backup(horario, funcao_backup, *args):
    def verificar_horario():
        while True:
            agora = datetime.now().strftime("%H:%M")
            if agora == horario:
                funcao_backup(*args)
                time.sleep(60)  # Evita múltiplas execuções no mesmo minuto
            time.sleep(1)

    agendamento_thread = Thread(target=verificar_horario)
    agendamento_thread.daemon = True
    agendamento_thread.start()

def backup_completo(origem, destino, progress_callback):
    total_items = sum(len(files) for _, _, files in os.walk(origem))
    if total_items == 0:
        progress_callback(100)
        return
    items_copiados = 0
    for dirpath, _, filenames in os.walk(origem):
        for filename in filenames:
            src_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(src_path, origem)
            dest_path = os.path.join(destino, rel_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            copiar_item(src_path, dest_path)
            items_copiados += 1
            progresso = (items_copiados / total_items) * 100
            progress_callback(progresso)
    progress_callback(100)  # Garantir que a barra de progresso atinja 100%

def agendar_backup_completo(intervalo_dias, funcao_backup, *args):
    def verificar_intervalo():
        while True:
            ultimo_backup = datetime.now() - timedelta(days=intervalo_dias)
            if datetime.now() >= ultimo_backup + timedelta(days=intervalo_dias):
                funcao_backup(*args)
                time.sleep(60 * 60 * 24)  # Verifica uma vez por dia
            time.sleep(60 * 60)  # Verifica uma vez por hora

    agendamento_thread = Thread(target=verificar_intervalo)
    agendamento_thread.daemon = True
    agendamento_thread.start()

# Funções para rodar em segundo plano
def create_image():
    # Generate an image and draw a pattern
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), (255, 255, 255))
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        (width // 2, 0, width, height // 2),
        fill=(255, 0, 0))
    dc.rectangle(
        (0, height // 2, width // 2, height),
        fill=(0, 255, 0))
    dc.rectangle(
        (width // 2, height // 2, width, height),
        fill=(0, 0, 255))
    dc.rectangle(
        (0, 0, width // 2, height // 2),
        fill=(255, 255, 0))

    return image

def quit_program(icon, item):
    icon.stop()
    os._exit(0)

def show_window(icon, item):
    global app
    app.root.deiconify()

def hide_window(app):
    app.root.withdraw()
    image = create_image()
    menu = (item('Show', show_window), item('Quit', quit_program))
    icon = pystray.Icon("name", image, "APP_Backup", menu)
    icon.run()

def add_to_startup():
    pth = os.path.dirname(os.path.realpath(__file__))
    s_name = "APP_Backup"
    address = os.path.join(pth, "backup_app.exe")
    key = reg.HKEY_CURRENT_USER
    key_value = "Software\\Microsoft\\Windows\\CurrentVersion\\Run"

    open = reg.OpenKey(key, key_value, 0, reg.KEY_ALL_ACCESS)
    reg.SetValueEx(open, s_name, 0, reg.REG_SZ, address)
    reg.CloseKey(open)

# Interface gráfica com melhorias
class BackupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Backup Empresarial")
        self.root.geometry("1024x768")
        
        # Configurações e variáveis
        self.config = carregar_configuracao()
        self.origem_var = tk.StringVar(value=self.config.get("origem", ""))
        self.destino_var = tk.StringVar(value=self.config.get("destino", ""))
        self.horario_var = tk.StringVar(value=self.config.get("horario", "02:00"))
        self.dias_retencao_var = tk.IntVar(value=self.config.get("dias_retencao", 7))
        self.progress_var = tk.DoubleVar()

        # Paleta de cores Material Design
        self.cores = {
            'primary': "#1976D2",      # Azul primário
            'secondary': "#140f14",    # Cinza escuro
            'background': "#ede25c",   # AMARELO SUAVE
            'surface': "#FFA500",      # LARANJA
            'error': "#D32F2F",       # Vermelho
            'success': "#388E3C",      # Verde
            'warning': "#F57C00",      # Laranja
            'text_primary': "#212121", # Texto principal
            'text_secondary': "#140f14" # Texto secundário
        }
        
        # Configuração do tema
        self.root.configure(bg=self.cores['background'])
        self.configurar_estilos()
        
        # Container principal com padding
        main_container = ttk.Frame(root, padding="20", style="Main.TFrame")
        main_container.pack(fill="both", expand=True)
        
        # Cabeçalho
        self.criar_cabecalho(main_container)
        
        # Container para duas colunas
        content_frame = ttk.Frame(main_container)
        content_frame.pack(fill="both", expand=True, pady=20)
        
        # Coluna esquerda - Configurações
        left_frame = self.criar_coluna_esquerda(content_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # Coluna direita - Progresso e Logs
        right_frame = self.criar_coluna_direita(content_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self.agendar_backup_automatico()  # Agendar backup automático ao iniciar a aplicação
        add_to_startup()  # Adicionar ao registro para iniciar com o sistema operacional

    def iniciar(self):
        self.root.mainloop()

    def configurar_estilos(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Estilos personalizados
        style.configure("Header.TLabel",
                       font=("Segoe UI", 24, "bold"),
                       foreground=self.cores['primary'])
        
        style.configure("Main.TFrame",
                       background=self.cores['background'])
        
        style.configure("Card.TLabelframe",
                       background=self.cores['surface'])
        
        style.configure("Card.TLabelframe.Label",
                       font=("Segoe UI", 12, "bold"),
                       foreground=self.cores['primary'])
        
        style.configure("Action.TButton",
                       font=("Segoe UI", 11, "bold"),
                       padding=10,
                       background="#007BFF",  # Azul
                       foreground="#FFFFFF",  # Branco
                       relief="flat")
        
        style.map("Action.TButton",
                  background=[("active", "#FF0000")],  # Vermelho quando ativo
                  foreground=[("active", "#FFFFFF")])  # Branco quando ativo
        
        style.configure("Secondary.TButton",
                       font=("Segoe UI", 10),
                       padding=8,
                       background="#6C757D",  # Cinza
                       foreground="#FFFFFF",  # Branco
                       relief="flat")
        
        style.map("Secondary.TButton",
                  background=[("active", "#FF0000")],  # Vermelho quando ativo
                  foreground=[("active", "#FFFFFF")])  # Branco quando ativo
        
        style.configure("Select.TButton",
                       font=("Segoe UI", 10),
                       padding=8,
                       background="#28A745",  # Verde
                       foreground="#FFFFFF",  # Branco
                       relief="flat")
        
        style.map("Select.TButton",
                  background=[("active", "#218838")],  # Verde escuro quando ativo
                  foreground=[("active", "#FFFFFF")])  # Branco quando ativo
        
        style.configure("Config.TLabel",
                       font=("Segoe UI", 10, "bold"),
                       background=self.cores['surface'],
                       foreground=self.cores['text_primary'])
        
        # Estilo para a barra de progresso
        style.configure("TProgressbar",
                       thickness=20,
                       troughcolor=self.cores['background'],
                       background=self.cores['primary'])

    def criar_cabecalho(self, parent):
        header = ttk.Frame(parent, style="Main.TFrame")
        header.pack(fill="x", pady=(0, 20))
        
        ttk.Label(header,
                 text="Sistema de Backup",
                 style="Header.TLabel").pack(anchor="w")
        
        ttk.Label(header,
                 text="Desenvolvido por Otaide Ferreira",
                 font=("Segoe UI", 10),
                 foreground=self.cores['text_secondary']).pack(anchor="w")

    def criar_coluna_esquerda(self, parent):
        left_frame = ttk.Frame(parent)
        
        # Frame de configuração de diretórios
        dirs_frame = ttk.LabelFrame(left_frame,
                                  text="Configuração de Diretórios",
                                  style="Card.TLabelframe",
                                  padding="3")  # Reduzir o padding
        dirs_frame.pack(fill="x", pady=(0, 10))  # Reduzir o espaço vertical
        
        # Grid para os campos de diretório
        for i, (label, var) in enumerate([
            ("Pasta de Origem:", self.origem_var),
            ("Pasta de Destino:", self.destino_var)
        ]):
            ttk.Label(dirs_frame, text=label).grid(row=i, column=0, sticky="w", pady=5)
            entry = ttk.Entry(dirs_frame, textvariable=var, width=80)  # Aumentar o tamanho da Entry
            entry.grid(row=i, column=1, padx=5, pady=5)
        
        # Botão para alterar pastas
        ttk.Button(dirs_frame, text="Alterar Pastas/horários", command=self.abrir_configuracoes, style="Action.TButton").grid(row=2, columnspan=3, pady=10)
        
        # Frame de configurações de backup
        config_frame = ttk.LabelFrame(left_frame,
                                    text="Configurações de Backup",
                                    style="Card.TLabelframe",
                                    padding="15")
        config_frame.pack(fill="x", pady=(0, 15))
        
        # Grid para configurações
        ttk.Label(config_frame, text="Horário do Backup:").grid(row=0, column=0, sticky="w", pady=5)
        horario_label = ttk.Label(config_frame, textvariable=self.horario_var, style="Config.TLabel")
        horario_label.grid(row=0, column=1, pady=5)
        
        ttk.Label(config_frame, text="Dias de Retenção:").grid(row=1, column=0, sticky="w", pady=5)
        retencao_label = ttk.Label(config_frame, textvariable=self.dias_retencao_var, style="Config.TLabel")
        retencao_label.grid(row=1, column=1, pady=5)
        
        # Frame de ações
        actions_frame = ttk.LabelFrame(left_frame,
                                     text="Ações",
                                     style="Card.TLabelframe",
                                     padding="15")
        actions_frame.pack(fill="x")
        
        for text, command in [
            ("Iniciar Backup Incremental", self.iniciar_backup),
            ("Iniciar Backup Completo", self.iniciar_backup_completo),
            ("Histórico de Backups", self.abrir_historico)
        ]:
            btn = ttk.Button(actions_frame,
                           text=text,
                           command=command,
                           style="Action.TButton")
            btn.pack(fill="x", pady=1)  # Reduzir o espaço vertical entre os botões
        
        return left_frame

    def criar_coluna_direita(self, parent):
        right_frame = ttk.Frame(parent)
        
        # Frame de progresso
        progress_frame = ttk.LabelFrame(right_frame,
                                      text="Status do Backup",
                                      style="Card.TLabelframe",
                                      padding="15")
        progress_frame.pack(fill="x", pady=(0, 15))
        
        self.progress_bar = ttk.Progressbar(progress_frame,
                                          variable=self.progress_var,
                                          mode="determinate",
                                          length=300,
                                          style="TProgressbar")
        self.progress_bar.pack(fill="x", pady=(10, 5))
        
        self.progress_label = ttk.Label(progress_frame,
                                      text="Progresso: 0%",
                                      font=("Segoe UI", 10))
        self.progress_label.pack()
        
        # Frame de logs
        log_frame = ttk.LabelFrame(right_frame,
                                 text="Logs do Sistema",
                                 style="Card.TLabelframe",
                                 padding="15")
        log_frame.pack(fill="both", expand=True)
        
        self.log_area = scrolledtext.ScrolledText(
            log_frame,
            font=("Consolas", 10),
            height=15,
            wrap=tk.WORD
        )
        self.log_area.pack(fill="both", expand=True, pady=(1, 10))
        
        # Botão para limpar logs
        ttk.Button(log_frame, text="Limpar Logs", command=self.limpar_logs, style="Action.TButton").pack(pady=1)
        
        return right_frame

    def limpar_logs(self):
        self.log_area.configure(state="normal")
        self.log_area.delete(1.0, tk.END)
        self.log_area.configure(state="disabled")

    def agendar_backup_automatico(self):
        agendar_backup(self.horario_var.get(), backup_diario, self.origem_var.get(), self.destino_var.get(), self.atualizar_progresso, self.atualizar_log, self.atualizar_hist, self.dias_retencao_var.get())

    def agendar_backup_completo_automatico(self, intervalo_dias):
        agendar_backup_completo(intervalo_dias, backup_completo, self.origem_var.get(), self.destino_var.get(), self.atualizar_progresso)

    def selecionar_pasta_origem(self, config_window):
        origem = filedialog.askdirectory(title="Selecione a pasta de origem")
        if origem:
            self.origem_var.set(origem)
        config_window.lift()

    def selecionar_pasta_destino(self, config_window):
        destino = filedialog.askdirectory(title="Selecione a pasta de destino")
        if destino:
            self.destino_var.set(destino)
        config_window.lift()

    def atualizar_log(self, texto):
        self.log_area.configure(state="normal")
        self.log_area.insert(tk.END, texto + "\n")
        self.log_area.yview(tk.END)
        self.log_area.configure(state="disabled")
        messagebox.showinfo("Log de Backup", texto)

    def atualizar_hist(self, texto):
        # Remover a referência ao atributo 'hist_area'
        pass

    def atualizar_progresso(self, progresso):
        self.progress_var.set(progresso)
        self.progress_label.config(text=f"Progresso: {progresso:.2f}%")
        self.root.update_idletasks()

    def iniciar_backup(self):
        self.progress_var.set(0)
        self.progress_label.config(text="Progresso: 0%")
        self.progress_bar.config(style="TProgressbar")
        self.root.update_idletasks()

        origem = self.origem_var.get()
        destino = self.destino_var.get()
        dias_retencao = self.dias_retencao_var.get()

        def progress_callback(progresso):
            self.atualizar_progresso(progresso)

        def log_callback(texto):
            self.atualizar_log(texto)

        def historico_callback(texto):
            self.atualizar_hist(texto)

        # Iniciar backup manualmente
        backup_thread = Thread(target=backup_diario, args=(origem, destino, progress_callback, log_callback, historico_callback, dias_retencao))
        backup_thread.start()

    def iniciar_backup_completo(self):
        self.progress_var.set(0)
        self.progress_label.config(text="Progresso: 0%")
        self.progress_bar.config(style="TProgressbar")
        self.root.update_idletasks()

        origem = self.origem_var.get()
        destino = self.destino_var.get()

        def progress_callback(progresso):
            self.atualizar_progresso(progresso)

        def log_callback(texto):
            self.atualizar_log(texto)

        # Iniciar backup completo manualmente
        backup_thread = Thread(target=backup_completo, args=(origem, destino, progress_callback))
        backup_thread.start()
        log_callback("Backup completo iniciado com sucesso!")  # Adicionar callback de log aqui
        adicionar_entrada_historico(origem, destino, "Sucesso")  # Adicionar entrada no histórico

    def abrir_configuracoes(self):
        config_window = tk.Toplevel(self.root)
        config_window.title("Configurações")
        config_window.geometry("1000x460")
        config_window.config(bg=self.cores['background'])

        # Estilo moderno
        style = ttk.Style()
        style.configure("TLabel", font=("Segoe UI", 12), background=self.cores['background'], foreground=self.cores['text_primary'])
        style.configure("TEntry", font=("Segoe UI", 12))
        style.configure("TButton", font=("Segoe UI", 12))

        frame = ttk.Frame(config_window, padding="20 20 20 20", style="TFrame")
        frame.pack(fill="both", expand=True)

        # Frame de configuração de diretórios
        dirs_frame = ttk.LabelFrame(frame,
                                    text="Configuração de Diretórios",
                                    style="Card.TLabelframe",
                                    padding="15")
        dirs_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(dirs_frame, text="Pasta de Origem:").grid(row=0, column=0, sticky="w", pady=5)
        origem_entry = ttk.Entry(dirs_frame, textvariable=self.origem_var, width=80)  # Aumentar o tamanho da Entry
        origem_entry.grid(row=0, column=1, pady=5)
        ttk.Button(dirs_frame, text="Selecionar Pasta", command=lambda: self.selecionar_pasta_origem(config_window), style="Select.TButton").grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(dirs_frame, text="Pasta de Destino:").grid(row=1, column=0, sticky="w", pady=5)
        destino_entry = ttk.Entry(dirs_frame, textvariable=self.destino_var, width=80)  # Aumentar o tamanho da Entry
        destino_entry.grid(row=1, column=1, pady=5)
        ttk.Button(dirs_frame, text="Selecionar Pasta", command=lambda: self.selecionar_pasta_destino(config_window), style="Select.TButton").grid(row=1, column=2, padx=5, pady=5)

        # Frame de configurações de backup
        backup_frame = ttk.LabelFrame(frame,
                                      text="Configurações de Backup",
                                      style="Card.TLabelframe",
                                      padding="15")
        backup_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(backup_frame, text="Horário do Backup Automático (HH:MM):").grid(row=0, column=0, sticky="w", pady=5)
        horario_entry = ttk.Entry(backup_frame, textvariable=self.horario_var, width=10)
        horario_entry.grid(row=0, column=1, pady=5)

        ttk.Label(backup_frame, text="Dias de Retenção de Backups:").grid(row=1, column=0, sticky="w", pady=5)
        retencao_entry = ttk.Entry(backup_frame, textvariable=self.dias_retencao_var, width=5)
        retencao_entry.grid(row=1, column=1, pady=5)

        # Botão para salvar configurações
        ttk.Button(frame, text="Salvar Configurações", command=self.salvar_configuracoes, style="Action.TButton").pack(pady=20)

    def abrir_historico(self):
        history_window = tk.Toplevel(self.root)
        history_window.title("Histórico de Backups")
        history_window.geometry("1000x600")
        history_window.config(bg=self.cores['background'])

        # Estilo moderno
        style = ttk.Style()
        style.configure("TLabel", font=("Segoe UI", 12), background=self.cores['background'], foreground=self.cores['text_primary'])
        style.configure("TButton", font=("Segoe UI", 12, "bold"))

        frame = ttk.Frame(history_window, padding="20 20 20 20", style="TFrame")
        frame.pack(fill="both", expand=True)

        columns = ("data", "origem", "destino", "status")
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        tree.heading("data", text="Data")
        tree.heading("origem", text="Origem")
        tree.heading("destino", text="Destino")
        tree.heading("status", text="Status")

        for row in obter_historico():
            tree.insert("", tk.END, values=row[1:])

        tree.pack(fill="both", expand=True)

        # Ajustar as colunas ao conteúdo
        tree.column("data", width=100, anchor=tk.W)
        tree.column("origem", width=400, anchor=tk.W)
        tree.column("destino", width=400, anchor=tk.W)
        tree.column("status", width=50, anchor=tk.W)

        ttk.Button(frame, text="Excluir Registros", command=self.excluir_historico).pack(pady=10)

    def excluir_historico(self):
        excluir_historico()
        self.atualizar_log("Histórico de backups excluído com sucesso!")

    def salvar_configuracoes(self):
        config = {
            "origem": self.origem_var.get(),
            "destino": self.destino_var.get(),
            "horario": self.horario_var.get(),
            "dias_retencao": self.dias_retencao_var.get()
        }
        salvar_configuracao(config)
        self.atualizar_log("Configurações salvas com sucesso!")
        self.agendar_backup_automatico()  # Atualizar agendamento após salvar configurações

# Executando a aplicação
if __name__ == "__main__":
    root = tk.Tk()
    global app
    app = BackupApp(root)  # Define app instance here
    app.iniciar()  # Iniciar a aplicação
