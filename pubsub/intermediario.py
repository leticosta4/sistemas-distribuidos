import Pyro5.api


@Pyro5.api.expose
class Intermediario(object):
    def __init__(self, ns):
        self.ns = ns #pra localizar subscribers
        self.topicos = set()   
        self.inscricoes = {}  #referente a um topico especifico: {topico: (subscribers inscritos)}
        self.subscribers = set()  #ids de subscribers que já se registraram


    def criar_topico(self, nome):
        self.topicos.add(nome)
        self.inscricoes.setdefault(nome, set()) #é um espaço para registros, mas não grava o subscriber aqui ainda
        print(f"[INTERMEDIARIO] Topico criado: {nome}")


    def registrar_subscriber(self, id_subscriber):
        self.subscribers.add(id_subscriber)
        print(f"[INTERMEDIARIO] Subscriber registrado: {id_subscriber}")


    def inscrever(self, id_subscriber, topico): 
        if topico not in self.topicos: #cria o topico automaticamente se ainda nao existir
            self.criar_topico(topico)

        self.inscricoes[topico].add(id_subscriber)
        print(f"[INTERMEDIARIO] {id_subscriber} inscrito em {topico}")


    def publicar(self, id_publisher, topico, mensagem):
        self.ns._pyroClaimOwnership()  # reivindica o proxy pra thread atual antes de usá-lo, evitando o erro: 'the calling thread is not the owner of this proxy, create a new proxy in this thread or transfer ownership.'
        print(f"[INTERMEDIARIO] Publicacao recebida de {id_publisher} em {topico}: {mensagem}")
        inscritos = self.inscricoes.get(topico, set())
        
        for id_subscriber in inscritos:
            try:
                uri = self.ns.lookup(f"subscriber.{id_subscriber}") #localiza a URI atual do subscriber no NS
                proxy = Pyro5.api.Proxy(uri)
                proxy.receber_msg(topico, id_publisher, mensagem) #encaminha a msg recebida do publisher para os subscribers interessados no topico
            except Exception as e:
                # se um subscriber caiu, nao trava o encaminhamento pros outros
                print(f"[INTERMEDIARIO] Falha ao enviar para {id_subscriber}: {e}")

####
def main():
    # Inicialização do middleware RPC
    daemon = Pyro5.api.Daemon()
    ns = Pyro5.api.locate_ns()

    instancia = Intermediario(ns) #para que em publicar o objeto ns já seja acessivel

    #registro da instancia já criada no Pyro, ele usa este mesmo objeto para todas as chamadas.
    uri = daemon.register(instancia)

    # Registra a URI no Servidor de Nomes global para os clientes (pubs, subs) localizarem
    ns.register("intermediario", uri)

    print(
        "[INTERMEDIARIO] Servidor intermediario registrado no Name Server e aguardando publishers e subsccribers..."
    )
    daemon.requestLoop() #inicia o loop de escuta


if __name__ == "__main__":
    main()
