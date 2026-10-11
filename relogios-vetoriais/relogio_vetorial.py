"""
lógica do relógio vetorial pra sincronizar os processos.

cada processo tem uma lista com N posições (N = total de processos).
a posição dele conta os eventos locais que ele próprio gerou, e as outras
posições guardam o que ele já sabe dos outros processos pelas mensagens.
"""


class RelogioVetorial:
    def __init__(self, id_processo: str, n: int) -> None:
        # converte o id tipo "P1" pro índice da lista (P1 vira 0, P2 vira 1...)
        self.indice = int(id_processo.strip().upper().lstrip("P")) - 1
        if not 0 <= self.indice < n:
            raise ValueError(
                f"id_processo '{id_processo}' inválido para um sistema com {n} processos"
            )
        self.n = n
        # inicializa o vetor com zeros
        self.V = [0] * n

    def incrementar(self) -> list:
        # soma 1 na posição do próprio processo quando rola um evento local
        self.V[self.indice] += 1
        return self.copia()

    def receber(self, mensagem: list) -> tuple:
        # ao receber mensagem: pega o máximo de cada posição e soma 1 no relógio local
        antes = self.copia()
        # atualiza cada entrada pegando o maior valor entre o local e o que veio na mensagem
        for j in range(self.n):
            if mensagem[j] > self.V[j]:
                self.V[j] = mensagem[j]
        # o próprio recebimento também conta como evento, então incrementa aqui
        self.V[self.indice] += 1
        return antes, self.copia()

    def copia(self) -> list:
        # retorna uma cópia da lista pra não alterar a original sem querer
        return list(self.V)

    @staticmethod
    def comparar(a: list, b: list) -> str:
        # compara dois vetores pra saber quem aconteceu antes ou se rolou concorrência
        if list(a) == list(b):
            return "iguais"
        a_menor = all(x <= y for x, y in zip(a, b))  # a <= b
        b_menor = all(y <= x for x, y in zip(a, b))  # b <= a
        if a_menor:
            return "a antes de b"
        if b_menor:
            return "b antes de a"
        # se nenhum é menor que o outro em todas as posições, são concorrentes
        return "concorrentes"

    @staticmethod
    def ocorreu_antes(a: list, b: list) -> bool:
        # diz se o evento 'a' aconteceu antes do 'b'
        return RelogioVetorial.comparar(a, b) == "a antes de b"

    @staticmethod
    def sao_concorrentes(a: list, b: list) -> bool:
        # diz se dois eventos são concorrentes
        return RelogioVetorial.comparar(a, b) == "concorrentes"

    def __str__(self) -> str:
        return str(self.V)
