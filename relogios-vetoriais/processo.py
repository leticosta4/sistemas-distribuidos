"""
processo.py
===========

Processo distribuido P_i do sistema de monitoring de eventos com RELOGIOS
VETORIAIS (trabalho da disciplina de Sistemas Distribuidos - UNEB).

Cada processo executado por este script e um processo INDEPENDENTE (um
processo de SO distinto, iniciado pelo `executar.py` ou manualmente) que:

  1. registra um objeto Pyro5 no Servidor de Nomes, com nome "processo.Pi";
  2. gera EVENTOS LOCAIS em intervalos ALEATORIOS (thread `loop_geracao`);
  3. a cada evento local:
        - incrementa o proprio relogio vetorial        (regra C1);
        - grava o evento no log local;
        - envia o relogio aos demais processos, com um ATRASO SIMULADO
          (time.sleep) diferente e em ORDEM EMBARALHADA para cada destinatario
          (a defasagem acontece SEM segurar nenhum bloqueio, portanto o
          recebimento de mensagens nunca fica bloqueado pelo envio);
  4. ao receber uma mensagem (metodo `receber_evento`, executado nas threads
     do pool do Pyro5):
        - atualiza o relogio vetorial                 (regras C3);
        - grava a ENTRADA no log local;
        - faz a ANALISE causal: compara o evento recebido com os eventos
          locais e com os ja recebidos, apontando CONCORRENCIAS e CASOS em
          que a ordem de CHEGADA divergiu da ordem CAUSAL.

Estrutura de threads de um processo:

    thread principal ..... daemon.requestLoop()  -> recebe mensagens Pyro5
    thread "gerador" ..... gera eventos + envia com atrasos aleatorios
    (threads do Pyro5 ... chamam `receber_evento` concorrentemente)

Todo acesso ao relogio e ao arquivo de log e protegido por `self.bloqueio`,
justamente porque esses tres atores (principal, gerador, pool do Pyro5)
tocam no mesmo estado.  O bloqueio NUNCA e mantido durante um time.sleep()
ou durante uma chamada RPC.

Uso:
    python processo.py --id P1
    python processo.py --id P2 --duracao 30 --n 4
"""

from __future__ import annotations

import argparse
import random
import threading
import time
from pathlib import Path

import Pyro5.api
from Pyro5.errors import NamingError

from relogio_vetorial import RelogioVetorial

# Descricoes possiveis para um evento local (coisa que o processo "fez").
# O trabalho pede que o evento represente algo concreto: conclusao de tarefa,
# alteracao de estado, operacao local...
ACOES = [
    "tarefa concluida",
    "estado alterado",
    "operacao local executada",
    "checkpoint salvo",
    "recurso liberado",
    "contador incrementado",
    "resultado parcial disponibilizado",
    "validacao concluida",
]


# ====================================================================== #
# 1. LOG                                                                 #
# ====================================================================== #
class Registro:
    """
    Log do processo: cada linha e gravada AO MESMO TEMPO no console e em um
    arquivo `logs/Pi.log` (um arquivo por processo), para que seja possivel
    acompanhar a evolucao dos relogios durante a execucao e depois anexar
    exemplos no relatorio.

    IMPORTANTE: todas as chamadas a `linha()` devem ser feitas com
    `Processo.bloqueio` segurado, para que duas threads nao intercalem
    caracteres de linhas diferentes.
    """

    def __init__(self, id_processo: str, caminho: Path) -> None:
        self.id = id_processo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        # modo "w": cada execucao comeca um log novo (mais facil de apresentar
        # como exemplo de saida do que ir concatenando execucoes antigas).
        self.arquivo = open(caminho, "w", encoding="utf-8")
        self.t0 = time.time()
        self.caminho = caminho

    def linha(self, tipo: str, detalhe: str, vc) -> None:
        """Escreve uma linha padronizada: [tempo] Pi | TIPO | detalhe | VC=..."""
        texto = (
            f"[{time.time() - self.t0:8.3f}] {self.id:<3} | {tipo:<12} | "
            f"{detalhe:<62} | VC={vc}"
        )
        print(texto, flush=True)
        self.arquivo.write(texto + "\n")
        self.arquivo.flush()  # o log esta sempre completo, mesmo com Ctrl+C

    def fechar(self) -> None:
        self.arquivo.close()


# ====================================================================== #
# 2. PROCESSO                                                            #
# ====================================================================== #
@Pyro5.api.expose
class Processo:
    """
    Objeto registrado no Pyro5.  O metodo `receber_evento` e o unico exposto
    aos demais processos (o decorador @expose torna publicos os metodos
    nao-privados da classe, por isso o restante usa prefixo "_").
    """

    def __init__(self, id_processo: str, n: int, duracao: float, caminho_log: Path) -> None:
        self.id = id_processo
        self.n = n
        self.duracao = duracao
        self.dreno = 3.0  # segundos extras de vida para receber atrasados

        # --- estado protegido por `self.bloqueio` ---------------------- #
        self.bloqueio = threading.Lock()
        self.relogio = RelogioVetorial(id_processo, n)
        self.seq_local = 0          # numero do proximo evento local (e1, e2...)
        self.seq_recebido = 0       # numero do proximo recebimento (r1, r2...)
        self.historico = []         # [(rotulo, vc)] TODOS os eventos ja vistos
        self.recebidos = []         # [(rotulo, vc)] apenas os vindos de fora,
                                    # ja com a ordem de chegada implicita
        self.stats = {
            "eventos_locais": 0,
            "envios_ok": 0,
            "envios_falha": 0,
            "entradas": 0,
            "concorrencias": 0,
            "inversoes_chegada": 0,
        }
        # --------------------------------------------------------------- #

        self.tempo_inicio = time.time()   # ajustado em `iniciar()` (main)
        self.parar = threading.Event()    # sinaliza fim da geracao de eventos
        self.uris_pares = {}              # {id: uri} descobertas no nameserver
        self.proxies = {}                 # {id: Proxy} criados NA thread geradora
        self.rng = random.Random(f"{id_processo}-{time.time()}")

        self.registro = Registro(id_processo, caminho_log)

    # ------------------------------------------------------------------ #
    # Log (sempre com o bloqueio segurado pelo chamador)                  #
    # ------------------------------------------------------------------ #
    def _registrar(self, tipo: str, detalhe: str, vc) -> None:
        self.registro.linha(tipo, detalhe, vc)

    # ------------------------------------------------------------------ #
    # RPC: recebimento de uma mensagem vinda de outro processo            #
    # ------------------------------------------------------------------ #
    def receber_evento(self, origem: str, seq_origem: int, vc_msg: list, descricao: str) -> str:
        """
        Chamado remotamente pelo processo `origem` quando ele gera um evento.

        Executa (C3) atualizacao do relogio, registra a ENTRADA no log e faz
        a analise causal.  Roda nas threads do pool do Pyro5, portanto pode
        ser chamado concorrentemente com a thread geradora: por isso o
        bloqueio.  O corpo inteiro e curto e nunca dorme, entao o custo de
        serializar o acesso e desprezivel.
        """
        with self.bloqueio:
            # (C3) incorpora o vetor do remetente e incrementa o proprio.
            vc_antes, vc_depois = self.relogio.receber(vc_msg)

            self.seq_recebido += 1
            rotulo = f"r{self.seq_recebido}"
            self.stats["entradas"] += 1
            self.historico.append((rotulo, vc_depois))
            self.recebidos.append((rotulo, vc_msg))

            self._registrar(
                "ENTRADA",
                f"{rotulo} <- {origem}#{seq_origem} '{descricao}' | {vc_antes} -> {vc_depois}",
                vc_depois,
            )

            # ---- ANALISE CAUSAL (a parte principal da demonstracao) ---- #
            notas, concorrencias, inversoes = self._analisar(vc_msg)
            self.stats["concorrencias"] += concorrencias
            self.stats["inversoes_chegada"] += inversoes
            self._registrar("ANALISE", notas, vc_depois)

        # a resposta vai para o chamador; nao precisa ser feita sob bloqueio.
        return f"{self.id} registrou {rotulo}"

    def _analisar(self, vc_msg: list) -> tuple:
        """
        Compara o evento recem-chegado (`vc_msg`) com o que este processo ja
        conhece e devolve:

          - notas:     texto para a linha ANALISE do log;
          - concorrencias: quantidade de eventos incomparaveis detectados;
          - inversoes: quantidade de eventos que chegaram DEPOIS de um
                       posterior a eles na ordem causal.

        Dois tipos de observacao sao geradas:

        (a) CONCORRENCIA: existe um evento anterior cujo vetor e incomparavel
            com o do evento recebido -- nenhum causou o outro.  Esse tipo de
            relacao NAO e observavel apenas olhando a ordem de chegada.

        (b) INVERSAO DE CHEGADA: um evento `x` recem-chegado tem vetor
            estritamente MENOR que o de um evento `y` que ja tinha chegado,
            ou seja, `x -> y` (x causou y) porem `y` chegou primeiro.  E a
            prova, dentro dos logs, de que a ordem fisica das mensagens nao
            e a ordem causal.
        """
        concorrentes = [
            rot
            for rot, vc in self.historico
            if RelogioVetorial.sao_concorrentes(vc, vc_msg)
        ]
        # x chegou agora e y chegou antes, mas x -> y: ordem de chegada invertida.
        invertidos = [
            rot
            for rot, vc in self.recebidos
            if RelogioVetorial.ocorreu_antes(vc_msg, vc)
        ]

        partes = []
        if concorrentes:
            partes.append(f"CONCORRENTE com {', '.join(concorrentes)}")
        if invertidos:
            partes.append(
                f"CHEGADA INVERTIDA: este evento e causalmente anterior a {', '.join(invertidos)}"
            )
        if not partes:
            partes.append("sem concorrencia nem inversao em relacao ao ja conhecido")

        return (
            "; ".join(partes),
            len(concorrentes),
            len(invertidos),
        )

    # ------------------------------------------------------------------ #
    # Thread geradora: eventos locais + disseminacao com atrasos          #
    # ------------------------------------------------------------------ #
    def iniciar_geracao(self) -> threading.Thread:
        """Cria e sobret a thread que gera eventos (chamado pelo main)."""
        t = threading.Thread(target=self._loop_geracao, name="gerador", daemon=True)
        t.start()
        return t

    def _loop_geracao(self) -> None:
        """
        Fica gerando eventos em intervalos aleatorios ate acabar a duracao
        da execucao.  Cada volta:

            dorme um intervalo aleatorio (sem bloqueio nenhum)
            -> evento local: incrementa o relogio e grava no log
            -> dissemina aos pares em ordem embaralhada, dormindo um atraso
               aleatorio ANTES de cada envio (defasagem pedida no trabalho)

        As dormidas acontecem SEM o bloqueio, de modo que as mensagens que
        chegam sao processadas normalmente enquanto este processo esta no
        meio de um atraso de envio.
        """
        # Espera os pares terminarem de ser descobertos (o main faz isso
        # antes de chamar iniciar_geracao; aqui e so uma garantia).
        while not self.uris_pares and not self.parar.is_set():
            time.sleep(0.05)

        while not self.parar.is_set():
            intervalo = self.rng.uniform(0.4, 1.8)  # instante aleatorio
            if self.parar.wait(intervalo):
                break
            if time.time() >= self.tempo_inicio + self.duracao:
                break
            self._gerar_evento()

    def _gerar_evento(self) -> None:
        """Gera um evento local (C1) e o envia a todos os pares."""
        # ---------------- evento local (C1) ---------------- #
        with self.bloqueio:
            vc = self.relogio.incrementar()
            self.seq_local += 1
            seq = self.seq_local
            acao = self.rng.choice(ACOES)
            descricao = f"e{seq} {acao}"
            self.stats["eventos_locais"] += 1
            self.historico.append((f"e{seq}", list(vc)))
            self._registrar("EVENTO_LOCAL", descricao, vc)

        # ---------------- disseminacao ---------------- #
        self._disseminar(seq, descricao, vc)

    def _disseminar(self, seq: int, descricao: str, vc: list) -> None:
        """
        Envia o evento para todos os pares.

        Pontos obrigatorios do trabalho atendidos aqui:

        * ORDEM DIFERENTE POR DESTINATARIO: os pares sao embaralhados a cada
          evento (`rng.shuffle`), entao P2 pode receber o evento e1 antes de
          P3, e no evento seguinte a ordem pode inverter.
        * ATRASO SIMULADO: `time.sleep(atraso)` entre um envio e o outro,
          com atraso aleatorio.  E esse atraso que faz as mensagens de um
          mesmo processo chegarem aos destinos em ordens distintas.
        * As mensagens sao FEITAS AQUI; o recebimento e tratado pelo
          `daemon.requestLoop()` na thread principal, ou seja, o atraso de
          envio nao trava o tratamento de mensagens recebidas.
        * Nenhuma dessas operacoes segura `self.bloqueio` (nem o sleep, nem a
          RPC), entao os eventos recebidos continuam sendo processados.
        """
        destinos = [p for p in self.uris_pares]
        if not destinos:
            return
        self.rng.shuffle(destinos)  # ordem de envio aleatoria a cada evento

        for destino in destinos:
            atraso = self.rng.uniform(0.02, 0.20)  # defasagem simulada
            time.sleep(atraso)                     # SEM bloqueio algum
            try:
                proxy = self._proxy_de(destino)
                proxy.receber_evento(self.id, seq, list(vc), descricao)
                status = "entregue"
                ok = True
            except Exception as exc:  # peer ainda nao subiu / caiu no meio
                status = f"FALHOU ({type(exc).__name__})"
                ok = False

            with self.bloqueio:
                self.stats["envios_ok" if ok else "envios_falha"] += 1
                # O ENVIO NAO incrementa de novo o relogio: o evento ja foi
                # incrementado uma unica vez em _gerar_evento, e as tres
                # copias da mensagem carregam o MESMO vetor (broadcast causal).
                self._registrar(
                    "ENVIO",
                    f"e{seq} -> {destino:<3} | atraso {atraso:.3f}s | {status}",
                    vc,
                )

    def _proxy_de(self, destino: str) -> Pyro5.api.Proxy:
        """
        Retorna o proxy Pyro5 de um par, criand-o SOB NECESSIDADE.

        Um objeto Proxy do Pyro5 pertence a thread que o utiliza (se outra
        thread usar, ocorre o erro "the calling thread is not the owner of
        the proxy").  Como este metodo so e chamado pela thread geradora, o
        proxy e criado e usado exclusivamente por ela -- sem necessidade de
        `_pyroClaimOwnership`.
        """
        if destino not in self.proxies:
            self.proxies[destino] = Pyro5.api.Proxy(self.uris_pares[destino])
        return self.proxies[destino]

    # ------------------------------------------------------------------ #
    # Encerramento                                                        #
    # ------------------------------------------------------------------ #
    def deve_continuar(self) -> bool:
        """Condicao de parada do requestLoop (checada a cada ~2 s pelo Pyro)."""
        return time.time() < self.tempo_inicio + self.duracao + self.dreno

    def finalizar(self) -> None:
        """Grava o RESUMO no log e o fecha (chamado ao sair do requestLoop)."""
        with self.bloqueio:
            s = self.stats
            self._registrar(
                "RESUMO",
                f"eventos locais={s['eventos_locais']} | envios={s['envios_ok']}"
                f" (falhas {s['envios_falha']}) | entradas={s['entradas']}"
                f" | concorrencias={s['concorrencias']}"
                f" | chegadas invertidas={s['inversoes_chegada']}",
                self.relogio.copia(),
            )
            self._registrar("RESUMO", "log encerrado", self.relogio.copia())
        self.registro.fechar()


# ====================================================================== #
# 3. DESCOBERTA NO SERVIDOR DE NOMES                                      #
# ====================================================================== #
def localizar_ns(host: str, porta: int, timeout: float = 15.0) -> Pyro5.api.Proxy:
    """Procura o servidor de nomes Pyro5 com rete ate `timeout` segundos."""
    fim = time.time() + timeout
    ultimo_erro = None
    while time.time() < fim:
        try:
            return Pyro5.api.locate_ns(host, porta)
        except NamingError as exc:
            ultimo_erro = exc
            time.sleep(0.25)
    raise RuntimeError(
        f"servidor de nomes nao encontrado em {host}:{porta} ({ultimo_erro}). "
        "Inicie com: python -m Pyro5.nameserver"
    )


def registrar_no_ns(ns: Pyro5.api.Proxy, nome: str, uri) -> None:
    """
    Registra o processo no nameserver.  Se ja existir um registro antigo
    (processo anterior morto sem limpeza), remove e registra de novo.
    """
    try:
        ns.register(nome, uri)
    except NamingError:
        ns.remove(nome)
        ns.register(nome, uri)


def descobrir_pares(
    ns: Pyro5.api.Proxy, meu_id: str, n: int, timeout: float = 20.0
) -> dict:
    """
    Localiza as URIs dos demais processos ("processo.P1"..."processo.Pn").
    Como os processos sobem em paralelo, o lookup e refeito com atraso ate
    `timeout`; se algum par nunca aparecer, o processo segue com os que
    encontrar (e avisa no log).
    """
    alvos = [f"P{i}" for i in range(1, n + 1) if f"P{i}" != meu_id]
    uris = {}
    fim = time.time() + timeout
    pendentes = list(alvos)
    while pendentes and time.time() < fim:
        for alvo in list(pendentes):
            try:
                uris[alvo] = ns.lookup(f"processo.{alvo}")
                pendentes.remove(alvo)
            except NamingError:
                time.sleep(0.25)
    return uris


# ====================================================================== #
# 4. MAIN                                                                #
# ====================================================================== #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Processo com relogio vetorial (Pyro5)")
    p.add_argument("--id", required=True, help="identificador: P1, P2, P3 ou P4")
    p.add_argument("--n", type=int, default=4, help="quantidade de processos do sistema")
    p.add_argument("--duracao", type=float, default=30.0, help="segundos gerando eventos")
    p.add_argument("--host", default="127.0.0.1", help="host deste daemon Pyro5")
    p.add_argument("--ns-host", default="127.0.0.1", help="host do servidor de nomes")
    p.add_argument("--ns-port", type=int, default=9090, help="porta do servidor de nomes")
    p.add_argument("--descoberta", type=float, default=20.0, help="timeout de descoberta (s)")
    p.add_argument(
        "--log-dir",
        default=str(Path(__file__).resolve().parent / "logs"),
        help="pasta dos logs (logs/Pi.log)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    meu_id = args.id.upper()
    caminho_log = Path(args.log_dir) / f"{meu_id}.log"

    # --- infraestrutura Pyro5 ---------------------------------------- #
    # O daemon e o servidor que recebe as chamadas remotas deste processo;
    # ele e que executa `receber_evento` nas threads do pool.
    daemon = Pyro5.api.Daemon(host=args.host)
    ns = localizar_ns(args.ns_host, args.ns_port)

    processo = Processo(meu_id, args.n, args.duracao, caminho_log)

    uri = daemon.register(processo)
    nome = f"processo.{meu_id}"
    registrar_no_ns(ns, nome, uri)

    # --- descoberta dos pares (antes de comecar a gerar eventos) ------ #
    uris = descobrir_pares(ns, meu_id, args.n, timeout=args.descoberta)
    processo.uris_pares = uris

    with processo.bloqueio:
        processo._registrar(
            "INFO",
            f"processo {meu_id} de {args.n} | duracao {args.duracao:.0f}s"
            f" | pares: {', '.join(sorted(uris)) or 'nenhum'}",
            processo.relogio.copia(),
        )
        if len(uris) < args.n - 1:
            processo._registrar(
                "INFO",
                f"AVISO: apenas {len(uris)}/{args.n - 1} pares encontrados",
                processo.relogio.copia(),
            )

    # O relogio comeca a contar a partir de agora (descoberta ja concluida).
    processo.tempo_inicio = time.time()
    thread_gerador = processo.iniciar_geracao()

    try:
        # Loop principal: fica ouvindo as chamadas dos outros processos ate
        # terminar `duracao + dreno` segundos.  O Pyro reavalia a condicao a
        # cada ~2 s (POLLTIMEOUT), entao o desligamento e bem proximo do fim.
        daemon.requestLoop(loopCondition=processo.deve_continuar)
    except KeyboardInterrupt:
        processo.parar.set()

    # Espera a thread geradora terminar o envio que estava em andamento.
    processo.parar.set()
    thread_gerador.join(timeout=5)

    processo.finalizar()
    try:
        ns.remove(nome)  # limpa o nameserver para a proxima execucao
    except Exception:
        pass
    daemon.close()


if __name__ == "__main__":
    main()
