"""
relogio_vetorial.py
===================

Implementacao da abstracao de RELOGIO VETORIAL (Fentress & Mattern, 1978),
usada pelos processos do sistema distribuido descrito em `relatorio.md`.

Conceito
--------
Cada processo P_i mantem um vetor V de N entradas (N = numero de processos do
sistema).  A entrada V[i] conta quantos eventos do proprio processo P_i ja
ocorreram (na pratica, quantos incrementos foram feitos).  As demais entradas
V[j] (j != i) representam o "ultimo conhecimento" que P_i tem sobre os eventos
de P_j: ou seja, o maior contador de P_j ja visto em qualquer mensagem
recebida.

Com isso e possivel decidir, comparando dois vetores, se um evento aconteceu
ANTES do outro (relacao causal / happened-before) ou se os dois sao
CONCORRENTES (nenhuma influencia causal entre eles) -- algo que a simples
ordem de chegada das mensagens NAO consegue mostrar.

Regras implementadas (as tres operacoes obrigatorias do trabalho):

  (C1) EVENTO LOCAL em P_i:
           V[i] = V[i] + 1

  (C2) ENVIO de mensagem a partir de P_i:
           a mensagem carrega uma COPIA do vetor V atual do remetente
           (feito pelo `processo.py` apos executar C1).

  (C3) RECEBIMENTO da mensagem em P_i:
           para todo j: V[j] = max(V[j], mensagem[j])   # incorpora o que o
                                                         # remetente ja sabia
           V[i] = V[i] + 1                               # o proprio recebimento
                                                         # tambem e um evento

Comparacao de eventos (usada para a analise dos logs):

  dado que a mensagem traz o vetor do evento `a` e o vetor atual (antes do
  merge) representa o estado de conhecimento do processo para o evento `b`:

      a <= b (componente a componente)  =>  a aconteceu antes de b  (a -> b)
      b <= a                            =>  b aconteceu antes de a  (b -> a)
      nenhum dos dois                   =>  a e b SAO CONCORRENTES
"""


class RelogioVetorial:
    """Um relogio vetorial de N entradas pertencente a um processo."""

    def __init__(self, id_processo: str, n: int) -> None:
        """
        Cria o relogio zerado.

        :param id_processo: identificador no formato "P1", "P2"... (o padrao
            do trabalho).  O numero do identificador define o INDICE que o
            processo incrementa: P1 -> indice 0, P2 -> indice 1, ...
        :param n: quantidade de processos do sistema (tamanho do vetor).
        """
        # "P1".lstrip("P") -> "1"; converte para indice de lista (base 0).
        self.indice = int(id_processo.strip().upper().lstrip("P")) - 1
        if not 0 <= self.indice < n:
            raise ValueError(
                f"id_processo '{id_processo}' invalido para um sistema com {n} processos"
            )
        self.n = n
        # (C1) estado inicial: nenhum evento ocorreu ainda.
        self.V = [0] * n

    # ------------------------------------------------------------------ #
    # Operacoes de atualizacao                                           #
    # ------------------------------------------------------------------ #
    def incrementar(self) -> list:
        """
        (C1) Incrementa a propria entrada do vetor apos a ocorrencia de um
        evento local (geracao de evento, envio etc.).

        :return: copia do vetor JA incrementado, pronta para ser registrada no
            log e embutida nas mensagens enviadas aos demais processos.
        """
        self.V[self.indice] += 1
        return self.copia()

    def receber(self, mensagem: list) -> tuple:
        """
        (C3) Incorpora o vetor trazido por uma mensagem recebida e entao
        incrementa a propria entrada (o recebimento tambem e um evento local).

        Passo 1 - "merge": para cada entrada j, V[j] = max(V[j], mensagem[j]).
                   Nao se faz atribuicao simples porque isso APAGARIA o
                   conhecimento local que ainda nao foi visto pelo remetente.
        Passo 2 - incremento proprio: V[i] += 1.

        :param mensagem: vetor do remetente no instante do envio.
        :return: tupla (antes, depois) com o vetor antes e depois da operacao,
                usada pelo `processo.py` para preencher o log e a analise.
        """
        antes = self.copia()
        for j in range(self.n):
            if mensagem[j] > self.V[j]:
                self.V[j] = mensagem[j]
        self.V[self.indice] += 1
        return antes, self.copia()

    def copia(self) -> list:
        """Retorna uma copia defensiva do vetor (evita efeitos colaterais)."""
        return list(self.V)

    # ------------------------------------------------------------------ #
    # Comparacao entre eventos (happen-before x concorrencia)            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def comparar(a: list, b: list) -> str:
        """
        Compara o momento em que o evento `a` ocorreu com o momento em que o
        evento `b` ocorreu, usando apenas os vetores.

        :return: um de
            - "iguais"        -> mesmo vetor (nao sao eventos distintos uteis);
            - "a antes de b"  -> a aconteceu antes de b (relacao causal a -> b);
            - "b antes de a"  -> b aconteceu antes de a (relacao causal b -> a);
            - "concorrentes"  -> nenhum aconteceu antes do outro: os dois sao
                                 independentes do ponto de vista causal.
        """
        if list(a) == list(b):
            return "iguais"
        a_menor = all(x <= y for x, y in zip(a, b))  # a <= b  =>  a -> b
        b_menor = all(y <= x for x, y in zip(a, b))  # b <= a  =>  b -> a
        if a_menor:
            return "a antes de b"
        if b_menor:
            return "b antes de a"
        return "concorrentes"  # incomparaveis: ha componentes nos dois lados

    @staticmethod
    def ocorreu_antes(a: list, b: list) -> bool:
        """Verdadeiro quando `a` aconteceu estritamente antes de `b` (a -> b)."""
        return RelogioVetorial.comparar(a, b) == "a antes de b"

    @staticmethod
    def sao_concorrentes(a: list, b: list) -> bool:
        """Verdadeiro quando nenhum dos eventos influenciou o outro."""
        return RelogioVetorial.comparar(a, b) == "concorrentes"

    # ------------------------------------------------------------------ #
    def __str__(self) -> str:
        """Representacao usada nos logs: VC=[1,0,2,3]."""
        return str(self.V)
