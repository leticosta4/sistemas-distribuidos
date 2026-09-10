Controle de Nomes de Usuários (20%):

Modifique o cliente para solicitar o nome do jogador antes de conectar.

Modifique o servidor e o cliente para que os lances, anúncios de vitória e turnos exibam os nomes reais dos jogadores, substituindo mensagens genéricas (ex: "Aguarde o turno do João..." em vez de "Aguarde o turno do seu adversário...").

Sistema de Pontuação Contínua (Revanche) (30%):

Atualmente, quando uma partida termina, os terminais são encerrados (j1.finalizar()).

Altere essa lógica: ao fim de uma partida, o servidor deve perguntar a ambos os jogadores se desejam jogar novamente (revanche).

Se ambos aceitarem, uma nova partida se inicia na mesma thread, mantendo um placar contínuo (Ex: "João 2 x 1 Maria").

Se um dos jogadores recusar, a conexão é encerrada de forma amigável para ambos.

Tolerância a Falhas / Desconexão (20%):

Implemente um sistema de Timeout ou verificação contínua (ex: um bloco try/except refinado ou ping periódico).

Se um jogador fechar o terminal (CTRL+C) ou perder a conexão de rede no meio da partida, o oponente que permaneceu ativo deve ser avisado claramente ("Oponente desconectado. Você venceu por W.O.") e o estado da partida deve ser limpo da memória do servidor para evitar vazamento de memória (threads zumbis).

