# API de eventos com Flask

CRUD simples de eventos com Python, Flask, armazenamento em um dicionário na memória RAM e documentação Swagger. As rotas recebem e devolvem JSON para uso no Postman, Insomnia ou curl. Requer Python 3.9 ou superior.

## Executar

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
flask --app app run
```

A API fica disponível em `http://127.0.0.1:5000`. Também é possível iniciar com `python app.py`.

Os eventos são armazenados em um dicionário Python chamado `eventos`, usando o ID como chave. O dicionário começa vazio, mantém os dados entre as requisições e perde os dados ao encerrar ou reiniciar o servidor, inclusive com o recarregador de desenvolvimento. Cada execução da aplicação possui seu próprio dicionário em RAM. Os IDs são gerados sequencialmente e não são reutilizados após excluir um evento.

Exemplo da estrutura em memória após um cadastro:

```python
eventos = {
    1: {"id": 1, "titulo": "Encontro Flask", "data": "2026-12-05"}
}
```

## Swagger

Abra **http://127.0.0.1:5000/docs** para ver os endpoints, campos obrigatórios, exemplos e códigos de resposta. Use **Try it out** e **Execute** para enviar requisições à mesma API. A raiz `/` redireciona para essa documentação.

O contrato OpenAPI está em `openapi.json` e em **http://127.0.0.1:5000/openapi.json**. Ao acessar pela API, o endereço do servidor é ajustado para o host e a porta utilizados.

A tela de documentação carrega os arquivos oficiais do Swagger UI por CDN e precisa de acesso à internet no navegador. A API funciona localmente, com apenas o Flask como dependência.

## Testar no Postman ou Insomnia

Para testar cadastro e listagem no Postman com o cabeçalho JSON já configurado, use **Import** e selecione `postman_collection.json`. Abra a requisição **Cadastrar evento** e clique em **Send**; o esperado é `201`. Depois envie **Listar eventos**, que deve retornar `200` e a lista de eventos.

Com o servidor em execução, importe o arquivo `openapi.json` ou a URL `http://127.0.0.1:5000/openapi.json`:

- **Postman:** use **Import**, selecione o arquivo ou cole a URL e importe como uma coleção.
- **Insomnia:** use **Import**, escolha **File** ou **URL** e conclua a importação. Se o contrato aparecer na aba **Spec**, use **Generate → Requests** para gerar as requisições.

Esses fluxos estão descritos nas documentações do [Postman](https://learning.postman.com/docs/getting-started/importing-and-exporting/importing-data) e do [Insomnia](https://developer.konghq.com/how-to/import-an-api-spec/).

Para criar requisições manualmente, use a base `http://127.0.0.1:5000`. Em POST e PUT, selecione corpo **JSON** e envie `Content-Type: application/json`.

Sequência sugerida para testar:

1. `GET /eventos` → `200` e `[]` em uma execução nova.
2. `POST /eventos` com cada um dos dois exemplos abaixo → `201`; anote os IDs retornados.
3. `GET /eventos` → `200`, com os eventos ordenados por data.
4. `GET /eventos/{id}` → `200`, com o evento consultado.
5. `PUT /eventos/{id}` com todos os campos obrigatórios → `200`, com os dados atualizados.
6. `DELETE /evento/{id}` → `204`, sem corpo.
7. `GET /eventos/{id}` para o evento removido → `404`.
8. `POST /eventos` com `{}` ou uma data impossível → `400`, com os erros.

Exemplo 1 para o corpo de `POST /eventos`:

```json
{
  "titulo": "Encontro Flask",
  "data": "2026-12-05"
}
```

Exemplo 2 para o corpo de `POST /eventos`:

```json
{
  "titulo": "Oficina de Python",
  "data": "2026-12-12"
}
```

Os exemplos também estão no Swagger. Cadastre-os pelas requisições após iniciar o servidor; eles não são inseridos automaticamente.

## Rotas

| Método | Rota | Resultado |
| --- | --- | --- |
| GET | `/eventos` | Lista ordenada por data crescente, com desempate por ID; retorna `[]` se não houver eventos. |
| GET | `/eventos/{id}` | Consulta um evento. |
| POST | `/eventos` | Cadastra um evento; retorna `201`, o evento criado e o cabeçalho `Location`. |
| PUT | `/eventos/{id}` | Substitui os dados do evento; retorna `200` e o evento atualizado. |
| DELETE | `/evento/{id}` | Remove um evento; retorna `204`, sem corpo. |
| DELETE | `/eventos/{id}` | Alternativa no plural para a mesma remoção. |

IDs inexistentes ou inválidos retornam `404`. PUT e DELETE não criam registros.

## Campos e validações

Cada evento contém apenas `id`, `titulo` e `data`. O `id` é um inteiro positivo gerado automaticamente pelo servidor e permanece o mesmo ao atualizar o evento. Exemplo de resposta:

```json
{
  "id": 1,
  "titulo": "Encontro Flask",
  "data": "2026-12-05"
}
```

POST e PUT exigem `Content-Type: application/json` e um objeto JSON com os dois campos abaixo:

| Campo | Obrigatório | Validação |
| --- | --- | --- |
| `titulo` | Sim | Texto não vazio, até 150 caracteres. |
| `data` | Sim | Data existente no formato `AAAA-MM-DD`, como `2026-12-20`. |

Espaços no início e no final dos textos são removidos. Campos desconhecidos, incluindo `id`, são rejeitados. Valores `null`, números, listas e objetos não são aceitos como valores dos campos. Datas passadas são permitidas.

PUT exige `titulo` e `data`, assim como POST. O ID do evento a atualizar é informado na URL.

Erros de validação retornam `400` com detalhes por campo:

```json
{
  "erro": "Dados inválidos.",
  "campos": {
    "titulo": "Campo obrigatório.",
    "data": "Informe uma data válida no formato AAAA-MM-DD."
  }
}
```

JSON malformado retorna `400`; tipo de conteúdo incorreto retorna `415`; corpos maiores que 64 KB retornam `413`. As respostas de erro são JSON.

## Exemplos

Cadastrar:

```bash
curl -i -X POST http://127.0.0.1:5000/eventos \
  -H 'Content-Type: application/json' \
  -d '{"titulo":"Encontro Flask","data":"2026-12-20"}'
```

Listar e consultar:

```bash
curl http://127.0.0.1:5000/eventos
curl http://127.0.0.1:5000/eventos/1
```

Atualizar:

```bash
curl -X PUT http://127.0.0.1:5000/eventos/1 \
  -H 'Content-Type: application/json' \
  -d '{"titulo":"Encontro atualizado","data":"2026-12-21"}'
```

Remover:

```bash
curl -i -X DELETE http://127.0.0.1:5000/evento/1
```

## Testes

Com as dependências instaladas:

```bash
python -m unittest discover -s tests -v
```

Os testes usam dicionários em RAM isolados por aplicação e verificam o CRUD, a ordenação, as validações, o compartilhamento entre requisições, a geração de IDs após exclusões, o descarte dos dados ao criar uma nova aplicação e a documentação Swagger/OpenAPI.
