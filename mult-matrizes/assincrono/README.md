# Assíncrono — Multiplicação de Matrizes

Abordagem **assíncrona** com sockets TCP: o coordenador cria **uma thread por trabalhador**. Cada thread envia as tarefas daquele trabalhador e coleta as respostas sem esperar pelas demais. As células chegam em qualquer ordem.

## Preparando o ambiente (1x)

Esta pasta usa apenas a **biblioteca padrão do Python**, então o ambiente é opcional (mas segue o mesmo padrão das outras pastas).

```bash
# na pasta mult-matrizes/ (onde está o requirements.txt)
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Como rodar (sem passar nada)

Abra **4 terminais**: 3 para os trabalhadores e 1 para o coordenador, e rode de dentro desta pasta `assincrono/`:

### Terminais 1, 2 e 3 — trabalhadores

Todos usam o **mesmo comando**:

```bash
python ServerAssincrono.py
```

Sem argumentos, cada servidor tenta `8001` e, se ocupada, sobe para a próxima porta livre (8002, 8003, ...):

| Terminal | Porta escolhida |
|---|---|
| 1 | `8001` (a primeira roda sem disputa) |
| 2 | `8002` (8001 já ocupada) |
| 3 | `8003` (8001 e 8002 já ocupadas) |

### Terminal 4 — coordenador

```bash
python ClienteAssincrono.py
```

Sem argumentos, o cliente escaneia `localhost` de 8001 a 8010 e usa **todos os trabalhadores ativos** encontrados, distribui as 9 células entre eles (round-robin) e cada thread dispara as tarefas do seu trabalhador em paralelo.

> Opcionalmente dá para forçar porta explícita por trabalhador (`python ServerAssincrono.py 8001`) ou lista de portas no cliente (`python ClienteAssincrono.py --portas 8001 8002 8003`).

## Exemplo de saída

### Trabalhador 8002 (perceba a porta subindo)

```
[21:22:56.616] [TRABALHADOR] Porta 8001 ocupada, tentando proxima...
[21:22:56.616] [TRABALHADOR 8002] Aguardando coordenador em localhost:8002...
[21:22:58.683] [TRABALHADOR 8002] Celula [0][1] = 65 (tarefa 1)
[21:22:59.067] [TRABALHADOR 8002] Celula [1][1] = 188 (tarefa 2)
[21:22:59.974] [TRABALHADOR 8002] Celula [2][1] = 342 (tarefa 3)
[21:22:59.975] [TRABALHADOR 8002] Fim das tarefas. Encerrando conexao.
[21:22:59.975] [TRABALHADOR 8002] Conexao encerrada. 3 tarefas. Aguardando proximo coordenador...
```

### Coordenador

```
[21:22:58.152] [COORDENADOR] Trabalhadores detectados: 3

[21:22:58.152] [COORDENADOR] Trabalhador 0 (localhost:8001) recebe 3 tarefas.
[21:22:58.152] [COORDENADOR] Trabalhador 1 (localhost:8002) recebe 3 tarefas.
[21:22:58.152] [COORDENADOR] Trabalhador 2 (localhost:8003) recebe 3 tarefas.

[21:22:58.608] Chegada 1/9: celula [0][2] = 69 (trabalhador 2) | demora 0.455s
[21:22:58.630] Chegada 2/9: celula [0][0] = 61 (trabalhador 0) | demora 0.022s
[21:22:58.644] Chegada 3/9: celula [1][0] = 175 (trabalhador 0) | demora 0.014s
[21:22:58.683] Chegada 4/9: celula [0][1] = 65 (trabalhador 1) | demora 0.039s
[21:22:58.948] Chegada 5/9: celula [2][0] = 318 (trabalhador 0) | demora 0.264s
[21:22:59.067] Chegada 6/9: celula [1][1] = 188 (trabalhador 1) | demora 0.384s
[21:22:59.311] Chegada 7/9: celula [1][2] = 201 (trabalhador 2) | demora 0.244s
[21:22:59.385] Chegada 8/9: celula [2][2] = 366 (trabalhador 2) | demora 0.073s
[21:22:59.975] Chegada 9/9: celula [2][1] = 342 (trabalhador 1) | demora 0.663s

[21:22:59.975] [COORDENADOR] Tempo total: 1.823s (9 celulas, 3 trabalhadores)

[21:22:59.975] [COORDENADOR] Matriz resultante:
[61, 65, 69]
[175, 188, 201]
[318, 342, 366]
```

## Observações

- As células chegam **fora de ordem** — a ordem da chegada depende do delay aleatório de cada trabalhador.
- Como os trabalhadores processam em paralelo, o tempo total é bem menor que o da versão [síncrona](../sincrono/README.md) (neste exemplo ~1.8s contra ~4.5s).
- Encerre os trabalhadores com `Ctrl+C`.