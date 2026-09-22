import argparse
import socket
import time
import rpyc
from datetime import datetime

inicio_total = time.time()

BASE_PORTA = 8001
FIM_SCAN = 8100


def agora():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def parse_args():
    parser = argparse.ArgumentParser(description="Coordenador da multiplicacao de matrizes (rpyc)")
    parser.add_argument("--portas", type=int, nargs="*", default=[], help="portas dos trabalhadores. Ex: --portas 8001 8002 8003 (se nao passado, scan automático a partir de 8001)")
    return parser.parse_args()


# Matrizes 3x3 de exemplo (mesmas do sincrono/assincrono)
matriz1 = [
    [0, 1, 3],
    [4, 3, 6],
    [7, 8, 9],
]

matriz2 = [
    [10, 11, 12],
    [13, 14, 15],
    [16, 17, 18],
]


# Verifica se tem algum trabalhador rpyc respondendo na porta
def trabalhador_no_ar(host, porta, timeout=0.2):
    try:
        s = socket.create_connection((host, porta), timeout=timeout)
        s.close()
        c = rpyc.connect(host, porta)
        c.root.tamanho()
        c.close()
        return True
    except Exception:
        return False


# Descobre trabalhadores pelas portas passadas ou escaneando 8001-8100
def descobrir_trabalhadores(portas):
    if portas:
        return [("localhost", p) for p in portas]
    achados = []
    for porta in range(BASE_PORTA, FIM_SCAN + 1):
        if trabalhador_no_ar("localhost", porta):
            achados.append(("localhost", porta))
    return achados


# Tenta conectar com retry (trabalhador pode ainda estar subindo)
def conectar_com_retry(host, porta, tentativas=20):
    ultimo_erro = None
    for t in range(tentativas):
        try:
            c = rpyc.connect(host, porta)
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
        print("Suba ao menos um antes: python3 TrabalhadorMatriz.py 8001")
        print("Ou especifique portas: python3 ClienteMatriz.py --portas 8001 8002")
        return

    if not len(matriz1[0]) == len(matriz2):
        print("O NUMERO DE COLUNAS DE UMA E DIFERENTE DO NUMERO DE LINHAS DA OUTRA")
        return

    print("[" + agora() + "] [COORDENADOR] Trabalhadores detectados: " + str(len(TRABALHADORES)) + "\n")

    # Conecta a cada trabalhador via rpyc
    conexoes = []
    for h in range(len(TRABALHADORES)):
        host = TRABALHADORES[h][0]
        porta = TRABALHADORES[h][1]
        c = conectar_com_retry(host, porta)
        conexoes.append(c)
        print("[" + agora() + "] [COORDENADOR] Conectado ao trabalhador " + str(h) + " em " + host + ":" + str(porta) + ".\n")

    # Inicializa matriz resultado com zeros
    matriz_resultado = []
    for i in range(len(matriz1)):
        linha_zero = []
        for j in range(len(matriz2[0])):
            linha_zero.append(0)
        matriz_resultado.append(linha_zero)

    # Distribui as celulas (round-robin); a chamada rpyc e bloqueante
    tarefa = 0
    for i in range(len(matriz1)):
        for j in range(len(matriz2[0])):
            linha = matriz1[i]

            coluna = []
            for k in range(len(matriz2)):
                coluna.append(matriz2[k][j])

            w = tarefa % len(conexoes)
            porta_w = TRABALHADORES[w][1]

            print(
                "[" + agora() + "] [COORDENADOR] >>> ENVIANDO celula [" + str(i) + "][" + str(j) +
                "] ao trabalhador " + str(w) + " (porta " + str(porta_w) + ") — BLOQUEADO até resposta...\n",
                flush=True,
            )

            # Chamada remota: o middleware abstrai a rede
            resultado = conexoes[w].root.produto_escalar(linha, coluna)
            matriz_resultado[i][j] = resultado

            print(
                "[" + agora() + "] [COORDENADOR] <<< RECEBIDO celula [" + str(i) + "][" + str(j) +
                "] do trabalhador " + str(w) + " (porta " + str(porta_w) + ") = " + str(resultado) +
                " — continuando...\n",
                flush=True,
            )
            tarefa = tarefa + 1

    # Encerra trabalhadores e fecha conexões
    for h in range(len(conexoes)):
        try:
            conexoes[h].root.encerrar()
        except Exception:
            pass
        conexoes[h].close()
        print("[" + agora() + "] [COORDENADOR] Conexao com trabalhador " + str(h) + " encerrada.", flush=True)

    print("[" + agora() + "] [COORDENADOR] Matriz resultante:")
    for i in range(len(matriz_resultado)):
        print(matriz_resultado[i])

    tempo_total = time.time() - inicio_total
    print(
        "\n[" + agora() + "] [COORDENADOR] Tempo total: " + str(round(tempo_total, 3)) +
        "s (" + str(len(matriz1) * len(matriz2[0])) + " celulas, " + str(len(TRABALHADORES)) + " trabalhadores)\n",
    )
    print("[" + agora() + "] [COORDENADOR] Encerrou.")


if __name__ == "__main__":
    main()
