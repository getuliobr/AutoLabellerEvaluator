
# testando tarefa 8832
from codebleu import calc_codebleu

# sugestão gpt
with open('gpt.java') as f:
  chatgpt = f.read()

# sugestão tfidf topk 1 para 30 dias anteriores
with open('8817.patch') as f:
  sugestao = f.read()
  
with open('8838.patch') as f:
  reference = f.read()

result = calc_codebleu([reference], [chatgpt], lang="java")
print('ChatGPT:', result)

result = calc_codebleu([reference], [sugestao], lang="java")
print('tfidf topk 1 para 30 dias:', result)