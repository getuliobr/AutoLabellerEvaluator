from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
  model="gpt-3.5-turbo-0125",
  response_format={ "type": "json_object" },
  messages=[
    {"role": "user", "content": "Pretend you are a developer for the jabref/jabref GitHub project and please give me just and only the code or code snippet you think would solve this issue: TITLE: <TÍTULO DA TAREFA> BODY: <CORPO DA TAREFA>}"}
  ]
)
print(response.choices[0].message.content)