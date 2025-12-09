# Usa uma imagem base Python
FROM python:3.11-slim

# Define o diretório de trabalho
WORKDIR /app

# Copia os ficheiros do projeto
COPY requirements.txt .
COPY main.py .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Expõe a porta da aplicação
EXPOSE 8000

# Variável de ambiente para o caminho dos dados
ENV FILES_STORAGE_PATH=/data/files.json

# Comando para executar a aplicação
CMD ["python", "main.py"]