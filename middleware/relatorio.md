# Relatório Técnico

### A.1) Explique a importância e o funcionamento da linha instancia_servidor = ServidorJogo() na função main() do servidor, contrastando com o registro direto da classe. O que aconteceria (em termos de gerência de estado) se registrássemos a classe diretamente no Daemon, sem instanciá-la?

A instância do objeto servidor é o que permite a existência do mesmo e funcionamento do projeto inicialmente, criando também uma fila a ser compartilhada pelos clientes - esse memso objeto será usado pelo Pyro para todas as chamadas remotas. 
Se a classe fosse passada diretamente no register(), o Pyro criaria novas instâncias para cada request para lidar com as chamadas remotas de acordo com o "Modo de instância" setado via código na classe (decorator @expose). Fonte: https://pyro5.readthedocs.io/en/latest/api/server.html#Pyro5.server.Daemon.register

### A.2) No método iniciar_jogo do servidor, o código armazena na fila a string (jogador_uri) ao invés do objeto Proxy já instanciado. Qual erro de concorrência inerente ao Pyro5 essa decisão evita na arquitetura multithread adotada?
O Pyro amarra o objeto Proxy à thread que o criou. Se fosse instanciado ali em vez da uri, a thread da partida (que roda em background) não terá
permissão para usá-lo, e ao iniciar novos jogos tentaria criar outros Proxy associados a thread principal do daemon, o que dá comportamento indefinido.


### A.3) No cliente.py, o método fazer_jogada utiliza o conceito de sinalização e espera (set() e wait()) através de threading.Event. Por que não foi possível utilizar um simples comando input() diretamente dentro deste método? Qual seria o impacto na comunicação de rede (RPC)?
O input() do python é uma operação de I/O bloqueante, não termina até o usuário digitar e mandar o input, o que trava o processador de chamadas remotas do pyro. Então o sistema ficaria travado, impedindo que o Pyro devolva o controle ao servidor até que o usuário (cliente) digite a jogada no terminal, o que bloqueia o daemon do Pyro de receber chamadas RPC (como receber_mensagens ou outros jogos/jogadores).
