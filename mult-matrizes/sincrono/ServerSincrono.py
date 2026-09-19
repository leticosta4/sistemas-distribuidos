import socket
import json
import sys

HOST = "localhost"
# cada processo trabalhador roda em uma porta diferente:
#   python3 ServerSincrono.py 8001
#   python3 ServerSincrono.py 8002
PORTA = int(sys.argv[1]) if len(sys.argv) > 1 else 8001


def receber_msg(conexao):
    # protocolo cru: cada mensagem JSON termina com \n
    dados = b""
    while True:
        parte = conexao.recv(1024)
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
    # calculo cru, iterando com [] e indices, sem numpy
    produto = 0
    for k in range(len(linha)):
        produto = produto + (linha[k] * coluna[k])
    return produto


def main():
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind((HOST, PORTA))
    servidor.listen()
    print("[TRABALHADOR " + str(PORTA) + "] Aguardando coordenador em " + HOST + ":" + str(PORTA) + "...", flush=True)

    conexao = None
    try:
        while True:
            conexao, endereco = servidor.accept()

            tarefas = 0
            while True:
                pedido = receber_msg(conexao)
                if pedido is None:
                    break

                # sinal de fim enviado pelo coordenador
                if "fim" in pedido:
                    print("[TRABALHADOR " + str(PORTA) + "] Fim das tarefas. Encerrando conexao.\n", flush=True)
                    break

                linha = pedido["linha"]
                coluna = pedido["coluna"]
                i = pedido["i"]
                j = pedido["j"]

                resultado = produto_escalar(linha, coluna)
                print("[TRABALHADOR " + str(PORTA) + "] Celula [" + str(i) + "][" + str(j) + "] linha=" + str(linha) + " coluna=" + str(coluna) + " = " + str(resultado) + "\n", flush=True)
                tarefas = tarefas + 1

                enviar_msg(conexao, {"i": i, "j": j, "resultado": resultado})

            conexao.close()
            conexao = None
            # conexao de teste (probe) fecha sem mandar tarefa: nao polui o log
            if tarefas > 0:
                print("[TRABALHADOR " + str(PORTA) + "] Conexao encerrada. Aguardando proximo coordenador...\n", flush=True)
    except KeyboardInterrupt:
        print("\n[TRABALHADOR " + str(PORTA) + "] Encerrado pelo usuario.", flush=True)
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
        print("\n[TRABALHADOR " + str(PORTA) + "] Encerrado pelo usuario.", flush=True)
