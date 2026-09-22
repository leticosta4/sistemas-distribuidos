import rpyc
import socket
import sys
import time
import random
from datetime import datetime

DELAY_MAX = 1.0

PORTA_INICIAL = 8001
PORTA_FINAL = 8100

PORTA = PORTA_INICIAL


def agora():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def candidatas_para_porta():
    if len(sys.argv) > 1:
        return [int(sys.argv[1])]
    return list(range(PORTA_INICIAL, PORTA_FINAL + 1))


def primeira_porta_livre():
    for porta in candidatas_para_porta():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((socket.gethostbyname("localhost"), porta))
            s.close()
            return porta
        except OSError:
            continue
    return None


class TrabalhadorMatriz(rpyc.Service):

    def exposed_produto_escalar(self, linha, coluna):
        tempo_inicio = time.time()
        if DELAY_MAX > 0:
            time.sleep(random.uniform(0, DELAY_MAX))
        resultado = sum(a * b for a, b in zip(linha, coluna))
        print(
            "[" + agora() + "] [TRABALHADOR " + str(PORTA) + "] celula = " + str(resultado) +
            " (demora " + str(round(time.time() - tempo_inicio, 3)) + "s)",
            flush=True,
        )
        return resultado

    def exposed_tamanho(self):
        return {"porta": PORTA, "status": "pronto"}

    def exposed_encerrar(self):
        print("[" + agora() + "] [TRABALHADOR " + str(PORTA) + "] Encerrado pelo coordenador. Encerrou.", flush=True)


if __name__ == "__main__":
    porta = primeira_porta_livre()
    if porta is None:
        print("[" + agora() + "] [TRABALHADOR] Nenhuma porta livre em " + str(PORTA_INICIAL) + "-" + str(PORTA_FINAL) + ".", flush=True)
        sys.exit(1)
    PORTA = porta
    t = rpyc.utils.server.ThreadedServer(TrabalhadorMatriz, port=PORTA)
    print("[" + agora() + "] [TRABALHADOR " + str(PORTA) + "] RMI server rodando...", flush=True)
    try:
        t.start()
    except KeyboardInterrupt:
        print("\n[" + agora() + "] [TRABALHADOR " + str(PORTA) + "] Encerrado pelo usuario. Encerrou.", flush=True)