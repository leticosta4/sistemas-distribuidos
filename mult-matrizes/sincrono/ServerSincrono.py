import socket
import json
import sys
import time
import random
from datetime import datetime

HOST = "localhost"
PORTA_INICIAL = 8001
PORTA_FINAL = 8010

DELAY_MAX = 1.0

PORTA = PORTA_INICIAL


def agora():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def candidatas_para_porta():
    if len(sys.argv) > 1:
        return [int(sys.argv[1])]
    return list(range(PORTA_INICIAL, PORTA_FINAL + 1))


def receber_msg(conexao):
    dados = b""
    while True:
        parte = conexao.recv(4096)
        if not parte:
            return None
        dados = dados + parte
        if b"\n" in dados:
            break
    linha, _, _ = dados.partition(b"\n")
    return json.loads(linha.decode())


def enviar_msg(conexao, obj):
    dados = json.dumps(obj) + "\n"
    conexao.sendall(dados.encode())


def produto_escalar(linha, coluna):
    produto = 0
    for k in range(len(linha)):
        produto = produto + (linha[k] * coluna[k])
    return produto


def main():
    global PORTA
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    for porta in candidatas_para_porta():
        try:
            servidor.bind((HOST, porta))
            PORTA = porta
            break
        except OSError:
            print("[" + agora() + "] [TRABALHADOR] Porta " + str(porta) + " ocupada, tentando proxima...", flush=True)
    else:
        print("[" + agora() + "] [TRABALHADOR] Nenhuma porta livre em " + str(PORTA_INICIAL) + "-" + str(PORTA_FINAL) + ".", flush=True)
        servidor.close()
        return

    servidor.listen()
    print("[" + agora() + "] [TRABALHADOR " + str(PORTA) + "] Aguardando coordenador em " + HOST + ":" + str(PORTA) + "...", flush=True)

    conexao = None
    try:
        while True:
            conexao, endereco = servidor.accept()

            tarefas = 0
            while True:
                pedido = receber_msg(conexao)
                if pedido is None:
                    break

                if "fim" in pedido:
                    print("[" + agora() + "] [TRABALHADOR " + str(PORTA) + "] Fim das tarefas. Encerrando conexao.\n", flush=True)
                    break

                linha = pedido["linha"]
                coluna = pedido["coluna"]
                i = pedido["i"]
                j = pedido["j"]

                if DELAY_MAX > 0:
                    time.sleep(random.uniform(0, DELAY_MAX))

                resultado = produto_escalar(linha, coluna)
                print("[" + agora() + "] [TRABALHADOR " + str(PORTA) + "] Celula [" + str(i) + "][" + str(j) + "] = " + str(resultado) + " (tarefa " + str(tarefas + 1) + ")\n", flush=True)
                tarefas = tarefas + 1

                enviar_msg(conexao, {"i": i, "j": j, "resultado": resultado})

            conexao.close()
            conexao = None
            if tarefas > 0:
                print("[" + agora() + "] [TRABALHADOR " + str(PORTA) + "] Conexao encerrada. " + str(tarefas) + " tarefas. Aguardando proximo coordenador...\n", flush=True)
    except KeyboardInterrupt:
        print("\n[" + agora() + "] [TRABALHADOR " + str(PORTA) + "] Encerrado pelo usuario.", flush=True)
    finally:
        if conexao is not None:
            try:
                conexao.close()
            except Exception:
                pass
        servidor.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[" + agora() + "] [TRABALHADOR " + str(PORTA) + "] Encerrado pelo usuario.", flush=True)