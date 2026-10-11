"""
código de cada processo do sistema distribuído.

aqui cada processo:
- se cadastra no servidor de nomes do pyro5;
- fica gerando eventos locais em momentos aleatórios;
- manda esses eventos pros outros processos com delays e ordem bagunçada;
- escuta as mensagens dos outros nós e atualiza o relógio vetorial.
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

# lista com algumas ações fictícias pros eventos locais
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


class Registro:
    # grava os logs no console e no arquivo .log ao mesmo tempo
    def __init__(self, id_processo: str, caminho: Path) -> None:
        self.id = id_processo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        # limpa/cria o arquivo do zero a cada execução
        self.arquivo = open(caminho, "w", encoding="utf-8")
        self.t0 = time.time()
        self.caminho = caminho

    def linha(self, tipo: str, detalhe: str, vc) -> None:
        # monta a linha padronizada com tempo relativo desde o início
        texto = (
            f"[{time.time() - self.t0:8.3f}] {self.id:<3} | {tipo:<12} | "
            f"{detalhe:<62} | VC={vc}"
        )
        print(texto, flush=True)
        self.arquivo.write(texto + "\n")
        self.arquivo.flush()

    def fechar(self) -> None:
        self.arquivo.close()


@Pyro5.api.expose
class Processo:
    # classe do processo que fica exposta no pyro5 pros outros nós chamarem
    def __init__(self, id_processo: str, n: int, duracao: float, caminho_log: Path) -> None:
        self.id = id_processo
        self.n = n
        self.duracao = duracao
        self.dreno = 3.0  # tempo extra pra esperar mensagens que ainda tão em trânsito

        # lock pra proteger o relógio e as listas de acessos concorrentes entre threads
        self.bloqueio = threading.Lock()
        self.relogio = RelogioVetorial(id_processo, n)
        self.seq_local = 0          # contador de eventos gerados aqui (e1, e2...)
        self.seq_recebido = 0       # contador de mensagens recebidas (r1, r2...)
        self.historico = []         # guarda todos os eventos pra gente analisar causalidade
        self.recebidos = []         # apenas eventos que vieram dos outros processos
        self.stats = {
            "eventos_locais": 0,
            "envios_ok": 0,
            "envios_falha": 0,
            "entradas": 0,
            "concorrencias": 0,
            "inversoes_chegada": 0,
        }

        self.tempo_inicio = time.time()
        self.parar = threading.Event()
        self.uris_pares = {}              # uris encontradas no nameserver {id: uri}
        self.proxies = {}                 # proxies do pyro criados sob demanda {id: Proxy}
        self.rng = random.Random(f"{id_processo}-{time.time()}")

        self.registro = Registro(id_processo, caminho_log)

    def _registrar(self, tipo: str, detalhe: str, vc) -> None:
        self.registro.linha(tipo, detalhe, vc)

    def receber_evento(self, origem: str, seq_origem: int, vc_msg: list, descricao: str) -> str:
        # método chamado via rpc quando outro processo manda mensagem
        with self.bloqueio:
            # regra C3: faz o merge dos vetores e soma 1 no relógio local
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

            # checa se o evento recebido é concorrente ou se chegou com inversão causal
            notas, concorrencias, inversoes = self._analisar(vc_msg)
            self.stats["concorrencias"] += concorrencias
            self.stats["inversoes_chegada"] += inversoes
            self._registrar("ANALISE", notas, vc_depois)

        return f"{self.id} registrou {rotulo}"

    def _analisar(self, vc_msg: list) -> tuple:
        # compara o vetor recebido com os que a gente já conhece
        concorrentes = [
            rot
            for rot, vc in self.historico
            if RelogioVetorial.sao_concorrentes(vc, vc_msg)
        ]
        # se o evento recém-chegado aconteceu antes de um que já tinha chegado, inverteu a ordem
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

    def iniciar_geracao(self) -> threading.Thread:
        # inicia a thread que vai ficar gerando e enviando os eventos locais
        t = threading.Thread(target=self._loop_geracao, name="gerador", daemon=True)
        t.start()
        return t

    def _loop_geracao(self) -> None:
        # loop que sorteia intervalos aleatórios e vai gerando eventos
        # espera achar os outros processos antes de começar a disparar
        while not self.uris_pares and not self.parar.is_set():
            time.sleep(0.05)

        while not self.parar.is_set():
            intervalo = self.rng.uniform(0.4, 1.8)  # dorme um intervalo aleatório
            if self.parar.wait(intervalo):
                break
            if time.time() >= self.tempo_inicio + self.duracao:
                break
            self._gerar_evento()

    def _gerar_evento(self) -> None:
        # gera um evento local (C1) e dispara pros outros nós
        with self.bloqueio:
            vc = self.relogio.incrementar()
            self.seq_local += 1
            seq = self.seq_local
            acao = self.rng.choice(ACOES)
            descricao = f"e{seq} {acao}"
            self.stats["eventos_locais"] += 1
            self.historico.append((f"e{seq}", list(vc)))
            self._registrar("EVENTO_LOCAL", descricao, vc)

        # faz os envios fora do lock pra não travar mensagens que tão chegando
        self._disseminar(seq, descricao, vc)

    def _disseminar(self, seq: int, descricao: str, vc: list) -> None:
        # manda o evento pra todos os outros processos
        destinos = [p for p in self.uris_pares]
        if not destinos:
            return
        self.rng.shuffle(destinos)  # embaralha a lista pra mandar em ordem diferente a cada vez

        for destino in destinos:
            atraso = self.rng.uniform(0.02, 0.20)  # delay aleatório pra simular atraso de rede
            time.sleep(atraso)                     # feito sem segurar lock
            try:
                proxy = self._proxy_de(destino)
                proxy.receber_evento(self.id, seq, list(vc), descricao)
                status = "entregue"
                ok = True
            except Exception as exc:
                status = f"FALHOU ({type(exc).__name__})"
                ok = False

            with self.bloqueio:
                self.stats["envios_ok" if ok else "envios_falha"] += 1
                # o envio carrega o mesmo vetor gerado no evento local
                self._registrar(
                    "ENVIO",
                    f"e{seq} -> {destino:<3} | atraso {atraso:.3f}s | {status}",
                    vc,
                )

    def _proxy_de(self, destino: str) -> Pyro5.api.Proxy:
        # cria ou reaproveita o proxy pyro do destinatário
        if destino not in self.proxies:
            self.proxies[destino] = Pyro5.api.Proxy(self.uris_pares[destino])
        return self.proxies[destino]

    def deve_continuar(self) -> bool:
        # checa se ainda tá dentro do tempo total da simulação
        return time.time() < self.tempo_inicio + self.duracao + self.dreno

    def finalizar(self) -> None:
        # grava o resumo das estatísticas no fim do log e fecha o arquivo
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


def localizar_ns(host: str, porta: int, timeout: float = 15.0) -> Pyro5.api.Proxy:
    # procura o nameserver com retentativas até dar o timeout
    fim = time.time() + timeout
    ultimo_erro = None
    while time.time() < fim:
        try:
            return Pyro5.api.locate_ns(host, porta)
        except NamingError as exc:
            ultimo_erro = exc
            time.sleep(0.25)
    raise RuntimeError(
        f"servidor de nomes não encontrado em {host}:{porta} ({ultimo_erro}). "
        "inicie com: python -m Pyro5.nameserver"
    )


def registrar_no_ns(ns: Pyro5.api.Proxy, nome: str, uri) -> None:
    # registra o processo no nameserver (sobrescreve se já existia um velho)
    try:
        ns.register(nome, uri)
    except NamingError:
        ns.remove(nome)
        ns.register(nome, uri)


def descobrir_pares(
    ns: Pyro5.api.Proxy, meu_id: str, n: int, timeout: float = 20.0
) -> dict:
    # procura os outros processos no nameserver até todo mundo aparecer
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


def parse_args() -> argparse.Namespace:
    # argumentos de linha de comando
    p = argparse.ArgumentParser(description="processo com relógio vetorial (Pyro5)")
    p.add_argument("--id", required=True, help="identificador do processo (P1, P2, P3 ou P4)")
    p.add_argument("--n", type=int, default=4, help="quantidade total de processos")
    p.add_argument("--duracao", type=float, default=30.0, help="tempo gerando eventos (segundos)")
    p.add_argument("--host", default="127.0.0.1", help="host deste processo Pyro5")
    p.add_argument("--ns-host", default="127.0.0.1", help="host do Name Server")
    p.add_argument("--ns-port", type=int, default=9090, help="porta do Name Server")
    p.add_argument("--descoberta", type=float, default=20.0, help="timeout para descobrir outros nós (s)")
    p.add_argument(
        "--log-dir",
        default=str(Path(__file__).resolve().parent / "logs"),
        help="pasta dos arquivos de log",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    meu_id = args.id.upper()
    caminho_log = Path(args.log_dir) / f"{meu_id}.log"

    # sobe o daemon do pyro pra receber chamadas remotas
    daemon = Pyro5.api.Daemon(host=args.host)
    ns = localizar_ns(args.ns_host, args.ns_port)

    processo = Processo(meu_id, args.n, args.duracao, caminho_log)

    uri = daemon.register(processo)
    nome = f"processo.{meu_id}"
    registrar_no_ns(ns, nome, uri)

    # busca os outros processos antes de começar a disparar eventos
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

    # inicia a thread que gera os eventos locais
    processo.tempo_inicio = time.time()
    thread_gerador = processo.iniciar_geracao()

    try:
        # fica escutando chamadas dos outros nós até bater o tempo limite
        daemon.requestLoop(loopCondition=processo.deve_continuar)
    except KeyboardInterrupt:
        processo.parar.set()

    # espera a thread geradora terminar de vez
    processo.parar.set()
    thread_gerador.join(timeout=5)

    processo.finalizar()
    try:
        ns.remove(nome)  # remove do nameserver pra não deixar sujeira pra próxima vez
    except Exception:
        pass
    daemon.close()


if __name__ == "__main__":
    main()
