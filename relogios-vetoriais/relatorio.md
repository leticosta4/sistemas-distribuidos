# Monitoramento Distribuído de Eventos com Relógios Vetoriais

> Alunas: Letícia Almeida e Sophia Lima

## 1. Objetivo

Desenvolver um sistema distribuído simples utilizando Python e Pyro5, no qual diferentes processos geram e compartilham eventos. O sistema deverá utilizar relógios vetoriais para registrar a ordem causal dos eventos e identificar eventos concorrentes.

## 2. Descrição

O sistema possui 4 processos independentes (P1, P2, P3, P4) executados concorrentemente. Cada processo gera eventos sucessivos em intervalos aleatórios. 

Quando um processo gera um evento:
- Atualiza seu relógio vetorial (C1).
- Registra o evento no log local (event_id, processo, instante, relógio vetorial).
- Envia o evento aos demais processos, com uma cópia do mesmo vetor, em ordem embaralhada e com atrasos aleatórios entre os envios.

Ao receber um evento (mensagem), o processo:
- Atualiza seu relógio vetorial conforme as regras de relógios vetoriais (merge + incremento próprio, C3).
- Registra a ENTRADA e uma linha de ANÁLISE (comparação com eventos conhecidos), apontando eventos concorrentes e/ou inversões entre ordem de chegada e ordem causal.

Cada envio é feito com `time.sleep` aleatório, não bloqueando o tratamento de mensagens recebidas (ouvinte em `daemon.requestLoop()` + threads separadas: gerador + pool do Pyro5). O mesmo evento local é disseminado com o MESMO vetor aos pares (broadcast causal). 

## 3. Requisitos atendidos

- [x] 4 processos independentes (P1–P4)
- [x] Geração de eventos em intervalos aleatórios
- [x] Disseminação aos demais com atrasos e ordens diferentes por destinatário
- [x] Atualização correta do relógio vetorial (local: `V[i]++`; recebimento: `V[j] = max(V[j], mensagem[j]); V[i]++`)
- [x] Log local por processo (timestamp relativo, tipo, detalhe, VC)
- [x] Registro de envio, recebimento, análise e resumo
- [x] Comunicação via Pyro5, sem bloquear recebimento durante envios

## 4. Instruções para executar

### Pré-requisitos

- Python 3.10+
- Pyro5 5.17 (instalado via `requirements.txt` na raiz do repositório)
- Ambiente virtual ativado (`.venv`)

### Opção 1: Orquestrador (recomendada)

Subir tudo com um único comando. O script dispara o nameserver e os 4 processos, imprimindo os logs intercalados no mesmo terminal. Ao final, gera `logs/P1.log`, `logs/P2.log`, `logs/P3.log`, `logs/P4.log`.

```bash
cd sistemas-distribuidos
source .venv/bin/activate  # Windows: .venv\Scripts\activate
cd relogios-vetoriais
python executar.py --duracao 30
```

Parâmetros úteis:
- `--n 4` (padrão)
- `--duracao 30` (segundos gerando eventos; há ~3s de dreno para recebimento tardio)
- `--ns-port 9090`, `--host 127.0.0.1`
- `--log-dir logs`

### Opção 2: Manual (4 terminais)

Ideal para observar cada log separadamente.

**Terminal 1 – Name Server**
```bash
cd sistemas-distribuidos
source .venv/bin/activate
python -m Pyro5.nameserver -n 127.0.0.1 -p 9090
```

**Terminais 2–5 – Processos**
```bash
cd sistemas-distribuidos
source .venv/bin/activate
cd relogios-vetoriais
python processo.py --id P1 --duracao 30 --n 4 --ns-host 127.0.0.1 --ns-port 9090
python processo.py --id P2 --duracao 30 --n 4 --ns-host 127.0.0.1 --ns-port 9090
python processo.py --id P3 --duracao 30 --n 4 --ns-host 127.0.0.1 --ns-port 9090
python processo.py --id P4 --duracao 30 --n 4 --ns-host 127.0.0.1 --ns-port 9090
```

## 5. Exemplo dos logs produzidos

A execução gera um arquivo por processo: `relogios-vetoriais/logs/P1.log`, `P2.log`, `P3.log`, `P4.log`. Cada linha segue o formato:

```
[tempo] Pi | TIPO       | detalhe                                                         | VC=[v1,v2,v3,v4]
```

Tipos utilizados: `INFO`, `EVENTO_LOCAL`, `ENVIO`, `ENTRADA`, `ANALISE`, `RESUMO`.

### 5.1 Evento local (C1)

O processo incrementa apenas sua própria entrada.

```
[  0.612] P1 | EVENTO_LOCAL | e1 tarefa concluida                                             | VC=[1,0,0,0]
```

### 5.2 Envio com atraso à ordem embaralhada

O mesmo VC de e1 é enviado a cada par, com `time.sleep` aleatório entre envios. A ordem dos pares varia entre eventos.

```
[  0.652] P1 | ENVIO       | e1 -> P2 | atraso 0.042s | entregue                             | VC=[1,0,0,0]
[  0.702] P1 | ENVIO       | e1 -> P3 | atraso 0.050s | entregue                             | VC=[1,0,0,0]
[  0.742] P1 | ENVIO       | e1 -> P4 | atraso 0.040s | entregue                             | VC=[1,0,0,0]
```

### 5.3 Recebimento + C3

Ao receber `vc_msg=[1,0,0,0]` de P1, P2 faz merge e incrementa sua entrada: `[max(0,1), max(0,0), ..., 0] -> [1,0,0,0]; V[1]+=1 -> [1,1,0,0]`. O recebimento é registrado como `r1`.

```
[  1.024] P2 | ENTRADA     | r1 <- P1#1 'e1 tarefa concluida' | [0,0,0,0] -> [1,1,0,0]       | VC=[1,1,0,0]
```

### 5.4 Análise causal

Compara o vetor recebido com o histórico. Quando não há relação de happened-before, é marcado como **concorrente**. Quando um evento que chegou agora é causalmente anterior a outro que já havia chegado, é identificada **ordem de chegada invertida** — isso demonstra que a ordem física não coincide com a causal.

```
[  1.025] P2 | ANALISE     | CONCORRENTE com e1; sem inversao em relacao ao ja conhecido      | VC=[1,1,0,0]
```

### 5.5 Resumo ao término

```
[ 30.812] P1 | RESUMO      | eventos locais=14 | envios=39 (falhas 0) | entradas=13 | concorrencias=43 | chegadas invertidas=21 | VC=[14,13,13,13]
[ 30.812] P1 | RESUMO      | log encerrado                                                     | VC=[14,13,13,13]
```

Os números variam por execução (intervalos/atrasos aleatórios), mas:
- `entradas` corresponde aos eventos recebidos de outros processos;
- `concorrencias` é o número de comparações em que o evento recebido era incomparável com algum evento já conhecido;
- `chegadas invertidas` indica casos em que a chegada física foi posterior à chegada do evento causalmente dependente — evidenciando que apenas o timestamp local não basta para estabelecer causalidade.

## 6. Demonstração da correção dos relógios vetoriais

- **C1 (evento local):** `V[i]++` — incrementa apenas índice do próprio processo.
- **C2 (envio):** mensagem carrega cópia integral de `V` após o incremento — garante que o receptor saiba o "estado" causal do remetente.
- **C3 (recebimento):** `max` componente a componente + `V[i]++` — incorpora o que o remetente conhecia, sem descartar conhecimento próprio, e registra o recebimento como evento.

Exemplo prático:
1. P1 gera e1: VC_P1 = `[1,0,0,0]`
2. P2 recebe e1 de P1: antes `[0,0,0,0]`, merge -> `[1,0,0,0]`, depois de receber -> `[1,1,0,0]`
3. P3 recebe e1 de P1: `[1,0,1,0]`
4. P2 gera e2: `[1,2,0,0]` (incrementa índice 1)
5. P3 pode receber e2 de P2 ANTES ou DEPOIS de algum evento de P4: os vetores permitirão detectar concorrência e/ou a relação `e1 -> e2`.

Comparação (happen-before):
- `[1,0,0,0] <= [1,1,0,0]` => "a antes de b" (P1 causou a entrada em P2)
- `[1,1,0,0]` e `[1,0,1,0]` não são comparáveis => concorrentes
- `[1,0,0,0]` <= `[1,2,0,0]` => o conhecimento de e1 chegou junto ao de e2 (P2 conhece e1 via P1)

## 7. Implementação (detalhes)

- **Módulos:** `relogio_vetorial.py` (classe `RelogioVetorial`, regras C1/C3, comparação `comparar`, utilitários), `processo.py` (classe `Processo` exposta ao Pyro, geração, envio com atrasos/embaralhamento, recebimento, análise), `executar.py` (orquestrador: nameserver + 4 subprocessos).
- **Comunicação:** Pyro5. Cada processo registra `processo.Pi` no Name Server; para enviar, obtém `Proxy` de cada par.
- **Concorrência:** 
  - `daemon.requestLoop()` recebe chamadas remotas (pool de threads do Pyro5).
  - `thread_geracao` gera eventos e faz envios com `time.sleep` (defasagem).
  - `threading.Lock` protege `relogio`, histórico, contadores e escrita em arquivo.
- **Atraso e ordem:** em cada `disseminar()`, embaralha destinos com `random.shuffle`, para cada um `time.sleep(uniform(0.02,0.20))`, depois chama `proxy.receber_evento(...)`. Nunca segura o lock durante o sleep ou durante a RPC.
- **Broadcast causal:** um único incremento gera UM vetor `vc`; esse MESMO vetor é enviado às N-1 cópias (não se incrementa por envio).
- **Descoberta:** aguarda pares no Name Server até 20s antes de começar a gerar (permite subir tudo em paralelo). 
- **Logs:** relativos a `t0`, flush imediato, um arquivo por processo (reprodutível por execução). 

## 8. Referências

- Mattern, F. (1989). Virtual Time and Global States of Distributed Systems. 
- Coulouris et al. Distributed Systems: Concepts and Design (cap. 14 – Ordering of events)
- Pyro5 Docs: https://pyro5.readthedocs.io/
