import argparse
import socket
import json
import time
from datetime import datetime

inicio_total = time.time()

BASE_PORTA = 8001
FIM_SCAN = 8010


def agora():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def parse_args():
    parser = argparse.ArgumentParser(description="Coordenador sincrono da multiplicacao de matrizes")
    parser.add_argument("--portas", type=int, nargs="*", default=None, help="portas dos trabalhadores. Ex: --portas 8001 8002 8003. Se omitido, detecta sozinho de 8001 a 8010")
    return parser.parse_args()


matriz1 = [
    [0, 1, 3],
    [4, 3, 6],
    [7, 8, 9]
]

matriz2 = [
    [10, 11, 12],
    [13, 14, 15],
    [16, 17, 18]
]


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


def trabalhador_no_ar(host, porta, timeout=0.2):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, porta))
        s.close()
        return True
    except Exception:
        return False


def descobrir_trabalhadores(portas):
    if portas:
        return [("localhost", p) for p in portas]
    achados = []
    for porta in range(BASE_PORTA, FIM_SCAN + 1):
        if trabalhador_no_ar("localhost", porta):
            achados.append(("localhost", porta))
    return achados


def conectar_com_retry(host, porta, tentativas=20):
    ultimo_erro = None
    for t in range(tentativas):
        try:
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.connect((host, porta))
            return c
        except Exception as e:
            ultimo_erro = e
            time.sleep(0.5)
    raise ultimo_erro


def main():
    args = parse_args()
    TRABALHADORES = descobrir_trabalhadores(args.portas)

    if len(TRABALHADORES) == 0:
        print("[" + agora() + "] [COORDENADOR] Nenhum trabalhador encontrado.")
        print("Suba ao menos um antes: python3 ServerSincrono.py 8001")
        print("Ou passe as portas: python3 ClienteSincrono.py --portas 8001 8002")
        return

    if not len(matriz1[0]) == len(matriz2):
        print("O NUMERO DE COLUNAS DE UMA E DIFERENTE DO NUMERO DE LINHAS DA OUTRA")
        return

    num_linhas = len(matriz1)
    num_colunas = len(matriz2[0])

    matriz_resultado = []
    for i in range(num_linhas):
        linha_zero = []
        for j in range(num_colunas):
            linha_zero.append(0)
        matriz_resultado.append(linha_zero)

    print("[" + agora() + "] [COORDENADOR] Trabalhadores detectados: " + str(len(TRABALHADORES)) + "\n")

    conexoes = []
    for h in range(len(TRABALHADORES)):
        host = TRABALHADORES[h][0]
        porta = TRABALHADORES[h][1]
        c = conectar_com_retry(host, porta)
        conexoes.append(c)
        print("[" + agora() + "] [COORDENADOR] Conectado ao trabalhador " + str(h) + " em " + host + ":" + str(porta) + ".\n")

    tarefa = 0
    for i in range(len(matriz1)):
        for j in range(len(matriz2[0])):
            linha = matriz1[i]

            coluna = []
            for k in range(len(matriz2)):
                coluna.append(matriz2[k][j])

            w = tarefa % len(conexoes)
            trabalhador = conexoes[w]
            porta_w = TRABALHADORES[w][1]

            print("[" + agora() + "] [COORDENADOR] >>> ENVIANDO celula [" + str(i) + "][" + str(j) + "] ao trabalhador " + str(w) + " (porta " + str(porta_w) + ") — BLOQUEADO até resposta...\n")

            enviar_msg(trabalhador, {"i": i, "j": j, "linha": linha, "coluna": coluna})

            resposta = receber_msg(trabalhador)
            matriz_resultado[resposta["i"]][resposta["j"]] = resposta["resultado"]
            print("[" + agora() + "] [COORDENADOR] <<< RECEBIDO celula [" + str(resposta["i"]) + "][" + str(resposta["j"]) + "] do trabalhador " + str(w) + " (porta " + str(porta_w) + ") = " + str(resposta["resultado"]) + " — continuando...\n")
            tarefa = tarefa + 1

    for h in range(len(conexoes)):
        enviar_msg(conexoes[h], {"fim": True})
        conexoes[h].close()

    print("[" + agora() + "] [COORDENADOR] Matriz resultante:")
    for i in range(len(matriz_resultado)):
        print(matriz_resultado[i])

    tempo_total = time.time() - inicio_total
    print("\n[" + agora() + "] [COORDENADOR] Tempo total: " + str(round(tempo_total, 3)) + "s (" + str(len(matriz1) * len(matriz2[0])) + " celulas, " + str(len(TRABALHADORES)) + " trabalhadores)\n")


if __name__ == "__main__":
    main()
