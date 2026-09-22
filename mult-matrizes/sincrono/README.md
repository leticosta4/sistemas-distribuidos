# Síncrono — Multiplicação de Matrizes

Abordagem **síncrona** com sockets TCP: o coordenador envia a célula `[i][j]`, **bloqueia aguardando a resposta**, e só então envia a próxima. Cada tarefa vai para um trabalhador diferente em round-robin.

## Preparando o ambiente (1x)

Esta pasta usa apenas a **biblioteca padrão do Python**, então o ambiente é opcional (mas segue o mesmo padrão das outras pastas).

```bash
# na pasta mult-matrizes/ (onde está o requirements.txt)
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Como rodar (sem passar nada)

Abra **4 terminais**: 3 para os trabalhadores e 1 para o coordenador, e rode de dentro desta pasta `sincrono/`:

### Terminais 1, 2 e 3 — trabalhadores

Todos usam o **mesmo comando**:

```bash
python ServerSincrono.py
```

Sem argumentos, cada servidor tenta `8001` e, se ocupada, sobe para a próxima porta livre (8002, 8003, ...):

| Terminal | Porta escolhida |
|---|---|
| 1 | `8001` (a primeira roda sem disputa) |
| 2 | `8002` (8001 já ocupada) |
| 3 | `8003` (8001 e 8002 já ocupadas) |

### Terminal 4 — coordenador

```bash
python ClienteSincrono.py
```

Sem argumentos, o cliente escaneia `localhost` de 8001 a 8010 e usa **todos os trabalhadores ativos** encontrados. Ele avisa quantos detectou e distribui as 9 células entre eles.

> Opcionalmente dá para forçar porta explícita por trabalhador (`python ServerSincrono.py 8001`) ou lista de portas no cliente (`python ClienteSincrono.py --portas 8001 8002 8003`).

## Exemplo de saída

### Trabalhador 8002 (perceba a porta subindo)

```
[21:22:26.839] [TRABALHADOR] Porta 8001 ocupada, tentando proxima...
[21:22:26.840] [TRABALHADOR 8002] Aguardando coordenador em localhost:8002...
[21:22:29.009] [TRABALHADOR 8002] Celula [0][1] = 65 (tarefa 1)
[21:22:30.362] [TRABALHADOR 8002] Celula [1][1] = 188 (tarefa 2)
[21:22:31.741] [TRABALHADOR 8002] Celula [2][1] = 342 (tarefa 3)
[21:22:32.392] [TRABALHADOR 8002] Fim das tarefas. Encerrando conexao.
[21:22:32.393] [TRABALHADOR 8002] Conexao encerrada. 3 tarefas. Aguardando proximo coordenador...
```

### Coordenador

```
[21:22:27.909] [COORDENADOR] Trabalhadores detectados: 3

[21:22:27.909] [COORDENADOR] Conectado ao trabalhador 0 em localhost:8001.
[21:22:27.910] [COORDENADOR] Conectado ao trabalhador 1 em localhost:8002.
[21:22:27.910] [COORDENADOR] Conectado ao trabalhador 2 em localhost:8003.

[21:22:27.910] [COORDENADOR] >>> ENVIANDO celula [0][0] ao trabalhador 0 (porta 8001) — BLOQUEADO até resposta...
[21:22:28.009] [COORDENADOR] <<< RECEBIDO celula [0][0] do trabalhador 0 (porta 8001) = 61 — continuando...
[21:22:28.009] [COORDENADOR] >>> ENVIANDO celula [0][1] ao trabalhador 1 (porta 8002) — BLOQUEADO até resposta...
[21:22:29.010] [COORDENADOR] <<< RECEBIDO celula [0][1] do trabalhador 1 (porta 8002) = 65 — continuando...
[21:22:29.010] [COORDENADOR] >>> ENVIANDO celula [0][2] ao trabalhador 2 (porta 8003) — BLOQUEADO até resposta...
[21:22:29.291] [COORDENADOR] <<< RECEBIDO celula [0][2] do trabalhador 2 (porta 8003) = 69 — continuando...
[21:22:29.291] [COORDENADOR] >>> ENVIANDO celula [1][0] ao trabalhador 0 (porta 8001) — BLOQUEADO até resposta...
[21:22:30.063] [COORDENADOR] <<< RECEBIDO celula [1][0] do trabalhador 0 (porta 8001) = 175 — continuando...
[21:22:30.063] [COORDENADOR] >>> ENVIANDO celula [1][1] ao trabalhador 1 (porta 8002) — BLOQUEADO até resposta...
[21:22:30.362] [COORDENADOR] <<< RECEBIDO celula [1][1] do trabalhador 1 (porta 8002) = 188 — continuando...
[21:22:30.363] [COORDENADOR] >>> ENVIANDO celula [1][2] ao trabalhador 2 (porta 8003) — BLOQUEADO até resposta...
[21:22:31.025] [COORDENADOR] <<< RECEBIDO celula [1][2] do trabalhador 2 (porta 8003) = 201 — continuando...
[21:22:31.025] [COORDENADOR] >>> ENVIANDO celula [2][0] ao trabalhador 0 (porta 8001) — BLOQUEADO até resposta...
[21:22:31.068] [COORDENADOR] <<< RECEBIDO celula [2][0] do trabalhador 0 (porta 8001) = 318 — continuando...
[21:22:31.068] [COORDENADOR] >>> ENVIANDO celula [2][1] ao trabalhador 1 (porta 8002) — BLOQUEADO até resposta...
[21:22:31.742] [COORDENADOR] <<< RECEBIDO celula [2][1] do trabalhador 1 (porta 8002) = 342 — continuando...
[21:22:31.742] [COORDENADOR] >>> ENVIANDO celula [2][2] ao trabalhador 2 (porta 8003) — BLOQUEADO até resposta...
[21:22:32.392] [COORDENADOR] <<< RECEBIDO celula [2][2] do trabalhador 2 (porta 8003) = 366 — continuando...

[21:22:32.392] [COORDENADOR] Matriz resultante:
[61, 65, 69]
[175, 188, 201]
[318, 342, 366]

[21:22:32.392] [COORDENADOR] Tempo total: 4.496s (9 celulas, 3 trabalhadores)
```

## Observações

- É uma execução **serializada**: cada célula espera a anterior. Os tempos variam por causa do `random.uniform(0, 1)` de delay em cada trabalhador.
- Encerre os trabalhadores com `Ctrl+C`.