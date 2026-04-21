Aqui contém o código fonte da ferramenta de coleta, sugestões e resultados de tarefas do GitHub.

No dataset disponibilizado (na pasta backup) temos os dados utilizados para o desenvolvimento do nosso trabalho, tais como as tarefas, dos 35 repositórios, mineradas, com o número dos pullrequests e arquivos que fecharam as tarefas.

# Preenchendo o arquivo de configuração

Para replicar este trabalho ou minerar novos dados você vai precisar criar um arquivo `config.ini` seguindo o template presente em `config.ini.example`. Você vai precisar preencher os seguintes dados:

- **GITHUB**:

1. **TOKEN:** Você vai precisar criar um token de acesso [aqui](https://github.com/settings/tokens), para desenvolver este trabalho nós utilizamos o token clássico. Caso vá minerar dados apenas de projetos públicos não é necessário marcar nenhuma permissão.

- **DATABASE**:

Nós utilizamos um container docker com a imagem do MongoDB para executar o trabalho.

1. **CONTAINER_NAME:** Nome do container do MongoDB, utilizado para fazer backup e restaurar o backup
2. **CONNECTION_STRING:** String para conectar com o MongoDB, não testamos strings com usuário e senha, pode ser que não funcione.
3. **NAME:** Nome do banco de dados no MongoDB, nos utilizamos o nome `evaluator`, caso altere é possível que tenha que renomear a pasta `evaluator`, dentro da pasta `backup`, para o nome passado.

- **OPENAI**:

Utilizamos o GPT 5.2 para gerar diffs dos códigos para resolver as issues. É possível que os mesmos prompts gerem resultados diferentes.

1. **API_KEY:** Sua chave de API do OpenAI.

- **OLLAMA**:

Nós usamos o qwen3.6:35b and gpt-oss:120b (high, medium) para gerar diffs dos códigos para resolver as issues. É possível que os mesmos prompts gerem resultados diferentes.

1. **BASE_URL**: Ollama base url. Por exemplo: http://localhost:11434
2. **MODEL**: Ollama model name. Por exemplo: gpt-oss:120b

# Instalando o dataset

Com o MongoDB e o arquivo de configuração preenchido só executar o comando `./loadBackup.sh`

# Instalando dependências

Desenvolvemos e executamos o estudo na versão do Python 3.10.8 e pip 23.1.2.

Utilizamos de algumas bibliotecas para desenvolver este trabalho, sendo elas:

```
beautifulsoup4==4.14.3
gensim==4.4.0
matplotlib==3.10.8
nltk==3.9.4
numpy==2.4.4
openai==2.32.0
pandas==3.0.2
pymongo==4.17.0
Requests==2.33.1
scikit_learn==1.8.0
scipy==1.17.1
seaborn==0.13.2
sentence_transformers==5.4.0
torch==2.9.0
tqdm==4.67.1
```

Você pode instalar todas as bibliotecas com o comando: `pip3 install -r requirements.txt`

# Executando

## Minerando e rodando testes

Você pode minerar e rodar testes com o comando: `python3 main.py`.

Vai aparecer uma janela onde você configura os pré processamentos e outras opções, sendo elas:

- **owner/repo:** O repositório a ser minerado, por exemplo: jabref/jabref ou godotengine/godot.
- **K:** O TopK, separado por vírgula.
- **Compare Data:** O que vai ser passado para os algoritmos de similaridade textual.
- **Fetch from API:** Se vai minerar os dados do GitHub ou se vai utilizar dados já minerados.
- **Use good first issues only:** Apenas tarefas boas para novatos vão ser testadas.
- **Good First Issue label:** Alguns repositórios não utilizam o nome tudo em minúsculo, ou, até mesmo, usam outros nomes como por exemplo: "tarefa fácil". Coloque o nome da etiqueta que o repositório usa aqui, isso irá marcar automaticamente se a tarefa é uma tarefa boa para novato nos resultados.
- **Start date:** Tarefas criadas apartir dessa data, fazem parte do grupo de teste.
- **Days before:** Janela de tempo.
- **Closed date:** Tarefas fechadas a partir dessa data vão ser mineradas.
- **Strategy:** Qual algoritmo de similaridade textual vai usar.

Acredito que as outras opções são autoexplicativas. A lematização não está implementada, não vai gerar resultados.

Por fim, após configurar só apertar no botão submit que ele vai minerar os resultados e rodar os testes automaticamente.

## Análises

### Estatísticas

Para conseguir o número de tarefas, prs, arquivos e testes, execute: `python3 count_issues.py`.

### QP1 e QP2

Para obter os resultados da QP1 e QP2 você vai rodar o script `python3 qp12.py`, caso queira apenas tarefas boas para novato descomente a linha 86.

### QP3

Só executar o comando `python3 qp3.py`.
