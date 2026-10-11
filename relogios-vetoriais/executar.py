"""
script pra rodar a simulação inteira de uma vez.

em vez de ter que abrir 5 terminais na mão (um pro nameserver e quatro pros
processos P1 a P4), esse script já sobe tudo sozinho:
1. inicia o nameserver do pyro5 em segundo plano e espera ele responder;
2. sobe os processos P1 até Pn como processos independentes do SO;
3. imprime tudo no mesmo terminal pra gente ver a ordem dos eventos acontecendo;
4. espera o tempo da simulação e encerra todo mundo direitinho no final.
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
    # argumentos da linha de comando pra facilitar os testes
    p = argparse.ArgumentParser(description="inicia o nameserver e os processos P1..Pn")
    p.add_argument("--n", type=int, default=4, help="quantidade de processos (padrão: 4)")
    p.add_argument("--duracao", type=float, default=30.0, help="tempo gerando eventos em segundos")
    p.add_argument("--host", default="127.0.0.1", help="host local")
    p.add_argument("--ns-port", type=int, default=9090, help="porta do nameserver Pyro5")
    p.add_argument(
        "--log-dir",
        default=str(PASTA / "logs"),
        help="pasta para salvar os logs individuais",
    )
    return p.parse_args()


def subir_nameserver(host: str, porta: int) -> subprocess.Popen:
    # sobe o nameserver do pyro5 em segundo plano e espera ele ficar pronto
    print(f"[EXECUTAR] subindo Name Server em {host}:{porta}...")
    ns_proc = subprocess.Popen(
        [sys.executable, "-m", "Pyro5.nameserver", "-n", host, "-p", str(porta)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    # dá um tempinho pro nameserver subir antes de tentar conectar
    fim = time.time() + 15
    while time.time() < fim:
        if ns_proc.poll() is not None:
            raise RuntimeError("o Name Server morreu antes da hora (porta já ocupada?).")
        try:
            Pyro5.api.locate_ns(host, porta)
            print("[EXECUTAR] Name Server online.")
            return ns_proc
        except NamingError:
            time.sleep(0.25)

    ns_proc.terminate()
    raise RuntimeError("tempo limite esgotado esperando o Name Server subir.")


def main() -> None:
    args = parse_args()
    filhos: list[subprocess.Popen] = []
    ns_proc = None

    try:
        ns_proc = subir_nameserver(args.host, args.ns_port)

        # sobe cada processo como um processo independente do SO
        # deixamos a saída no mesmo console pra gente ver os logs intercalados
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

        # espera todo mundo acabar (tempo da simulação + folga pras mensagens em trânsito)
        limite = args.duracao + 45
        inicio = time.time()
        for i, f in enumerate(filhos, start=1):
            restante = max(1, limite - (time.time() - inicio))
            codigo = f.wait(timeout=restante)
            print(f"[EXECUTAR] processo P{i} finalizado com código {codigo}")

    except KeyboardInterrupt:
        print("\n[EXECUTAR] execução interrompida. encerrando processos...")
    finally:
        # encerramento limpo: mata os processos filhos e o nameserver se ainda tiverem vivos
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

        print("[EXECUTAR] logs salvos em:")
        for i in range(1, args.n + 1):
            print(f"           {Path(args.log_dir) / f'P{i}.log'}")


if __name__ == "__main__":
    main()
