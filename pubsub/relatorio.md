# Intermediário PubSUb

>
> Alunas: Letícia Almeida e Sophia Lima
>

## Arquitetura

O sistema segue o modelo Pub/Sub clássico com comunicação indireta: publisher e subscriber nunca se conectam diretamente, tudo passa pelo intermediário.

```mermaid
graph LR
    P[Publisher] -->|publicar| I[Intermediário<br/>Tópicos / Inscrições]
    S[Subscriber] -->|registrar_subscriber<br/>inscrever| I
    I -->|receber_msg| S
```


Todos os 3 processos são objetos Pyro5, registrados no Name Server (NS). Cada processo se registra no NS com um nome lógico (`"intermediario"`, `"subscriber.S1"`, etc) e quem precisa falar com ele consulta o NS pra achar a URI atual, sem precisar saber IP/porta de ninguém na mão.

## Descrição dos processos
**Intermediário** (`intermediario.py`): único processo "central" do sistema. Sabe sobre os tópicos existentes, os subscribers registrados e as inscrições de cada um. Fica com `daemon.requestLoop()` rodando indefinidamente, esperando chamadas de publishers e subscribers. 
 
**Publisher** (`publisher.py`): funciona como um cliente, não expõe nada e não sobe daemon próprio — só localiza o intermediário via NS para fazer as publicações. Roda em loop até o usuário digitar `"sair"`, permitindo publicar várias mensagens numa mesma sessão para diferentes tópicos. Não conhece nenhum subscriber, só manda a mensagem pro intermediário.
 
**Subscriber** (`subscriber.py`): é cliente e servidor ao mesmo tempo. Cliente porque se registra e se inscreve chamando métodos do intermediário; servidor porque precisa expor um objeto remoto pra que o intermediário consiga chamá-lo de volta quando chegar uma mensagem de interesse. Por isso sobe seu próprio `daemon` e se registra no NS com um nome único (`subscriber.<id>`), senão dois subscribers rodando ao mesmo tempo colidiriam no NS.

O intermediario encaminha as msgs recebidas do publisher para os subscribers de acordo com o topico vinculado. Publishers e Subscribers não sabem um do outro, a única relação em comum é o nome do tópico


## Descrição dos métodos remotos
Todos ficam expostos na classe `Intermediario`, com `@Pyro5.api.expose`:
 
- **`criar_topico(nome)`**: adiciona o tópico no set `self.topicos` e cria uma entrada vazia em `self.inscricoes`. Não precisa ser chamado manualmente por ninguém — é chamado internamente pelo próprio `inscrever()` quando o tópico ainda não existe, já que no Pub/Sub o tópico não é "reservado" antes por ninguém, ele só existe por convenção de nome entre quem publica e quem assina.
- **`registrar_subscriber(id_subscriber)`**: adiciona o id no set `self.subscribers`. É chamado pelo subscriber assim que ele sobe, antes de se inscrever em qualquer tópico.
- **`inscrever(id_subscriber, topico)`**: associa o id do subscriber ao tópico. Essa estrutura é um dict `{topico: {ids de subscribers}}`, então múltiplos subscribers podem estar no mesmo tópico e um mesmo subscriber pode estar em vários tópicos.
- **`publicar(id_publisher, topico, mensagem)`**: recebe a mensagem do publisher e dispara o encaminhamento (ver seção abaixo).


## Encaminhamento das mensagens

Quando `publicar()` é chamado, o intermediário busca em `self.inscricoes` a lista de ids inscritos naquele tópico. Pra cada um, ele:
 
1. Faz `self.ns.lookup(f"subscriber.{id_subscriber}")` pra achar a URI atual daquele subscriber no NS (por isso o nome de registro do subscriber segue esse padrão fixo — é assim que o intermediário sabe onde procurar sem guardar a URI manualmente).
2. Cria um `Pyro5.api.Proxy(uri)` novo pra esse subscriber.
3. Chama `proxy.receber_msg(topico, id_publisher, mensagem)`.
O `try/except` em volta dessa chamada existe pra que, se um subscriber tiver caído (processo fechado mas ainda registrado), a falha no envio pra ele não impeça o envio pros demais inscritos no mesmo tópico — o loop continua normalmente.


## Uso do Pyro5
- **Name Server**: usado pelos três processos. Intermediário registra `"intermediario"`; cada subscriber registra `"subscriber.<id>"`. Publisher e subscriber usam `locate_ns()` + `lookup()` pra achar o intermediário; o intermediário usa o NS internamente pra achar cada subscriber na hora de publicar.
- **`@Pyro5.api.expose`**: usado nas classes `Intermediario` e `Subscriber` pra marcar os métodos como chamáveis remotamente.
- **`daemon.requestLoop()`**: usado no intermediário e no subscriber (os dois processos que precisam *receber* chamadas, e não só fazer). O publisher não precisa, porque só faz chamadas, nunca recebe.
- **Callback remoto**: o subscriber expõe `receber_msg` justamente pra funcionar como callback — é o intermediário que chama esse método, nunca o subscriber chama ele mesmo. Isso é o que fecha o ciclo do Pub/Sub sem o publisher nunca precisar conhecer o subscriber.

Extra: na primeira versão, o método `publicar()` usava `self.ns` (o proxy do Name Server, criado no `main()`) diretamente, e ao executar tudo junto, depois de o Publisher enviar uma msg, o erro seguinte era emitido: `the calling thread is not the owner of this proxy, create a new proxy in this thread or transfer ownership.` Isso acontece porque, por padrão, o Pyro5 processa cada chamada remota recebida numa thread separada — e o próprio changelog oficial do Pyro5 documenta essa mudança de comportamento: a partir da v5, "*proxy doesn't have a thread lock anymore and no can longer be shared across different threads. A single thread is the sole 'owner' of a proxy*" ([fonte](https://pypi.org/project/Pyro5/5.0/)). Ou seja: o `self.ns` foi criado na thread principal (dentro do `main()`), mas quando `publicar()` roda numa chamada remota, ele executa numa thread diferente do daemon — e essa thread não é "dona" do proxy. A solução aplicada foi usar o mecanismo que o próprio Pyro5 disponibiliza pra esse caso, `_pyroClaimOwnership()`, chamado logo no início de `publicar()`. Isso transfere a posse do proxy pra thread que está processando aquela chamada específica, sem precisar recriar o proxy do NS a cada publicação nem desabilitar a concorrência do daemon.


## Exemplos de execução
Como rodar:
```bash
python -m Pyro5.nameserver
python intermediario.py
python subscriber.py #digite id e topicos de interesse para acompanhar
python publisher.py #digite id e topico a ser publicado com uma msg
```

Caso para testar múltiplos subscribers e publishers, dividos por assunto:

- `S1` se inscreve no tópico `positivo`
- `S2` se inscreve no tópico `negativo`
- `P1` publica mensagens em `positivo`
- `P2` publica mensagens em `negativo`

O resultado esperado é `S1` só receber as mensagens publicadas por `P1` em `positivo`, e `S2` só receber as de `P2` em `negativo` — mesmo os dois publishers e os dois subscribers estando ativos ao mesmo tempo, o intermediário encaminha só pra quem está inscrito no tópico certo.


## Breve discussão: comunicação indireta e desacoplamento

O ponto central do trabalho é que publisher e subscriber nunca têm um proxy um do outro — nenhum dos dois conhece o endereço, o processo ou sequer a existência do outro lado. Toda a comunicação passa pelo intermediário, que resolve em tempo real, via Name Server, pra onde encaminhar cada mensagem. Isso caracteriza o **desacoplamento espacial**: nenhuma das partes precisa guardar ou trocar uma referência direta da outra. Na prática, isso significa que publisher e subscriber podem rodar em máquinas diferentes sem nenhuma configuração de rede um sabendo do outro — só precisam conhecer o intermediário. Também é o que permite um publisher publicar num tópico mesmo que nenhum subscriber esteja inscrito nele ainda (a mensagem simplesmente não é entregue a ninguém) e um subscriber se inscrever num tópico que nenhum publisher jamais usou — nenhum dos dois precisa da existência confirmada do outro pra funcionar.

A limitação consciente dessa implementação está no **desacoplamento temporal**: publisher e subscriber, idealmente, não precisariam estar ativos ao mesmo tempo pra o sistema funcionar — mas aqui, como não existe persistência de dados, um subscriber só recebe o que for publicado *depois* da sua inscrição. Se ele entrar depois de uma publicação, ela já se perdeu. Sistemas de mensageria reais (como o Kafka, usado no trabalho da empresa) resolvem isso guardando um log persistente das mensagens, permitindo que subscribers consumam publicações antigas mesmo tendo entrado depois. Isso não foi implementado aqui porque o próprio enunciado dispensa explicitamente mecanismos de persistência e filas avançadas, mantendo o foco no desacoplamento espacial — que é o que a comunicação indireta via intermediário realmente resolve.
