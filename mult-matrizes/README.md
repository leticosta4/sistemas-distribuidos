# mult-matrizes

Coordenador distribui celulas da multiplicacao para N processos trabalhadores via socket TCP (JSON + `\n`). Cada trabalhador recebe uma linha de A + uma coluna de B, calcula o produto escalar e devolve.

## Como funciona

- `sincrono/`: coordenador envia 1 tarefa e espera a resposta antes da proxima (round-robin).
- `assincrono/`: coordenador divide as tarefas e coleta as respostas conforme chegam (fila + delay aleatorio no server p/ embaralhar a ordem).

Os trabalhadores sao processos de verdade (`Server*.py`, um por porta). O cliente detecta sozinho quantos estao no ar.

## Como roda

Suba quantos workers quiser (um terminal por worker):

```bash
python3 sincrono/ServerSincrono.py 8001
python3 sincrono/ServerSincrono.py 8002
python3 sincrono/ServerSincrono.py 8003
```

Rode o cliente (ele escaneia 8001-8010 e usa todos que achar):

```bash
python3 sincrono/ClienteSincrono.py
```

Ou avise as portas direto:

```bash
python3 sincrono/ClienteSincrono.py --portas 8001 8002 8003
```

Assincrono e igual, trocando a pasta:

```bash
python3 assincrono/ServerAssincrono.py 8001
python3 assincrono/ServerAssincrono.py 8002
python3 assincrono/ClienteAssincrono.py
python3 assincrono/ClienteAssincrono.py --portas 8001 8002
```

## Visualizacao

Coordenador imprime cada celula `[i][j]` com o worker (porta) que calculou e a matriz final:

```
[COORDENADOR] Trabalhadores detectados: 3
[COORDENADOR] Celula [0][0] feita pelo trabalhador 0 (porta 8001) linha=[0, 1, 3] coluna=[10, 13, 16] = 61
...
[COORDENADOR] Matriz resultante:
[61, 65, 69]
[175, 188, 201]
[318, 342, 366]
```

No assincrono a ordem de chegada varia a cada execucao:

```
[COORDENADOR] Chegada 1/9: celula [0][1] feita pelo trabalhador 1 = 65
[COORDENADOR] Chegada 2/9: celula [0][0] feita pelo trabalhador 0 = 61
```
