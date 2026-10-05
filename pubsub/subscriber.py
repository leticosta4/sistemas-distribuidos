import Pyro5.api


@Pyro5.api.expose
class Subscriber(object):
    def receber_msg(self, topico, publisher_id, msg):
        print(f"\n[MENSAGEM RECEBIDA] Topico: {topico} | Publisher: {publisher_id} | Mensagem: {msg}\n")


def main():
    id_subscriber = input("Informe seu ID (ex: S1): ")

    #sobe um daemon aqui tb pq subscriber tb precisa de servidor para que intermediario encaminhe a msg do publisher
    daemon = Pyro5.api.Daemon()
    ns = Pyro5.api.locate_ns()
    instancia = Subscriber()
    uri = daemon.register(instancia)

    #registra a URI com nome de acordo com ID, para diferenciar no intermediario
    ns.register(f"subscriber.{id_subscriber}", uri)
    print("[SUBSCRIBER] Subscriber registrado no NS")

    #conexão no intermediario e registro do sub
    uri_intermed = ns.lookup("intermediario")
    intermed = Pyro5.api.Proxy(uri_intermed)
    intermed.registrar_subscriber(id_subscriber) 

    #inscrição dos topicos
    topicos_interesse = input("informe os topicos de interesse, separados por virgula: ")
    for topico in [t.strip() for t in topicos_interesse.split(",") if t.strip()]:
        intermed.inscrever(id_subscriber, topico)

    print("[SUBSCRIBER] Aguardando msg...")

    # trava aguardanddo callback do intermediario
    daemon.requestLoop()


if __name__ == "__main__":
    main()
