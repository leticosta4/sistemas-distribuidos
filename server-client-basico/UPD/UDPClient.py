import socket

def main():
    server_address = "127.0.0.1"  # Endereço IP do servidor (localhost)
    server_port = 8000            # Porta usada pelo servidor

    # Cria um socket UDP
    # AF_INET → protocolo IP versão 4 (IPv4)
    # SOCK_DGRAM → usa UDP
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        while True:
            # Solicita ao usuário uma mensagem para enviar
            mensagem = input("digite uma string pra o servidor (ou 'sair' para encerrar): ")

            if mensagem.lower() == 'sair':
                print("[INFO] Encerrando conexão com o servidor.")
                break  # Sai do loop e fecha a conexão

            # Envia a mensagem codificada em bytes para o servidor
            # .sendto() recebe dois parâmetros:
            #   1. mensagem codificada (em bytes)
            #   2. tupla com (IP do servidor, porta)
            client_socket.sendto(mensagem.encode(), (server_address, server_port))

            # Aguarda a resposta do servidor (até 40 bytes)
            # recvfrom retorna a mensagem e o endereço do servidor
            resposta, _ = client_socket.recvfrom(40)

            # Exibe a resposta, decodificando de bytes para string
            print("Recebida:", resposta.decode())

    except Exception as e:
        # Em caso de erro, mostra a mensagem correspondente
        print("Erro:", e)

    finally:
        # Fecha o socket e encerra a comunicação
        client_socket.close()

if __name__ == "__main__":
    main()
