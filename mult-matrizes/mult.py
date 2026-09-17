# síncrona pra cada processo fazer a multiplicaçaõ de uma linha e retornar

# depois assíncrona

# depois com middleware
import numpy as np

matriz1 = [
    [0,1,3],
    [4,3,6],
    [7,8,9]
]
matriz2 = [
    [10,11,12],
    [13,14,15],
    [16,17,18]
]

# tam_m_result = len(matriz1) x len(matriz2[0])

matriz_resultado = []


def multiplicacao_matrizes(m1, m2):
    if not len(m1[0]) == len(m2):
        print("O NUMERO DE COLUNAS DE UMA É DIFERENTE DO NUMERO DE LINHAS DA OUTRA")
        return

# o servidor espera colunas da M1 x linhas da M2 vezes receber 2 vetores, pra guardar vai ser:

linha = []
coluna = []

for i in len(matriz1*matriz2[0]):
    for idx in zip(matriz1, matriz2):
        linha.append(matriz1[idx])
        coluna.append(matriz2[idx])

produto_escalar = 0
        
for i in len(linha):
    produto_escalar += (linha[i] * coluna[i]) 