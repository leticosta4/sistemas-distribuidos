import Pyro5.api


def main():
    ns = Pyro5.api.locate_ns()
    uri_intermed = ns.lookup("intermediario")
    intermed = Pyro5.api.Proxy(uri_intermed)

    id_publisher = input("Informe seu ID de publisher (ex: P1): ")

    #loop simples: publica varias mensagens ate o usuario digitar "sair"
    while True:
        topico = input("\ninforme o topico ou digite 'sair' para encerrar: ")
        if topico.lower() == "sair":
            break

        mensagem = input("Mensagem: ")
        intermed.publicar(id_publisher, topico, mensagem)


if __name__ == "__main__":
    main()
