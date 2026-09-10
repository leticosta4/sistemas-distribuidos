# sistemas-distribuidos

Mini projetos da disciplina de Sistemas Distribuidos (UNEB).

## Requisitos

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Pyro5](https://pyro5.readthedocs.io/en/latest/index.html)

## Configuração

```bash
# Clonar o repo
git clone https://github.com/leticosta4/sistemas-distribuidos.git
cd sistemas-distribuidos

# Instalar dependências de todos os projetos
uv sync
```

## Projetos

### server-client-basico

Comunicação básica entre cliente e servidor usando sockets Python (TCP/UDP).

```bash
# TCP
uv run python server-client-basico/TCP/TCPServer.py
uv run python server-client-basico/TCP/TCPClient.py

# UDP
uv run python server-client-basico/UDP/UDPServer.py
uv run python server-client-basico/UDP/UDPClient.py
```

### middleware

Exercícios de middleware com RPC usando Pyro5.

```bash
# Servidor (em um terminal)
uv run -m Pyro5.nameserver

uv run python middleware/JVServer.py


# Cliente (em outro terminal)
uv run python middleware/JVClient.py
```

## Adicionando um novo projeto

1. Crie uma pasta para o projeto
2. Crie um `pyproject.toml` dentro dela:

```toml
[project]
name = "nome-do-projeto"
version = "0.1.0"
description = "Descrição"
requires-python = ">=3.10"
dependencies = []
```

3. Adicione a pasta ao workspace em `pyproject.toml` (raiz):

```toml
[tool.uv.workspace]
members = ["server-client-basico", "middleware", "nome-do-projeto"]
```

4. Rode `uv sync` para instalar as dependências
