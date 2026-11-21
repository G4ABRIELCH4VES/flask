import json
from datetime import date
from itertools import count
from threading import RLock

from flask import (
    Flask,
    abort,
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.exceptions import HTTPException


LIMITES = {"titulo": 150, "data": 10}
OBRIGATORIOS = {"titulo", "data"}

class ErroValidacao(ValueError):
    def __init__(self, campos):
        super().__init__("Dados inválidos.")
        self.campos = campos


def validar_evento(dados):
    if not isinstance(dados, dict):
        raise ErroValidacao({"corpo": "Envie um objeto JSON."})

    erros = {}
    evento = {}
    for campo, limite in LIMITES.items():
        valor = dados.get(campo, "")
        if not isinstance(valor, str):
            erros[campo] = "Informe um texto."
            continue

        valor = valor.strip()
        if campo in OBRIGATORIOS and not valor:
            erros[campo] = "Campo obrigatório."
        elif len(valor) > limite:
            erros[campo] = f"Informe no máximo {limite} caracteres."
        else:
            evento[campo] = valor

    for campo in dados.keys() - LIMITES.keys():
        erros[campo] = "Campo não permitido."

    if "data" in evento:
        try:
            if date.fromisoformat(evento["data"]).isoformat() != evento["data"]:
                raise ValueError
        except ValueError:
            erros["data"] = "Informe uma data válida no formato AAAA-MM-DD."

    if erros:
        raise ErroValidacao(erros)
    return evento


def buscar_evento(evento_id):
    if not 1 <= evento_id <= 9223372036854775807:
        abort(404)
    evento = current_app.extensions["eventos"].get(evento_id)
    if evento is None:
        abort(404)
    return dict(evento)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(MAX_CONTENT_LENGTH=64 * 1024)
    if test_config is not None:
        app.config.update(test_config)

    eventos = {}
    app.extensions["eventos"] = eventos
    proximo_id = count(1)
    eventos_lock = RLock()

    with app.open_resource("openapi.json") as arquivo:
        especificacao = json.load(arquivo)

    @app.before_request
    def bloquear_eventos():
        # Protege o dicionário e a geração de IDs entre requisições simultâneas.
        eventos_lock.acquire()
        g.eventos_bloqueados = True

    @app.teardown_request
    def liberar_eventos(_erro):
        if g.pop("eventos_bloqueados", False):
            eventos_lock.release()

    @app.get("/")
    def inicio():
        return redirect(url_for("documentacao"))

    @app.get("/docs", strict_slashes=False)
    def documentacao():
        return render_template("swagger.html")

    @app.get("/openapi.json")
    def openapi():
        return jsonify(
            {
                **especificacao,
                "servers": [{"url": request.url_root.rstrip("/")}],
            }
        )

    @app.errorhandler(ErroValidacao)
    def tratar_validacao(erro):
        return jsonify(erro="Dados inválidos.", campos=erro.campos), 400

    @app.errorhandler(HTTPException)
    def tratar_erro_http(erro):
        mensagens = {
            400: "JSON inválido. Envie um corpo JSON bem formado.",
            404: "Recurso não encontrado.",
            405: "Método não permitido.",
            413: "O corpo da requisição excede o limite de 64 KB.",
            415: "Envie o corpo com Content-Type application/json.",
            500: "Erro interno do servidor.",
        }
        resposta = erro.get_response()
        resposta.data = app.json.dumps(
            {"erro": mensagens.get(erro.code, erro.description)}
        )
        resposta.content_type = "application/json"
        return resposta

    @app.get("/eventos")
    def listar_eventos():
        return jsonify(
            sorted(eventos.values(), key=lambda evento: (evento["data"], evento["id"]))
        )

    @app.get("/eventos/<int:evento_id>")
    def consultar_evento(evento_id):
        return jsonify(buscar_evento(evento_id))

    @app.post("/eventos")
    def cadastrar_evento():
        dados = validar_evento(request.get_json())
        evento = {"id": next(proximo_id), **dados}
        eventos[evento["id"]] = evento
        return (
            jsonify(evento),
            201,
            {"Location": url_for("consultar_evento", evento_id=evento["id"])},
        )

    @app.put("/eventos/<int:evento_id>")
    def atualizar_evento(evento_id):
        buscar_evento(evento_id)
        dados = validar_evento(request.get_json())
        evento = {"id": evento_id, **dados}
        eventos[evento_id] = evento
        return jsonify(evento)

    @app.delete("/evento/<int:evento_id>")
    @app.delete("/eventos/<int:evento_id>")
    def remover_evento(evento_id):
        buscar_evento(evento_id)
        del eventos[evento_id]
        return "", 204

    return app


if __name__ == "__main__":
    create_app().run()
