import argparse
import socket
import json
import time
import threading
import queue

# Cada trabalhador e um processo separado (ServerAssincrono.py) numa porta.
# Voce sobe quantos quiser, o cliente descobre sozinho:
#   python3 ServerAssincrono.py 8001
#   python3 ServerAssincrono.py 8002
#   python3 ServerAssincrono.py 8003
#   python3 ClienteAssincrono.py
# Ou avisa as portas direto:
#   python3 ClienteAssincrono.py --portas 8001 8002 8003
BASE_PORTA = 8001
FIM_SCAN = 8010


def parse_args():
    parser = argparse.ArgumentParser(description="Coordenador assincrono da multiplicacao de matrizes")
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


def trabalhador_no_ar(host, porta, timeout=0.2):
    # probe rapido: so diz se tem um trabalhador ouvindo ali
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


def rotina_trabalhador(h, host, porta, tarefas_h, fila_resultados):
    # roda numa thread propria: cada thread fala com um trabalhador em paralelo.
    # o recv aqui bloqueia SO esta thread; as outras continuam enviando/recebendo.
    conexao = conectar_com_retry(host, porta)
    for t in range(len(tarefas_h)):
        i = tarefas_h[t][0]
        linha = tarefas_h[t][1]
        j = tarefas_h[t][2]
        coluna = tarefas_h[t][3]
        enviar_msg(conexao, {"i": i, "j": j, "linha": linha, "coluna": coluna})
        resposta = receber_msg(conexao)
        fila_resultados.put((h, resposta))
    enviar_msg(conexao, {"fim": True})
    conexao.close()


def main():
    args = parse_args()
    TRABALHADORES = descobrir_trabalhadores(args.portas)

    if len(TRABALHADORES) == 0:
        print("[COORDENADOR] Nenhum trabalhador encontrado.")
        print("Suba ao menos um antes: python3 ServerAssincrono.py 8001")
        print("Ou passe as portas: python3 ClienteAssincrono.py --portas 8001 8002")
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

    # monta a lista de tarefas: cada uma tem a linha i da matriz1
    # e a coluna j da matriz2, usando [] e indices
    todas_tarefas = []
    for i in range(len(matriz1)):
        for j in range(len(matriz2[0])):
            linha = matriz1[i]
            coluna = []
            for k in range(len(matriz2)):
                coluna.append(matriz2[k][j])
            todas_tarefas.append([i, linha, j, coluna])

    # distribui as tarefas entre os N trabalhadores (round-robin).
    # diferente do sincrono, aqui NAO espera resposta: so separa os lotes.
    tarefas_por_trabalhador = []
    for h in range(len(TRABALHADORES)):
        tarefas_por_trabalhador.append([])
    for t in range(len(todas_tarefas)):
        w = t % len(TRABALHADORES)
        tarefas_por_trabalhador[w].append(todas_tarefas[t])

    for h in range(len(TRABALHADORES)):
        print("[COORDENADOR] Trabalhador " + str(h) + " (" + TRABALHADORES[h][0] + ":" + str(TRABALHADORES[h][1]) + ") recebe " + str(len(tarefas_por_trabalhador[h])) + " tarefas.\n")

    # ASSINCRONO: uma thread por trabalhador envia sem esperar as outras.
    # a thread principal coleta pela fila conforme as respostas CHEGAM
    # (fora de ordem e diferente da ordem de envio).
    fila_resultados = queue.Queue()
    threads = []
    for h in range(len(TRABALHADORES)):
        th = threading.Thread(target=rotina_trabalhador, args=(h, TRABALHADORES[h][0], TRABALHADORES[h][1], tarefas_por_trabalhador[h], fila_resultados))
        th.start()
        threads.append(th)

    for n in range(len(todas_tarefas)):
        h, resposta = fila_resultados.get()
        matriz_resultado[resposta["i"]][resposta["j"]] = resposta["resultado"]
        print("[COORDENADOR] Chegada " + str(n + 1) + "/" + str(len(todas_tarefas)) + ": celula [" + str(resposta["i"]) + "][" + str(resposta["j"]) + "] feita pelo trabalhador " + str(h) + " = " + str(resposta["resultado"]) + "\n")

    for h in range(len(threads)):
        threads[h].join()

    print("[COORDENADOR] Matriz resultante:")
    for i in range(len(matriz_resultado)):
        print(matriz_resultado[i])


if __name__ == "__main__":
    main()
