"""
executar.py
===========

Orquestrador da demonstracao: sobe TODA a infraestrutura da atividade com um
unico comando.

O que ele faz, nesta ordem:

  1. inicia o SERVIDOR DE NOMES do Pyro5 (`python -m Pyro5.nameserver`) como
     um processo filho, na porta 9090 de 127.0.0.1;
  2. espera o nameserver responder ao `locate_ns`;
  3. dispara os 4 processos INDEPENDENTES do trabalho (P1..P4), cada um como
     um processo de SO separado rodando `processo.py` -- todos compartilhando
     o mesmo console, entao as linhas dos quatro logs aparecem intercaladas e
     da para acompanhar a ordem de chegada das mensagens em tempo real;
  4. aguarda os processos terminarem (cada um gera eventos por `--duracao`
     segundos e ainda fica `dreno` segundos recebendo atrasados);
  5. encerra o nameserver e aponta onde ficaram os logs individuais.

Tambem e possivel rodar tudo manualmente (um terminal para o nameserver e um
para cada processo) -- veja `relatorio.md`.

Uso:
    python executar.py
    python executar.py --duracao 10 --n 4
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import Pyro5.api
from Pyro5.errors import NamingError

PASTA = Path(__file__).resolve().parent
PROCESSO = PASTA / "processo.py"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sobe nameserver + processos P1..Pn")
    p.add_argument("--n", type=int, default=4, help="quantidade de processos")
    p.add_argument("--duracao", type=float, default=30.0, help="segundos de execucao")
    p.add_argument("--host", default="127.0.0.1", help="host comum (nameserver e daemons)")
    p.add_argument("--ns-port", type=int, default=9090, help="porta do nameserver")
    p.add_argument(
        "--log-dir",
        default=str(PASTA / "logs"),
        help="pasta dos logs individuais (logs/Pi.log)",
    )
    return p.parse_args()


def subir_nameserver(host: str, porta: int) -> subprocess.Popen:
    """
    Inicia o servidor de nomes do Pyro5 como subprocesso.

    Tambem seria possivel subir o nameserver dentro do proprio Python
    (`Pyro5.nameserver.start_ns_loop`), mas manter em um processo separado
    deixa o cenario mais parecido com o de producao e permite usar o mesmo
    comando das instrucoes manuais.
    """
    print(f"[EXECUTAR] subindo name server em {host}:{porta} ...")
    ns_proc = subprocess.Popen(
        [sys.executable, "-m", "Pyro5.nameserver", "-n", host, "-p", str(porta)],
        stdout=subprocess.DEVNULL,   # so interessa se ele responde ou nao
        stderr=subprocess.STDOUT,
    )

    # Espera o nameserver comecar a atender, com rete.
    fim = time.time() + 15
    while time.time() < fim:
        if ns_proc.poll() is not None:
            raise RuntimeError("name server encerrou antes da hora (porta em uso?)")
        try:
            Pyro5.api.locate_ns(host, porta)
            print("[EXECUTAR] name server pronto.")
            return ns_proc
        except NamingError:
            time.sleep(0.25)
    ns_proc.terminate()
    raise RuntimeError("name server nao respondeu em 15s")


def main() -> None:
    args = parse_args()
    filhos: list[subprocess.Popen] = []
    ns_proc = None

    try:
        ns_proc = subir_nameserver(args.host, args.ns_port)

        # Dispara os processos.  `sys.executable` garante que use o mesmo
        # interpretador/ambiente virtual onde o Pyro5 esta instalado.
        # stdout SEM redirecionar: as linhas dos 4 logs chegam intercaladas
        # neste console (cada linha ja comeca com o id do processo).
        for i in range(1, args.n + 1):
            cmd = [
                sys.executable,
                str(PROCESSO),
                "--id", f"P{i}",
                "--n", str(args.n),
                "--duracao", str(args.duracao),
                "--host", args.host,
                "--ns-host", args.host,
                "--ns-port", str(args.ns_port),
                "--log-dir", args.log_dir,
            ]
            print(f"[EXECUTAR] iniciando P{i}: {' '.join(cmd)}")
            filhos.append(subprocess.Popen(cmd))

        # Aguarda todos terminarem (margem para o dreno + descoberta).
        limite = args.duracao + 45
        inicio = time.time()
        for i, f in enumerate(filhos, start=1):
            restante = max(1, limite - (time.time() - inicio))
            codigo = f.wait(timeout=restante)
            print(f"[EXECUTAR] P{i} terminou com codigo {codigo}")

    except KeyboardInterrupt:
        print("\n[EXECUTAR] interrompido; encerrando processos...")
    finally:
        for f in filhos:
            if f.poll() is None:
                f.terminate()
        for f in filhos:
            if f.poll() is None:
                f.wait(timeout=5)
        if ns_proc is not None and ns_proc.poll() is None:
            ns_proc.terminate()
            try:
                ns_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ns_proc.kill()

        print("[EXECUTAR] logs individuais em:")
        for i in range(1, args.n + 1):
            print(f"           {Path(args.log_dir) / f'P{i}.log'}")


if __name__ == "__main__":
    main()
