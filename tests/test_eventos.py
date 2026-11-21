import unittest
from concurrent.futures import ThreadPoolExecutor

from app import create_app


class EventosTestCase(unittest.TestCase):
    def setUp(self):
        self.config = {"TESTING": True}
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.dados = {
            "titulo": "Encontro Flask",
            "data": "2026-12-20",
        }

    def cadastrar(self, **alteracoes):
        resposta = self.client.post("/eventos", json={**self.dados, **alteracoes})
        self.assertEqual(resposta.status_code, 201)
        return resposta.get_json()

    def test_listagem_inicial_vazia(self):
        resposta = self.client.get("/eventos")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json(), [])

    def test_criar_consultar_atualizar_e_remover(self):
        resposta = self.client.post("/eventos", json=self.dados)
        self.assertEqual(resposta.status_code, 201)
        evento = resposta.get_json()
        self.assertEqual(evento, {"id": evento["id"], **self.dados})
        endereco = f"/eventos/{evento['id']}"
        self.assertEqual(resposta.headers["Location"], endereco)

        consulta = self.client.get(endereco)
        self.assertEqual(consulta.status_code, 200)
        self.assertEqual(consulta.get_json(), evento)

        novos_dados = {
            "titulo": "Novo encontro",
            "data": "2027-01-10",
        }
        atualizacao = self.client.put(endereco, json=novos_dados)
        self.assertEqual(atualizacao.status_code, 200)
        esperado = {"id": evento["id"], **novos_dados}
        self.assertEqual(atualizacao.get_json(), esperado)
        self.assertEqual(self.client.get(endereco).get_json(), esperado)

        remocao = self.client.delete(f"/evento/{evento['id']}")
        self.assertEqual(remocao.status_code, 204)
        self.assertEqual(remocao.data, b"")
        self.assertEqual(self.client.get(endereco).status_code, 404)
        self.assertEqual(self.client.get("/eventos").get_json(), [])

    def test_listagem_ordena_por_data_e_desempata_por_id(self):
        futuro = self.cadastrar(data="2027-01-01")
        primeiro = self.cadastrar(data="2025-02-01")
        segundo = self.cadastrar(data="2025-02-01")
        intermediario = self.cadastrar(data="2026-12-31")
        self.assertEqual(
            self.client.get("/eventos").get_json(),
            [primeiro, segundo, intermediario, futuro],
        )

    def test_alterar_data_muda_posicao_na_listagem(self):
        primeiro = self.cadastrar(data="2026-01-01")
        segundo = self.cadastrar(data="2026-02-01")
        resposta = self.client.put(
            f"/eventos/{primeiro['id']}",
            json={**self.dados, "data": "2026-03-01"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            [evento["id"] for evento in self.client.get("/eventos").get_json()],
            [segundo["id"], primeiro["id"]],
        )

    def test_remocao_tambem_aceita_rota_plural(self):
        evento = self.cadastrar()
        resposta = self.client.delete(f"/eventos/{evento['id']}")
        self.assertEqual(resposta.status_code, 204)
        self.assertEqual(self.client.get("/eventos").get_json(), [])

    def test_espacos_removidos(self):
        dados = {
            "titulo": "  Encontro  ",
            "data": " 2026-12-20 ",
        }
        resposta = self.client.post("/eventos", json=dados)
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(
            resposta.get_json(),
            {
                "id": resposta.get_json()["id"],
                "titulo": "Encontro",
                "data": "2026-12-20",
            },
        )

    def test_rejeita_campos_removidos_no_post_e_put(self):
        evento = self.cadastrar()
        for metodo, endereco in (
            (self.client.post, "/eventos"),
            (self.client.put, f"/eventos/{evento['id']}"),
        ):
            for campo in ("local", "descricao"):
                with self.subTest(metodo=metodo.__name__, campo=campo):
                    resposta = metodo(
                        endereco, json={**self.dados, campo: "Texto de exemplo"}
                    )
                    self.assertEqual(resposta.status_code, 400)
                    self.assertEqual(
                        resposta.get_json()["campos"][campo], "Campo não permitido."
                    )
        self.assertEqual(self.client.get("/eventos").get_json(), [evento])

    def test_campos_obrigatorios_no_post_e_put(self):
        evento = self.cadastrar()
        for metodo, endereco in (
            (self.client.post, "/eventos"),
            (self.client.put, f"/eventos/{evento['id']}"),
        ):
            for campo in ("titulo", "data"):
                for valor in ("ausente", "", "   ", None):
                    with self.subTest(metodo=metodo.__name__, campo=campo, valor=valor):
                        dados = dict(self.dados)
                        if valor == "ausente":
                            dados.pop(campo)
                        else:
                            dados[campo] = valor
                        resposta = metodo(endereco, json=dados)
                        self.assertEqual(resposta.status_code, 400)
                        self.assertIn(campo, resposta.get_json()["campos"])
        self.assertEqual(self.client.get("/eventos").get_json(), [evento])

    def test_rejeita_tipos_incorretos_sem_gravar(self):
        for campo in self.dados:
            for valor in (42, True, [], {}, None):
                with self.subTest(campo=campo, valor=valor):
                    resposta = self.client.post("/eventos", json={**self.dados, campo: valor})
                    self.assertEqual(resposta.status_code, 400)
                    self.assertIn(campo, resposta.get_json()["campos"])
        self.assertEqual(self.client.get("/eventos").get_json(), [])

    def test_limite_de_tamanho_do_titulo(self):
        resposta = self.client.post(
            "/eventos", json={**self.dados, "titulo": "á" * 150}
        )
        self.assertEqual(resposta.status_code, 201)
        resposta = self.client.post(
            "/eventos", json={**self.dados, "titulo": "á" * 151}
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("titulo", resposta.get_json()["campos"])

    def test_rejeita_datas_impossiveis_e_formatos_diferentes(self):
        for data in (
            "2026-02-29",
            "2026-04-31",
            "2026-13-01",
            "0000-01-01",
            "20/12/2026",
            "20261220",
            "2026-W51-7",
            "2026-1-01",
            "2026-12-20T10:00:00",
        ):
            with self.subTest(data=data):
                resposta = self.client.post("/eventos", json={**self.dados, "data": data})
                self.assertEqual(resposta.status_code, 400)
                self.assertIn("data", resposta.get_json()["campos"])
        self.assertEqual(self.client.get("/eventos").get_json(), [])

    def test_aceita_data_bissexta_e_data_passada(self):
        self.cadastrar(data="2024-02-29")

    def test_rejeita_campos_desconhecidos_e_id_fornecido(self):
        for campo in ("id", "outro"):
            with self.subTest(campo=campo):
                resposta = self.client.post("/eventos", json={**self.dados, campo: 7})
                self.assertEqual(resposta.status_code, 400)
                self.assertIn(campo, resposta.get_json()["campos"])
        self.assertEqual(self.client.get("/eventos").get_json(), [])

    def test_rejeita_corpo_que_nao_seja_objeto(self):
        for corpo in ("[]", "null", '"texto"', "123", "true"):
            with self.subTest(corpo=corpo):
                resposta = self.client.post(
                    "/eventos", data=corpo, content_type="application/json"
                )
                self.assertEqual(resposta.status_code, 400)
                self.assertIn("corpo", resposta.get_json()["campos"])

    def test_json_malformado_ou_ausente(self):
        for corpo in ('{"titulo":', ""):
            with self.subTest(corpo=corpo):
                resposta = self.client.post(
                    "/eventos", data=corpo, content_type="application/json"
                )
                self.assertEqual(resposta.status_code, 400)
                self.assertIn("erro", resposta.get_json())

    def test_content_type_incorreto(self):
        resposta = self.client.post("/eventos", data="titulo=Encontro")
        self.assertEqual(resposta.status_code, 415)
        self.assertIn("erro", resposta.get_json())

    def test_rejeita_corpo_acima_do_limite(self):
        resposta = self.client.post(
            "/eventos", json={**self.dados, "titulo": "x" * 65536}
        )
        self.assertEqual(resposta.status_code, 413)
        self.assertIn("erro", resposta.get_json())

    def test_ids_inexistentes_e_invalidos(self):
        for evento_id in (999, 0, -1, "abc", 9223372036854775808):
            for metodo in ("GET", "PUT", "DELETE"):
                with self.subTest(id=evento_id, metodo=metodo):
                    resposta = self.client.open(
                        f"/eventos/{evento_id}", method=metodo, json=self.dados
                    )
                    self.assertEqual(resposta.status_code, 404)
                    self.assertIn("erro", resposta.get_json())
            resposta = self.client.delete(f"/evento/{evento_id}")
            self.assertEqual(resposta.status_code, 404)
        self.assertEqual(self.client.get("/eventos").get_json(), [])

    def test_remover_duas_vezes_retorna_404(self):
        evento = self.cadastrar()
        endereco = f"/evento/{evento['id']}"
        self.assertEqual(self.client.delete(endereco).status_code, 204)
        self.assertEqual(self.client.delete(endereco).status_code, 404)

    def test_ids_nao_sao_reutilizados_apos_remocao(self):
        primeiro = self.cadastrar(titulo="Primeiro evento")
        segundo = self.cadastrar(titulo="Segundo evento")
        resposta = self.client.delete(f"/evento/{segundo['id']}")
        self.assertEqual(resposta.status_code, 204)

        terceiro = self.cadastrar(titulo="Terceiro evento")
        self.assertGreater(terceiro["id"], segundo["id"])
        self.assertEqual(self.client.get("/eventos").get_json(), [primeiro, terceiro])
        self.assertEqual(
            self.client.get(f"/eventos/{segundo['id']}").status_code, 404
        )

    def test_validacao_retorna_todos_os_erros(self):
        resposta = self.client.post("/eventos", json={})
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(set(resposta.get_json()["campos"]), {"titulo", "data"})

    def test_metodo_nao_permitido_preserva_cabecalho_allow(self):
        resposta = self.client.patch("/eventos/1", json=self.dados)
        self.assertEqual(resposta.status_code, 405)
        self.assertIn("erro", resposta.get_json())
        self.assertIn("PUT", resposta.headers["Allow"])

    def test_eventos_sao_armazenados_em_dicionario(self):
        eventos = self.app.extensions["eventos"]
        self.assertIsInstance(eventos, dict)
        self.assertEqual(eventos, {})

        evento = self.cadastrar()
        self.assertEqual(eventos, {evento["id"]: evento})

        resposta = self.client.put(
            f"/eventos/{evento['id']}",
            json={"titulo": "Novo título", "data": "2026-12-21"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(eventos, {evento["id"]: resposta.get_json()})

        resposta = self.client.delete(f"/evento/{evento['id']}")
        self.assertEqual(resposta.status_code, 204)
        self.assertEqual(eventos, {})

    def test_dados_permanecem_entre_clientes_da_mesma_aplicacao(self):
        evento = self.cadastrar()
        outro_cliente = self.app.test_client()
        self.assertEqual(outro_cliente.get("/eventos").get_json(), [evento])

    def test_nova_aplicacao_comeca_vazia_e_isolada(self):
        evento = self.cadastrar()
        nova_app = create_app(self.config)
        self.assertEqual(nova_app.test_client().get("/eventos").get_json(), [])
        self.assertEqual(self.client.get("/eventos").get_json(), [evento])

    def test_requisicoes_em_threads_compartilham_o_dicionario_com_seguranca(self):
        def cadastrar_em_thread(indice):
            with self.app.test_client() as cliente:
                resposta = cliente.post(
                    "/eventos", json={**self.dados, "titulo": f"Evento {indice}"}
                )
                return resposta.status_code, resposta.get_json()

        with ThreadPoolExecutor(max_workers=4) as executor:
            resultados = list(executor.map(cadastrar_em_thread, range(12)))

        self.assertTrue(all(status == 201 for status, _ in resultados))
        self.assertEqual(len({evento["id"] for _, evento in resultados}), 12)
        self.assertEqual(len(self.client.get("/eventos").get_json()), 12)

    def test_inicio_redireciona_para_documentacao(self):
        resposta = self.client.get("/")
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.headers["Location"], "/docs")

    def test_swagger_disponivel_com_e_sem_barra_final(self):
        for endereco in ("/docs", "/docs/"):
            with self.subTest(endereco=endereco):
                resposta = self.client.get(endereco)
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.mimetype, "text/html")
                self.assertIn(b"SwaggerUIBundle", resposta.data)
                self.assertIn(b'"/openapi.json"', resposta.data)

    def test_openapi_documenta_todas_as_operacoes(self):
        resposta = self.client.get("/openapi.json")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.mimetype, "application/json")
        especificacao = resposta.get_json()
        self.assertEqual(especificacao["openapi"], "3.0.3")
        self.assertEqual(set(especificacao["paths"]), {
            "/eventos", "/eventos/{id}", "/evento/{id}"
        })
        for caminho, metodos in (
            ("/eventos", {"get", "post"}),
            ("/eventos/{id}", {"get", "put", "delete"}),
            ("/evento/{id}", {"delete"}),
        ):
            self.assertEqual(
                set(especificacao["paths"][caminho]) - {"parameters"}, metodos
            )

    def test_openapi_usa_endereco_real_do_servidor(self):
        resposta = self.client.get(
            "/openapi.json", base_url="http://127.0.0.1:5001"
        )
        self.assertEqual(
            resposta.get_json()["servers"], [{"url": "http://127.0.0.1:5001"}]
        )

    def test_openapi_documenta_apenas_os_campos_do_evento(self):
        especificacao = self.client.get("/openapi.json").get_json()
        schemas = especificacao["components"]["schemas"]
        entrada = schemas["EventoEntrada"]
        evento = schemas["Evento"]
        self.assertEqual(set(entrada["properties"]), {"titulo", "data"})
        self.assertEqual(set(entrada["required"]), {"titulo", "data"})
        self.assertEqual(set(evento["properties"]), {"id", "titulo", "data"})
        self.assertEqual(set(evento["required"]), {"id", "titulo", "data"})
        self.assertTrue(evento["properties"]["id"]["readOnly"])
        self.assertEqual(set(evento["example"]), {"id", "titulo", "data"})

    def test_exemplos_do_swagger_podem_ser_cadastrados(self):
        especificacao = self.client.get("/openapi.json").get_json()
        exemplos = especificacao["components"]["requestBodies"]["DadosEvento"][
            "content"
        ]["application/json"]["examples"]
        self.assertEqual(len(exemplos), 2)
        for exemplo in exemplos.values():
            resposta = self.client.post("/eventos", json=exemplo["value"])
            self.assertEqual(resposta.status_code, 201)
        self.assertEqual(len(self.client.get("/eventos").get_json()), 2)

    def test_referencias_internas_do_openapi_existem(self):
        especificacao = self.client.get("/openapi.json").get_json()

        def verificar(valor):
            if isinstance(valor, dict):
                if "$ref" in valor:
                    referencia = valor["$ref"]
                    self.assertTrue(referencia.startswith("#/"))
                    destino = especificacao
                    for chave in referencia[2:].split("/"):
                        self.assertIn(chave, destino)
                        destino = destino[chave]
                for filho in valor.values():
                    verificar(filho)
            elif isinstance(valor, list):
                for filho in valor:
                    verificar(filho)

        verificar(especificacao)

    def test_texto_com_sql_e_tratado_como_dado(self):
        evento = self.cadastrar(titulo="Evento'); DROP TABLE eventos; --")
        self.assertEqual(self.client.get("/eventos").get_json(), [evento])
        self.cadastrar(titulo="Próximo evento")


if __name__ == "__main__":
    unittest.main()
