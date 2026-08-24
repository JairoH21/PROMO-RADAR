from flask import Flask, request
import requests
import os


def create_app():
    app = Flask(__name__)

    @app.route("/", methods=["GET"])
    def home():
        code = request.args.get("code")

        # =====================================================
        # AUTENTICAÇÃO MERCADO LIVRE
        # =====================================================
        if code:
            client_id = os.getenv("MELI_CLIENT_ID")
            client_secret = os.getenv("MELI_CLIENT_SECRET")

            redirect_uri = os.getenv(
                "MELI_REDIRECT_URI",
                "https://promo-radar.onrender.com/"
            )

            if not client_id or not client_secret:
                return """
                <h2>Erro de configuração</h2>
                <p>MELI_CLIENT_ID ou MELI_CLIENT_SECRET não configurados.</p>
                """

            try:
                resposta_token = requests.post(
                    "https://api.mercadolibre.com/oauth/token",
                    data={
                        "grant_type": "authorization_code",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "code": code,
                        "redirect_uri": redirect_uri
                    },
                    headers={
                        "accept": "application/json",
                        "content-type":
                            "application/x-www-form-urlencoded"
                    },
                    timeout=10
                )

                dados_token = resposta_token.json()

                if resposta_token.ok:
                    access_token = dados_token.get("access_token")
                    refresh_token = dados_token.get("refresh_token")

                    return f"""
                    <!DOCTYPE html>
                    <html lang="pt-BR">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport"
                              content="width=device-width, initial-scale=1.0">
                        <title>Mercado Livre conectado</title>
                        <style>
                            body {{
                                font-family: Arial, sans-serif;
                                background: #f4f6f8;
                                padding: 30px;
                            }}

                            .box {{
                                max-width: 700px;
                                margin: auto;
                                background: white;
                                padding: 25px;
                                border-radius: 15px;
                            }}

                            textarea {{
                                width: 100%;
                                min-height: 100px;
                                margin-bottom: 20px;
                            }}
                        </style>
                    </head>

                    <body>
                        <div class="box">
                            <h2>✅ Mercado Livre conectado com sucesso!</h2>

                            <p><b>Access Token:</b></p>
                            <textarea readonly>{access_token}</textarea>

                            <p><b>Refresh Token:</b></p>
                            <textarea readonly>{refresh_token}</textarea>

                            <p>
                                <b>
                                    ⚠️ Não compartilhe esses tokens
                                    com ninguém.
                                </b>
                            </p>
                        </div>
                    </body>
                    </html>
                    """

                return (
                    "Erro ao gerar token: "
                    + str(dados_token)
                )

            except Exception as erro:
                return f"Erro na autenticação: {erro}"

        # =====================================================
        # BUSCA DE PRODUTOS
        # =====================================================
        busca = request.args.get("q", "").strip()
        produtos = []

        if busca:
            try:
                access_token = os.getenv(
                    "MERCADO_LIVRE_ACCESS_TOKEN"
                )

                headers = {}

                if access_token:
                    headers["Authorization"] = (
                        f"Bearer {access_token}"
                    )

                url = "https://api.mercadolibre.com/users/me"
                    
    
                
                resposta = requests.get(
    url,
    headers=headers,
    timeout=10
)
                

                resposta.raise_for_status()
                dados = resposta.json()

                for item in dados.get("results", []):
                    preco = item.get("price", 0)

                    preco_formatado = (
                        f"{preco:,.2f}"
                        .replace(",", "X")
                        .replace(".", ",")
                        .replace("X", ".")
                    )

                    produtos.append({
                        "nome": item.get(
                            "title",
                            "Produto"
                        ),
                        "loja": "Mercado Livre",
                        "preco": f"R$ {preco_formatado}",
                        "desconto": "Oferta",
                        "link": item.get(
                            "permalink",
                            "#"
                        )
                    })

            except Exception as erro:
                print(
                    "Erro Mercado Livre:",
                    erro
                )

        # =====================================================
        # CARDS DOS PRODUTOS
        # =====================================================
        cards = ""

        for produto in produtos:
            cards += f"""
            <div class="card">

                <div class="desconto">
                    {produto['desconto']}
                </div>

                <h3>
                    {produto['nome']}
                </h3>

                <p class="loja">
                    {produto['loja']}
                </p>

                <p class="preco">
                    {produto['preco']}
                </p>

                <a
                    href="{produto['link']}"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    <button type="button">
                        Ver oferta
                    </button>
                </a>

            </div>
            """

        resultado = ""

        if busca:
            if produtos:
                resultado = f"""
                <h2>
                    Ofertas encontradas para: {busca}
                </h2>

                <div class="produtos">
                    {cards}
                </div>
                """
            else:
                resultado = f"""
                <div class="aviso">
                    Nenhuma oferta encontrada para
                    <b>{busca}</b>.
                </div>
                """

        # =====================================================
        # PÁGINA PRINCIPAL
        # =====================================================
        return f"""
<!DOCTYPE html>
<html lang="pt-BR">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Promo Radar</title>

    <style>

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f4f6f8;
            color: #222;
        }}

        header {{
            background:
                linear-gradient(
                    135deg,
                    #ff5a1f,
                    #ff8a00
                );

            color: white;
            padding: 35px 20px;
            text-align: center;
        }}

        header h1 {{
            margin: 0;
            font-size: 38px;
        }}

        header p {{
            margin-top: 10px;
            font-size: 17px;
        }}

        .container {{
            width: 92%;
            max-width: 1100px;
            margin: auto;
        }}

        .busca {{
            background: white;
            padding: 25px;
            margin-top: -25px;
            border-radius: 14px;

            box-shadow:
                0 5px 20px
                rgba(0, 0, 0, 0.10);

            display: flex;
            gap: 10px;
        }}

        .busca input {{
            flex: 1;
            padding: 16px;
            font-size: 17px;
            border-radius: 8px;
            border: 1px solid #ccc;
        }}

        .busca button {{
            border: 0;
            background: #ff5a1f;
            color: white;
            padding: 0 25px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
        }}

        h2 {{
            margin-top: 35px;
        }}

        .produtos {{
            display: grid;

            grid-template-columns:
                repeat(
                    auto-fit,
                    minmax(240px, 1fr)
                );

            gap: 20px;
            margin: 20px 0 50px;
        }}

        .card {{
            background: white;
            border-radius: 14px;
            padding: 20px;

            box-shadow:
                0 4px 15px
                rgba(0, 0, 0, 0.08);

            position: relative;
        }}

        .card h3 {{
            min-height: 48px;
        }}

        .desconto {{
            display: inline-block;
            background: #19a463;
            color: white;
            padding: 6px 10px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: bold;
        }}

        .loja {{
            color: #666;
        }}

        .preco {{
            font-size: 27px;
            font-weight: bold;
            color: #15803d;
        }}

        .card a {{
            text-decoration: none;
        }}

        .card button {{
            width: 100%;
            background: #ff5a1f;
            color: white;
            border: 0;
            padding: 13px;
            border-radius: 8px;
            font-weight: bold;
            cursor: pointer;
        }}

        .aviso {{
            text-align: center;
            color: #777;
            margin: 35px 0;
        }}

        @media (max-width: 600px) {{

            .busca {{
                flex-direction: column;
            }}

            .busca button {{
                padding: 15px;
            }}

            header h1 {{
                font-size: 30px;
            }}

        }}

    </style>

</head>

<body>

    <header>

        <h1>
            🔥 Promo Radar
        </h1>

        <p>
            Encontre promoções e compare preços
            em um só lugar
        </p>

    </header>

    <main class="container">

        <form
            class="busca"
            method="GET"
        >

            <input
                type="text"
                name="q"
                value="{busca}"
                placeholder="Ex: iPhone 15, TV 50, tênis..."
                required
            >

            <button type="submit">
                🔎 Buscar ofertas
            </button>

        </form>

        {resultado}

        <div class="aviso">
            Promo Radar • Comparador de ofertas
        </div>

    </main>

</body>

</html>
        """

    return app
