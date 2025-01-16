# Sistema de Backup local

Este projeto é um sistema de backup local desenvolvido em Python. Ele permite a configuração e execução de backups incrementais e completos de diretórios especificados pelo usuário. O sistema também inclui uma interface gráfica moderna e intuitiva, além de funcionalidades para agendamento automático de backups e gerenciamento de histórico.

## Funcionalidades

- **Backup Incremental**: Realiza backups apenas dos arquivos que foram modificados desde o último backup.
- **Backup Completo**: Realiza um backup completo de todos os arquivos do diretório de origem.
- **Agendamento Automático**: Permite agendar backups automáticos em horários específicos.
- **Gerenciamento de Histórico**: Mantém um histórico dos backups realizados, permitindo a visualização e exclusão de registros antigos.
- **Interface Gráfica**: Interface moderna e intuitiva desenvolvida com Tkinter.
- **Notificações e Logs**: Exibe notificações e logs detalhados das operações de backup.

## Configuração

As configurações do sistema são armazenadas no arquivo `backup_config.json`. Este arquivo contém os seguintes parâmetros:

- `origem`: Caminho do diretório de origem para o backup.
- `destino`: Caminho do diretório de destino para o backup.
- `horario`: Horário para agendamento automático do backup (formato HH:MM).
- `dias_retencao`: Número de dias para retenção dos backups antigos.

## Como Executar

1. Certifique-se de ter o Python instalado em seu sistema.
2. Instale as dependências necessárias listadas no arquivo `requirements.txt`.
3. Execute o script `backup_app.py` para iniciar a aplicação.

```bash
python backup_app.py
```

## Autor

Desenvolvido por Otaide Ferreira.