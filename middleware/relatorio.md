# Relatório Técnico

### A.1) Explique a importância e o funcionamento da linha instancia_servidor = ServidorJogo() na função main() do servidor, contrastando com o registro direto da classe. O que aconteceria (em termos de gerência de estado) se registrássemos a classe diretamente no Daemon, sem instanciá-la?

### A.2) No método iniciar_jogo do servidor, o código armazena na fila a string (jogador_uri) ao invés do objeto Proxy já instanciado. Qual erro de concorrência inerente ao Pyro5 essa decisão evita na arquitetura multithread adotada?

### A.3) No cliente.py, o método fazer_jogada utiliza o conceito de sinalização e espera (set() e wait()) através de threading.Event. Por que não foi possível utilizar um simples comando input() diretamente dentro deste método? Qual seria o impacto na comunicação de rede (RPC)?