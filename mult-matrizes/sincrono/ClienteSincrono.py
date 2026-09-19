import argparse
import socket
import json
import time

# Cada trabalhador e um processo separado (ServerSincrono.py) numa porta.
# Voce sobe quantos quiser, o cliente descobre sozinho:
#   python3 ServerSincrono.py 8001
#   python3 ServerSincrono.py 8002
#   python3 ServerSincrono.py 8003
#   python3 ClienteSincrono.py
# Ou avisa as portas direto:
#   python3 ClienteSincrono.py --portas 8001 8002 8003

BASE_PORTA = 8001
FIM_SCAN = 8010


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


def trabalhador_no_ar(host, porta, timeout=0.2):
    # verifica se já tem um worker naquela porta
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, porta))
        s.close()
        return True
    except Exception:
        return False


def descobrir_trabalhadores(portas):
    # se o usuario passou --portas, usa exatamente essas.
    # senao, escaneia BASE_PORTA..FIM_SCAN e pega todas que responderem.
    if portas:
        return [("localhost", p) for p in portas]
    achados = []
    for porta in range(BASE_PORTA, FIM_SCAN + 1):
        if trabalhador_no_ar("localhost", porta):
            achados.append(("localhost", porta))
    return achados


def conectar_com_retry(host, porta, tentativas=20):
    # espera o trabalhador caso ele tenha sido aberto com atraso
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
        print("[COORDENADOR] Nenhum trabalhador encontrado.")
        print("Suba ao menos um antes: python3 ServerSincrono.py 8001")
        print("Ou passe as portas: python3 ClienteSincrono.py --portas 8001 8002")
        return

    if not len(matriz1[0]) == len(matriz2):
        print("O NUMERO DE COLUNAS DE UMA E DIFERENTE DO NUMERO DE LINHAS DA OUTRA")
        return

    num_linhas = len(matriz1)
    num_colunas = len(matriz2[0])

    # cria a matriz resultado zerada, usando [] e indices
    matriz_resultado = []
    for i in range(num_linhas):
        linha_zero = []
        for j in range(num_colunas):
            linha_zero.append(0)
        matriz_resultado.append(linha_zero)

    print("[COORDENADOR] Trabalhadores detectados: " + str(len(TRABALHADORES)) + "\n")

    # conecta em todos os processos trabalhadores (com espera)
    conexoes = []
    for h in range(len(TRABALHADORES)):
        host = TRABALHADORES[h][0]
        porta = TRABALHADORES[h][1]
        c = conectar_com_retry(host, porta)
        conexoes.append(c)
        print("[COORDENADOR] Conectado ao trabalhador " + str(h) + " em " + host + ":" + str(porta) + ".\n")

    # distribuicao SINCRONA entre os N trabalhadores (round-robin):
    # envia uma tarefa e aguarda a resposta antes de prosseguir
    tarefa = 0
    for i in range(len(matriz1)):
        for j in range(len(matriz2[0])):
            # pega a linha i da matriz1 usando []
            linha = matriz1[i]

            # monta a coluna j da matriz2 usando [] e indices
            coluna = []
            for k in range(len(matriz2)):
                coluna.append(matriz2[k][j])

            # escolhe qual processo trabalhador recebe esta tarefa
            w = tarefa % len(conexoes)
            trabalhador = conexoes[w]
            porta_w = TRABALHADORES[w][1]

            enviar_msg(trabalhador, {"i": i, "j": j, "linha": linha, "coluna": coluna})

            # SINCRONO: bloqueia aqui ate o trabalhador responder
            resposta = receber_msg(trabalhador)
            matriz_resultado[resposta["i"]][resposta["j"]] = resposta["resultado"]
            print("[COORDENADOR] Celula [" + str(resposta["i"]) + "][" + str(resposta["j"]) + "] feita pelo trabalhador " + str(w) + " (porta " + str(porta_w) + ") linha=" + str(linha) + " coluna=" + str(coluna) + " = " + str(resposta["resultado"]) + "\n")
            tarefa = tarefa + 1

    for h in range(len(conexoes)):
        enviar_msg(conexoes[h], {"fim": True})
        conexoes[h].close()

    print("[COORDENADOR] Matriz resultante:")
    for i in range(len(matriz_resultado)):
        print(matriz_resultado[i])


if __name__ == "__main__":
    main()
