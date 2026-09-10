import socket
import threading

# Classe que representa uma thread para lidar com cada cliente
class ClientThread(threading.Thread):
    def __init__(self, client_socket, address):
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.address = address
        print(f"[INFO] Conectado a {address}")

    def run(self):
        try:
            while True:
                # Recebe a mensagem do cliente
                data = self.client_socket.recv(40).decode()
                if not data:
                    break
                print(f"Recebido de {self.address}: {data}")

                processed_data = data.upper()  #operação: letras maiusculas
                processed_data = processed_data[::-1]  #operação: inverte a string
                
                # Envia uma resposta de volta ao cliente
                response = f"Resposta ao {data}: {processed_data}"
                self.client_socket.send(response.encode())

        except Exception as e:
            print(f"[ERRO] {e}")
        finally:
            self.client_socket.close()
            print(f"[INFO] Conexão com {self.address} encerrada.")



# Função principal do servidor
def start_server():
    server_port = 8000
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', server_port))
    server_socket.listen()

    print(f"[INFO] Servidor escutando na porta {server_port}...")

    # Loop principal para aceitar conexões de clientes
    while True:
        client_socket, addr = server_socket.accept()
        thread = ClientThread(client_socket, addr)
        thread.start()

# Início da execução
if __name__ == "__main__":
    start_server()
