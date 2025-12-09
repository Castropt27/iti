# Projeto Flask + NFS + RAID + Docker + Prometheus + Grafana

## Arquitetura
- **Flask API**: Aplicação web com Swagger
- **NFS**: Partilha de ficheiros entre VMs
- **RAID1 (ZFS)**: Redundância de dados
- **Prometheus**: Monitorização de métricas
- **Grafana**: Visualização de dados
- **cAdvisor**: Monitorização de containers

## Estrutura do Projeto
```
projeto/
├── main.py              # Aplicação Flask
├── requirements.txt     # Dependências Python
├── Dockerfile          # Imagem Docker da aplicação
├── docker-compose.yml  # Orquestração de containers
├── prometheus.yml      # Configuração do Prometheus
└── README.md          # Este ficheiro
```

## Como Usar

### 1. Verificar se o NFS está montado
```bash
df -h | grep projetocliente
```

Se não estiver montado:
```bash
sudo mount 192.168.1.1:/nfsraid/projeto ~/projetocliente
```

### 2. Construir e iniciar os containers
```bash
cd ~/projeto
docker-compose up -d --build
```

### 3. Verificar se os containers estão a correr
```bash
docker-compose ps
```

### 4. Aceder aos serviços

- **Flask API + Swagger**: http://localhost:5000/apidocs
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (user: admin, password: admin)
- **cAdvisor**: http://localhost:8080

### 5. Testar a API

**GET - Listar ficheiros:**
```bash
curl http://localhost:5000/files
```

**POST - Adicionar ficheiro:**
```bash
curl -X POST http://localhost:5000/files \
  -H "Content-Type: application/json" \
  -d '"meu_ficheiro.txt"'
```

**Health check:**
```bash
curl http://localhost:5000/health
```

### 6. Ver logs
```bash
docker-compose logs -f flask-app
```

### 7. Parar os containers
```bash
docker-compose down
```

## Verificar Persistência

### No Cliente (onde corre o Docker):
```bash
cat ~/projetocliente/files.json
```

### No Servidor (onde está o RAID):
```bash
cat /nfsraid/projeto/files.json
```

Os ficheiros devem ser iguais porque a pasta está partilhada via NFS!

## Configurar Grafana

1. Acede a http://localhost:3000
2. Login: admin / admin
3. Adiciona fonte de dados:
   - Settings → Data Sources → Add data source
   - Escolhe **Prometheus**
   - URL: `http://prometheus:9090`
   - Clica em **Save & Test**

4. Importa dashboards prontos:
   - Create → Import
   - ID: `1860` (Node Exporter Full)
   - ID: `893` (Docker Dashboard)

## Troubleshooting

### Container não inicia:
```bash
docker-compose logs flask-app
```

### NFS não está montado:
```bash
sudo mount 192.168.1.1:/nfsraid/projeto ~/projetocliente
```

### Permissões de escrita:
```bash
sudo chown -R $USER:$USER ~/projetocliente
```

### Recriar containers:
```bash
docker-compose down
docker-compose up -d --build
```
