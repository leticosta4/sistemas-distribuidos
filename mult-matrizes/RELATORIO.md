# Relatório Técnico — Multiplicação de Matrizes Distribuída

**Disciplina:** Sistemas Distribuídos
**Projeto:** `mult-matrizes`
**Estrutura da pasta**

```
mult-matrizes/
├── requirements.txt
├── sincrono/        ServerSincrono.py, ClienteSincrono.py
├── assincrono/      ServerAssincrono.py, ClienteAssincrono.py
└── middleware/      TrabalhadorMiddleware.py, ClienteMiddleware.py
```

## 1. Arquitetura implementada (mestre/escravo)

O projeto segue o padrão **mestre/escravo** (master/slave): existe **um mestre** (o coordenador) e **N escravos** (os trabalhadores).

- **Mestre** (`ClienteSincrono.py`, `ClienteAssincrono.py`, `ClienteMiddleware.py`): gera todas as tarefas, distribui as células entre os trabalhadores, coleta os resultados parciais e monta a matriz resultado.
- **Escravo** (`ServerSincrono.py`, `ServerAssincrono.py`, `TrabalhadorMiddleware.py`): recebe a tarefa, calcula o produto escalar de uma linha de A por uma coluna de B e devolve a célula `[i][j]` com o resultado.

Cada célula do resultado é independente das outras, o que permite distribuir as 9 tarefas (numa multiplicação 3x3) entre vários trabalhadores:

```
tarefa(i, j) = soma_k( A[i][k] * B[k][j] )
```

A comunicação é feita em **`localhost`**, com cada trabalhador em uma porta TCP a partir de **8001**. Para simplificar a execução, nenhuma porta precisa ser informada:

- o **trabalhador** sobe na primeira porta livre (tenta 8001, depois 8002, ...);
- o **coordenador** escaneia `localhost` (8001–8010 nos sockets, 8001–8100 no middleware) e usa todos os trabalhadores ativos que encontrar.

Esse mecanismo de descoberta automática elimina configuração manual e torna o experimento reproduzível em qualquer máquina.

## 2. Comunicação síncrona

A versão síncrona (`sincrono/`) usa **sockets TCP** com mensagens **JSON** terminadas em `\n` como protocolo.

No cliente, para cada célula:

1. monta a linha de A e a coluna de B;
2. escolhe o trabalhador em **round-robin** (`tarefa % n_trabalhadores`);
3. envia `{i, j, linha, coluna}` e **fica bloqueado** aguardando o `{i, j, resultado}` de volta;
4. só então parte para a célula seguinte.

O trabalhador, por sua vez, escuta em loop: recebe uma linha+coluna, calcula o produto escalar e responde. Entre uma célula e outra ele aplica um atraso aleatório (`random.uniform(0, 1)`) para simular variação de carga.

**Característica principal:** o coordenador só processa uma célula por vez. Como cada resposta leva em média ~0,5s (atraso aleatório), o tempo total com 3 trabalhadores fica em torno de **4,5s** para 9 células — os trabalhadores ficam ociosos a maior parte do tempo. É a abordagem **mais simples de implementar e debugar**, porém a mais lenta.

## 3. Comunicação assíncrona

A versão assíncrona (`assincrono/`) mantém a mesma base de sockets + JSON, mas muda o comportamento do coordenador: agora ele cria **uma thread por trabalhador**.

Cada thread:

1. conecta-se ao seu trabalhador;
2. envia **todas** as células destinadas a ele (também em round-robin na distribuição);
3. coleta as respostas e coloca os resultados em uma **fila compartilhada** (`queue.Queue`).

O coordenador apenas consome a fila — a **ordem de chegada varia** conforme o atraso de cada trabalhador. No mesmo cenário 3x3 com 3 trabalhadores, todas as células chegam em ~1,8s, contra ~4,5s do síncrono, pois os três trabalham **de fato em paralelo**.

**Trade-offs:** resposta fora de ordem (o coordenador não sabe de antemão qual célula virá) e uso de threads no cliente para gerenciar a concorrência. A cobrança desse gerenciamento fica no cliente; o trabalhador continua idêntico ao da versão síncrona.

## 4. Middleware e chamadas remotas

A Parte 2 (`middleware/`) substitui a comunicação manual por **RPC via rpyc**.

O trabalhador (`TrabalhadorMiddleware.py`) define um serviço derivado de `rpyc.Service` com os métodos públicos remotos (`exposed_*`):

- `exposed_produto_escalar(linha, coluna)` — calcula a célula;
- `exposed_tamanho()` — usado na descoberta para confirmar que é um worker rpyc;
- `exposed_encerrar()` — sinaliza encerramento ao final.

Cada trabalhador roda um `rpyc.utils.server.ThreadedServer` na porta escolhida.

O coordenador (`ClienteMiddleware.py`) não monta nem serializa mensagens: ele conecta (`rpyc.connect`) e **chama o método como se fosse local**:

```python
resultado = conexoes[w].root.produto_escalar(linha, coluna)
```

O rpyc cuida da serialização, do transporte na rede e do retorno. A **possível limitação** é que a execução deste exemplo é sequencial (a chamada é bloqueante, igual à versão síncrona) — o ganho da Parte 2 não está em performance, e sim em **abstração**: o coordenador esquece que existe rede no meio.

## 5. Exemplos de execução (matrizes 3x3)

Todas as versões usam as mesmas matrizes:

```
A = [0 1 3]        B = [10 11 12]
    [4 3 6]            [13 14 15]
    [7 8 9]            [16 17 18]

A x B =
[61, 65, 69]
[175, 188, 201]
[318, 342, 366]
```

### 5.1 Síncrono — trabalhador 8002 (porta subindo sozinha)

```
[21:22:26.839] [TRABALHADOR] Porta 8001 ocupada, tentando proxima...
[21:22:26.840] [TRABALHADOR 8002] Aguardando coordenador em localhost:8002...
[21:22:29.009] [TRABALHADOR 8002] Celula [0][1] = 65 (tarefa 1)
[21:22:30.362] [TRABALHADOR 8002] Celula [1][1] = 188 (tarefa 2)
[21:22:31.741] [TRABALHADOR 8002] Celula [2][1] = 342 (tarefa 3)
[21:22:32.392] [TRABALHADOR 8002] Fim das tarefas. Encerrando conexao.
[21:22:32.393] [TRABALHADOR 8002] Conexao encerrada. 3 tarefas. Aguardando proximo coordenador...
```

### 5.2 Síncrono — coordenador

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

### 5.3 Assíncrono — coordenador (resultados fora de ordem)

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

### 5.4 Middleware — trabalhador 8002

```
[21:23:24.581] [TRABALHADOR 8002] RMI server rodando...
[21:23:27.415] [TRABALHADOR 8002] celula = 65 (demora 0.362s)
[21:23:29.502] [TRABALHADOR 8002] celula = 188 (demora 0.644s)
[21:23:31.131] [TRABALHADOR 8002] celula = 342 (demora 0.122s)
[21:23:31.971] [TRABALHADOR 8002] Encerrado pelo coordenador. Encerrou.
```

### 5.5 Middleware — coordenador

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

## 6. Comparação crítica: Parte 1 vs Parte 2

| Critério | Parte 1 — sockets (síncrono/assíncrono) | Parte 2 — middleware rpyc |
|---|---|---|
| Protocolo | Manual: JSON + `\n` como delimitador | Transparente, o rpyc serializa/transporta |
| Conhecimento de rede no coordenador | Necessário (abrir/ler conexão, montar/enviar/receber mensagens) | Dispensável (chama método remoto) |
| Descoberta de trabalhadores | Scan de porta TCP | Scan de porta + chamada `tamanho()` |
| Paralelismo alcançado | Síncrono: serial; assíncrono: threads no cliente | Sequencial (chamada bloqueante) |
| Massa de código no cliente | Maior (funções de envio/recebimento) | Menor (só a chamada de método) |
| Facilidade de manutenção | Menor — qualquer mudança de formato exige mudar os dois lados | Maior — a interface é o método exposto |

**Pontos que merecem destaque:**

1. **O middleware não é mais rápido por si só.** A versão rpyc deste projeto executa de forma bloqueante, então o tempo final é comparável ao síncrono (~5,4s neste teste, sujeito ao atraso aleatório). O **único** ganho real de tempo veio do **assíncrono** da Parte 1 (threads), que levou ~1,8s para a mesma carga.
2. **Níveis de abstração diferentes, mesma semântica.** Na Parte 1 o coordenador trabalha no nível de **mensagens** (ele sabe o que está na rede). Na Parte 2 ele trabalha no nível de **chamadas** — o middleware esconde transporte, serialização e conexão, o que torna o código mais enxuto e menos propenso a erros de protocolo.
3. **A arquitetura mestre/escravo se mantém nas duas partes.** A divisão de responsabilidades (mestre distribui; escravo calcula) não mudou; o que mudou foi a camada de comunicação entre eles.
4. **Como concorrência de verdade com middleware?** Para isso, o cliente precisaria disparar as chamadas em threads (padrão utilizado no assíncrono da Parte 1) mantendo uma fila de resultados — o rpyc sozinho não oferece isso.

**Conclusão.** As duas partes resolvem o mesmo problema e produzem a mesma matriz; a Parte 1 explora e exige o controle manual do protocolo distribuído (sendo que o assíncrono, com threads, foi o que trouxe paralelismo), enquanto a Parte 2 prioriza abstração e manutenibilidade, trocando mensagens por chamadas remotas.