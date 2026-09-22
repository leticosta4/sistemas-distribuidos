# Middleware — Multiplicação de Matrizes via rpyc

Abordagem com **middleware rpyc** (RPC). Cada trabalhador expõe um serviço `TrabalhadorMatriz` com o método remoto `produto_escalar(linha, coluna)`. O coordenador não monta mensagens nem gerencia conexões de baixo nível: ele apenas **chama o método remoto como se fosse local**.

## Preparando o ambiente (1x)

Esta é a única pasta que depende de uma biblioteca externa (`rpyc`), que já vem no `requirements.txt`.

```bash
# na pasta mult-matrizes/ (onde está o requirements.txt)
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Se o venv não for criado, o `python` do sistema não vai ter o `rpyc` instalado.

## Como rodar (sem passar nada)

Abra **4 terminais**: 3 para os trabalhadores e 1 para o coordenador, e rode de dentro desta pasta `middleware/`:

### Terminais 1, 2 e 3 — trabalhadores

Todos usam o **mesmo comando**:

```bash
python TrabalhadorMiddleware.py
```

Sem argumentos, cada trabalhador tenta `8001` e, se ocupada, sobe para a próxima porta livre (8002, 8003, ...):

| Terminal | Porta escolhida |
|---|---|
| 1 | `8001` |
| 2 | `8002` |
| 3 | `8003` |

### Terminal 4 — coordenador

```bash
python ClienteMiddleware.py
```

Sem argumentos, o cliente escaneia `localhost` de 8001 a 8100 e conecta-se via rpyc a **todos os trabalhadores ativos** encontrados.

> Opcionalmente dá para forçar porta explícita por trabalhador (`python TrabalhadorMiddleware.py 8001`) ou lista de portas no cliente (`python ClienteMiddleware.py --portas 8001 8002 8003`).

## Exemplo de saída

### Trabalhador 8002

```
[21:23:24.581] [TRABALHADOR 8002] RMI server rodando...
[21:23:27.415] [TRABALHADOR 8002] celula = 65 (demora 0.362s)
[21:23:29.502] [TRABALHADOR 8002] celula = 188 (demora 0.644s)
[21:23:31.131] [TRABALHADOR 8002] celula = 342 (demora 0.122s)
[21:23:31.971] [TRABALHADOR 8002] Encerrado pelo coordenador. Encerrou.
```

### Coordenador

```
[21:23:26.668] [COORDENADOR] Trabalhadores detectados: 3

[21:23:26.668] [COORDENADOR] Conectado ao trabalhador 0 em localhost:8001.
[21:23:26.668] [COORDENADOR] Conectado ao trabalhador 1 em localhost:8002.
[21:23:26.668] [COORDENADOR] Conectado ao trabalhador 2 em localhost:8003.

[21:23:26.668] [COORDENADOR] >>> ENVIANDO celula [0][0] ao trabalhador 0 (porta 8001) — BLOQUEADO até resposta...
[21:23:27.050] [COORDENADOR] <<< RECEBIDO celula [0][0] do trabalhador 0 (porta 8001) = 61 — continuando...
[21:23:27.050] [COORDENADOR] >>> ENVIANDO celula [0][1] ao trabalhador 1 (porta 8002) — BLOQUEADO até resposta...
[21:23:27.415] [COORDENADOR] <<< RECEBIDO celula [0][1] do trabalhador 1 (porta 8002) = 65 — continuando...
[21:23:27.415] [COORDENADOR] >>> ENVIANDO celula [0][2] ao trabalhador 2 (porta 8003) — BLOQUEADO até resposta...
[21:23:27.820] [COORDENADOR] <<< RECEBIDO celula [0][2] do trabalhador 2 (porta 8003) = 69 — continuando...
[21:23:27.820] [COORDENADOR] >>> ENVIANDO celula [1][0] ao trabalhador 0 (porta 8001) — BLOQUEADO até resposta...
[21:23:28.816] [COORDENADOR] <<< RECEBIDO celula [1][0] do trabalhador 0 (porta 8001) = 175 — continuando...
[21:23:28.816] [COORDENADOR] >>> ENVIANDO celula [1][1] ao trabalhador 1 (porta 8002) — BLOQUEADO até resposta...
[21:23:29.502] [COORDENADOR] <<< RECEBIDO celula [1][1] do trabalhador 1 (porta 8002) = 188 — continuando...
[21:23:29.502] [COORDENADOR] >>> ENVIANDO celula [1][2] ao trabalhador 2 (porta 8003) — BLOQUEADO até resposta...
[21:23:30.452] [COORDENADOR] <<< RECEBIDO celula [1][2] do trabalhador 2 (porta 8003) = 201 — continuando...
[21:23:30.452] [COORDENADOR] >>> ENVIANDO celula [2][0] ao trabalhador 0 (porta 8001) — BLOQUEADO até resposta...
[21:23:30.968] [COORDENADOR] <<< RECEBIDO celula [2][0] do trabalhador 0 (porta 8001) = 318 — continuando...
[21:23:30.968] [COORDENADOR] >>> ENVIANDO celula [2][1] ao trabalhador 1 (porta 8002) — BLOQUEADO até resposta...
[21:23:31.132] [COORDENADOR] <<< RECEBIDO celula [2][1] do trabalhador 1 (porta 8002) = 342 — continuando...
[21:23:31.132] [COORDENADOR] >>> ENVIANDO celula [2][2] ao trabalhador 2 (porta 8003) — BLOQUEADO até resposta...
[21:23:31.885] [COORDENADOR] <<< RECEBIDO celula [2][2] do trabalhador 2 (porta 8003) = 366 — continuando...

[21:23:31.929] [COORDENADOR] Conexao com trabalhador 0 encerrada.
[21:23:31.972] [COORDENADOR] Conexao com trabalhador 1 encerrada.
[21:23:32.014] [COORDENADOR] Conexao com trabalhador 2 encerrada.
[21:23:32.015] [COORDENADOR] Matriz resultante:
[61, 65, 69]
[175, 188, 201]
[318, 342, 366]

[21:23:32.015] [COORDENADOR] Tempo total: 5.366s (9 celulas, 3 trabalhadores)
[21:23:32.015] [COORDENADOR] Encerrou.
```

## Observações

- O acesso é chamada normal, de **forma sequencial** (o coordenador chama cada RPC de forma bloqueante), como na versão [síncrona](../sincrono/README.md). O que muda é a forma de comunicar, não o paralelismo.
- Ao final, o coordenador chama `encerrar()` em cada trabalhador — eles imprimem a confirmação mas continuam em execução esperando outro coordenador; use `Ctrl+C` para encerrá-los.
- A diferença fundamental para as partes anteriores é que aqui o coordenador **invoca métodos remotos** — o middleware (rpyc) esconde toda a rede (serialização, conexões, protocolo) de quem escreve a aplicação.