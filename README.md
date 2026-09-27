# sistemas-distribuidos

Mini projetos da disciplina de Sistemas Distribuidos (UNEB).

## Requisitos

- Python 3.10 ou superior
- [Pyro5](https://pyro5.readthedocs.io/en/latest/index.html) e `rpyc` (instalados via `requirements.txt`)

## Configuração

```bash
# Clonar o repo
git clone https://github.com/leticosta4/sistemas-distribuidos.git
cd sistemas-distribuidos

# Criar o ambiente e instalar as dependências de todos os projetos
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

O mesmo `.venv` da raiz serve para todos os projetos abaixo. Só `server-client-basico/` e as partes
síncrona/assíncrona de `mult-matrizes/` rodam sem nenhuma dependência externa, mas usar o ambiente
comum evita erro de `ModuleNotFoundError`.

## Projetos

### server-client-basico

Comunicação básica entre cliente e servidor usando sockets Python (TCP/UDP).

```bash
# TCP
python server-client-basico/TCP/TCPServer.py
python server-client-basico/TCP/TCPClient.py

# UDP
python server-client-basico/UDP/UDPServer.py
python server-client-basico/UDP/UDPClient.py
```

### middleware

Exercícios de middleware com RPC usando Pyro5.

```bash
# Servidor (em um terminal)
python -m Pyro5.nameserver

python middleware/JVServer.py


# Cliente (em outro terminal)
python middleware/JVClient.py
```

### mult-matrizes

Multiplicação de matrizes distribuída no padrão mestre/escravo, em três versões: sockets síncronos,
sockets assíncronos (thread por trabalhador) e RPC com `rpyc`. O relatório completo está em
[mult-matrizes/RELATORIO.md](mult-matrizes/RELATORIO.md).

Cada versão abre 4 terminais: 3 trabalhadores e 1 coordenador. Os trabalhadores sobem sozinhos na
primeira porta livre (8001, 8002, ...) e o coordenador usa todos os que encontrar.

```bash
# Versão síncrona (cada comando em um terminal)
python mult-matrizes/sincrono/ServerSincrono.py
python mult-matrizes/sincrono/ClienteSincrono.py

# Versão assíncrona
python mult-matrizes/assincrono/ServerAssincrono.py
python mult-matrizes/assincrono/ClienteAssincrono.py

# Versão com middleware (rpyc)
python mult-matrizes/middleware/TrabalhadorMiddleware.py
python mult-matrizes/middleware/ClienteMiddleware.py
```

Detalhes de execução e exemplos de saída em [síncrono](mult-matrizes/sincrono/README.md),
[assíncrono](mult-matrizes/assincrono/README.md) e [middleware](mult-matrizes/middleware/README.md).


### PubSub 

Como rodar:
```bash
python -m Pyro5.nameserver
python pubsub/intermediario.py
python pubsub/subscriber.py #digite id e topicos de interesse para acompanhar
python pubsub/publisher.py #digite id e topico a ser publicado com uma msg
```

## Adicionando um novo projeto

1. Crie uma pasta para o projeto
2. Escreva os scripts (Python puro, sem necessidade de instalar o repositório como pacote)
3. Se precisar de biblioteca externa, adicione em `requirements.txt` na raiz e rode
   `pip install -r requirements.txt`
4. Documente no `README.md` da pasta como rodar, e registre o projeto na lista acima
