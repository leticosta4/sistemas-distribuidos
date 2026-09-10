import socket

# Função principal do cliente
def start_client():
    server_address = '127.0.0.1'
    server_port = 8000

    # Criação do socket TCP e conexão com o servidor
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((server_address, server_port))
        print("[INFO] Conectado ao servidor.")

        while True:
            message = input("digite uma string pra o servidor (ou 'sair' para encerrar): ")

            if message.lower() == 'sair': #opcao de encerrar
                print("[INFO] Encerrando conexão com o servidor.")
                break

            client_socket.send(message.encode())
                        
            # Aguarda resposta do servidor
            data = client_socket.recv(1024).decode()
            print(f"Recebido: {data}")

# Início da execução
if __name__ == "__main__":
    start_client()


"""

dupla: Letícia Almeida e Kaik Costa
preferencia: TCP, já que o UDP é mais apropriado pra transmissões como
streaming de vídeo ou áudio, com foco em velocidade. O TCP é mais confiável
para aplicações que exigem entrega garantida de dados.

"""