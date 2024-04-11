Aqui contem o código fonte da ferramenta de coleta, sugestões e resultados de tarefas do GitHub.

No dataset disponibilizado (na pasta backup) temos os dados utilizados para o desenvolvimento do nosso trabalho, tais como as tarefas, dos 35 repositorios, mineradas, com o número dos pullrequests e arquivos que fecharam as tarefas. 

# Preenchendo o arquivo de configuração

Para replicar este trabalho ou minerar novos dados você vai precisar criar um arquivo `config.ini` seguindo o template presente em `config.ini.example`. Você vai precisar preencher os seguintes dados:

- Seção **GITHUB**:

1. **TOKEN:** Você vai precisar criar um token de acesso [aqui](https://github.com/settings/tokens), para desenvolver este trabalho nós utilizamos o token clássico. Caso vá minerar dados apenas de projetos públicos não é necessário marcar nenhuma permissão.

- Seção **DATABASE**:

Nós utilizamos um container docker com a imagem do MongoDB para executar o trabalho.

1. **CONTAINER_NAME:** Nome do container do MongoDB, utilizado para fazer backup e restaurar o backup
2. **CONNECTION_STRING:** String para conectar com o MongoDB, não testamos strings com usuário e senha, pode ser que não funcione.
3. **NAME:** Nome do banco de dados no MongoDB, nos utilizamos o nome `evaluator`, caso altere é possível que tenha que renomear a pasta `evaluator`, dentro da pasta `backup`, para o nome passado.

- Seção **OPENAI**:

Utilizamos o ChatGPT 3.5 e 4 para fazer gerar códigos para resolver as tarefas, é possível que os mesmos prompts gerem resultados diferentes. Os códigos gerados se encontram no dataset que nós disponibilizamos (na coleção do MongoDB: jabref/jabref_gpt_results).

1. **API_KEY:** Sua chave de API do OpenAI.

# Instalando dependências

Desenvolvemos e executamos o estudo na versão do Python 3.10.8 e pip 23.1.2. 

Utilizamos de algumas bibliotecas para desenvolver este trabalho, sendo elas:

```
beautifulsoup4==4.12.3
codebleu==0.6.0
gensim==4.2.0
matplotlib==3.6.2
nltk==3.7
numpy==1.23.5
octokit==0.0.1
octokitpy==0.15.0
openai==1.16.2
pandas==1.5.1
pymongo==4.3.3
requests==2.25.1
scikit_learn==1.4.1.post1
scipy==1.13.0
seaborn==0.13.2
sentence_transformers==2.2.2
torch==1.12.1+cu116
unidiff==0.7.5
```

Você pode instalar todas as bibliotecas com o comando: `pip3 install -r requirements.txt`

# Executando

## Minerando e rodando testes

Você pode minerar e rodar testes com o comando: `python3 main.py`. 

Vai aparecer uma janela onde você configura os preprocessamentos e outras opções, sendo elas:

- **K:** O TopK, separado por vírgula.
- **Compare Data:** O que vai ser passado para os algoritmos de similaridade textual.
- **Fetch from API:** Se vai minerar os dados do GitHub ou se vai utilizar dados já minerados.
- **Use good first issues only:** Apenas tarefas boas para novatos vão ser testadas.
- **Good First Issue label:** Alguns repositórios não utilizam o nome tudo em minusculo, ou, até mesmo, usam outros nomes como por exemplo: "tarefa fácil". Coloque o nome da etiqueta que o repositório usa aqui, isso irá marcar automaticamente se a tarefa é uma tarefa boa para novato nos resultados.
- **Start date:** Tarefas criadas apartir dessa data, fazem parte do grupo de teste.
- **Days before:** Janela de tempo.
- **Closed date:** Tarefas fechadas a partir dessa data vão ser mineradas.
- **Strategy:** Qual algoritmo de similaridade textual vai usar.

A lematização não está implementada.