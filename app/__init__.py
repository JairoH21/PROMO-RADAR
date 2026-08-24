from pathlib import Path

code = r'''from flask import Flask, request, redirect
import html
import os
from urllib.parse import urlencode

import requests


ML_API = "https://api.mercadolibre.com"
ML_AUTH = "https://auth.mercadolivre.com.br/authorization"
SITE_ID = "MLB"

# Cache em memória. As variáveis do Render continuam sendo a fonte principal.
TOKEN_CACHE = {
    "access_token": os.getenv("MERCADO_LIVRE_ACCESS_TOKEN", "").strip(),
    "refresh_token": os.getenv("MERCADO_LIVRE_REFRESH_TOKEN", "").strip(),
}


def _env(name, default=""):
    return os.getenv(name, default).strip()


def _redirect_uri():
    # IMPORTANTE: deve ser EXATAMENTE igual ao URI cadastrado no Mercado Livre.
    return _env("MELI_REDIRECT_URI", "https://promo-radar.onrender.com")


def _access_token():
    return TOKEN_CACHE.get("access_token") or _env("MERCADO_LIVRE_ACCESS_TOKEN")


def _refresh_token():
    return TOKEN_CACHE.get("refresh_token") or _env("MERCADO_LIVRE_REFRESH_TOKEN")


def _auth_headers():
    token = _access_token()
    if not token:
        return {}
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Promo-Radar/1.0",
    }


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return {}


def _ml_error_message(response):
    data = _safe_json(response)
    message = data.get("message") or data.get("error") or response.text or "Erro desconhecido."
    code = data.get("code", "")
    if code:
        return f"{message} ({code})"
    return str(message)


def _exchange_authorization_code(code):
    client_id = _env("MELI_CLIENT_ID")
    client_secret = _env("MELI_CLIENT_SECRET")

    if not client_id or not client_secret:
        return False, "MELI_CLIENT_ID ou MELI_CLIENT_SECRET não configurado no Render."

    response = requests.post(
        f"{ML_API}/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": _redirect_uri(),
        },
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=20,
    )

    data = _safe_json(response)
    if not response.ok:
        return False, _ml_error_message(response)

    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")

    if not access_token:
        return False, "O Mercado Livre não devolveu um Access Token."

    TOKEN_CACHE["access_token"] = access_token
    if refresh_token:
        TOKEN_CACHE["refresh_token"] = refresh_token

    return True, "Mercado Livre conectado com sucesso."


def _refresh_access_token():
    client_id = _env("MELI_CLIENT_ID")
    client_secret = _env("MELI_CLIENT_SECRET")
    refresh_token = _refresh_token()

    if not client_id or not client_secret or not refresh_token:
        return False, "Credenciais ou Refresh Token não configurados."

    response = requests.post(
        f"{ML_API}/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=20,
    )

    data = _safe_json(response)
    if not response.ok:
        return False, _ml_error_message(response)

    new_access = data.get("access_token")
    new_refresh = data.get("refresh_token")

    if not new_access:
        return False, "O Mercado Livre não devolveu um novo Access Token."

    TOKEN_CACHE["access_token"] = new_access
    if new_refresh:
        TOKEN_CACHE["refresh_token"] = new_refresh

    return True, "Token renovado."


def _api_get(path, params=None, retry_token=True):
    response = requests.get(
        f"{ML_API}{path}",
        params=params or {},
        headers=_auth_headers(),
        timeout=20,
    )

    # Tenta uma renovação automática apenas uma vez.
    if response.status_code in (401, 403) and retry_token and _refresh_token():
        refreshed, _ = _refresh_access_token()
        if refreshed:
            return _api_get(path, params=params, retry_token=False)

    return response


def _format_brl(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Preço indisponível"

    formatted = f"{number:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _collect_offers(query):
    """
    Fluxo atual:
    1) Busca produtos de catálogo pelo endpoint oficial /products/search.
    2) Para cada produto, tenta usar o buy_box_winner.
    3) Se não houver vencedor, consulta /products/{PRODUCT_ID}/items.
    """
    if not _access_token():
        return [], "O Access Token do Mercado Livre não está configurado."

    search = _api_get(
        "/products/search",
        params={
            "status": "active",
            "site_id": SITE_ID,
            "q": query,
            "limit": 8,
        },
    )

    if not search.ok:
        if search.status_code == 403:
            return [], (
                "O Mercado Livre recusou a chamada com erro 403. "
                "Isso normalmente indica que o token não possui a permissão/escopo exigido "
                "pela API. Reconecte o aplicativo depois de revisar as permissões no DevCenter. "
                f"Detalhe: {_ml_error_message(search)}"
            )
        if search.status_code == 401:
            return [], "O Access Token está inválido ou expirado. Reconecte o Mercado Livre."
        return [], f"Erro Mercado Livre {search.status_code}: {_ml_error_message(search)}"

    catalog = _safe_json(search).get("results", [])
    offers = []

    # Limita chamadas para manter o site rápido no plano grátis do Render.
    for product in catalog[:6]:
        product_id = product.get("id")
        if not product_id:
            continue

        detail_response = _api_get(f"/products/{product_id}")
        if not detail_response.ok:
            continue

        detail = _safe_json(detail_response)
        name = detail.get("name") or product.get("name") or "Produto"
        permalink = detail.get("permalink") or "#"

        picture = ""
        pictures = detail.get("pictures") or []
        if pictures and isinstance(pictures, list):
            picture = pictures[0].get("url", "") or pictures[0].get("secure_url", "")

        winner = detail.get("buy_box_winner")
        if winner and winner.get("price") is not None:
            offers.append(
                {
                    "nome": name,
                    "loja": "Mercado Livre",
                    "preco_num": float(winner.get("price", 0)),
                    "preco": _format_brl(winner.get("price")),
                    "link": permalink,
                    "imagem": picture,
                    "frete_gratis": bool((winner.get("shipping") or {}).get("free_shipping")),
                }
            )
            continue

        # Se não houver buy box, tenta pegar a publicação mais barata da PDP.
        items_response = _api_get(
            f"/products/{product_id}/items",
            params={"limit": 5},
        )
        if not items_response.ok:
            continue

        items = _safe_json(items_response).get("results", [])
        valid_items = [item for item in items if item.get("price") is not None]
        if not valid_items:
            continue

        cheapest = min(valid_items, key=lambda item: float(item.get("price", 0)))
        item_id = cheapest.get("item_id", "")
        item_link = (
            f"https://produto.mercadolivre.com.br/{item_id}"
            if item_id
            else permalink
        )

        offers.append(
            {
                "nome": name,
                "loja": "Mercado Livre",
                "preco_num": float(cheapest.get("price", 0)),
                "preco": _format_brl(cheapest.get("price")),
                "link": item_link,
                "imagem": picture,
                "frete_gratis": bool((cheapest.get("shipping") or {}).get("free_shipping")),
            }
        )

    offers.sort(key=lambda item: item["preco_num"])
    return offers, None


def _page(query="", offers=None, error=None, notice=None):
    offers = offers or []

    cards = ""
    for offer in offers:
        image_html = ""
        if offer.get("imagem"):
            image_html = (
                f'<img class="product-image" src="{html.escape(offer["imagem"], quote=True)}" '
                f'alt="{html.escape(offer["nome"], quote=True)}">'
            )

        shipping = '<span class="shipping">Frete grátis</span>' if offer.get("frete_gratis") else ""

        cards += f"""
        <article class="card">
            {image_html}
            <div class="badge">Mercado Livre</div>
            <h3>{html.escape(offer["nome"])}</h3>
            <p class="price">{html.escape(offer["preco"])}</p>
            {shipping}
            <a class="offer-button" href="{html.escape(offer["link"], quote=True)}"
               target="_blank" rel="noopener noreferrer">Ver oferta</a>
        </article>
        """

    feedback = ""
    if error:
        feedback = f'<div class="message error">{html.escape(error)}</div>'
    elif notice:
        feedback = f'<div class="message success">{html.escape(notice)}</div>'
    elif query and not offers:
        feedback = f'<div class="message">Nenhuma oferta encontrada para <b>{html.escape(query)}</b>.</div>'

    results_title = ""
    if query and offers:
        results_title = f"<h2>Ofertas para: {html.escape(query)}</h2>"

    connected = bool(_access_token())
    connection_text = "Mercado Livre conectado" if connected else "Mercado Livre não conectado"
    connection_class = "connected" if connected else "disconnected"

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Promo Radar</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: Arial, Helvetica, sans-serif;
            background: #f5f6f8;
            color: #222;
        }}
        header {{
            background: linear-gradient(135deg,#ff2b2b,#ff7a00);
            color: white;
            padding: 34px 18px 52px;
            text-align: center;
        }}
        header h1 {{ margin: 0; font-size: clamp(30px,6vw,44px); }}
        header p {{ margin: 8px 0 0; opacity: .95; }}
        .container {{ width: min(1120px,94%); margin: -24px auto 50px; }}
        .search-box {{
            background: white;
            padding: 18px;
            border-radius: 16px;
            box-shadow: 0 8px 30px rgba(0,0,0,.10);
        }}
        form {{ display: flex; gap: 10px; }}
        input {{
            flex: 1;
            min-width: 0;
            padding: 15px;
            border: 1px solid #ccd0d5;
            border-radius: 10px;
            font-size: 17px;
        }}
        button, .connect-button {{
            border: 0;
            background: #ff4b1f;
            color: white;
            padding: 14px 20px;
            border-radius: 10px;
            font-weight: 700;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
        }}
        .status-row {{
            margin: 14px 0 0;
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .status {{
            font-size: 14px;
            font-weight: 700;
            padding: 7px 10px;
            border-radius: 999px;
        }}
        .connected {{ background: #e8f7ee; color: #147a3b; }}
        .disconnected {{ background: #fff0ef; color: #b42318; }}
        h2 {{ margin-top: 32px; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit,minmax(235px,1fr));
            gap: 18px;
            margin-top: 18px;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            padding: 18px;
            box-shadow: 0 5px 18px rgba(0,0,0,.07);
            display: flex;
            flex-direction: column;
        }}
        .product-image {{
            width: 100%;
            height: 190px;
            object-fit: contain;
            margin-bottom: 10px;
        }}
        .badge {{
            align-self: flex-start;
            background: #fff3cd;
            color: #725c00;
            border-radius: 999px;
            padding: 5px 9px;
            font-size: 12px;
            font-weight: 700;
        }}
        .card h3 {{ font-size: 16px; line-height: 1.35; }}
        .price {{ font-size: 27px; font-weight: 800; color: #15803d; margin: 4px 0 8px; }}
        .shipping {{ color: #16883f; font-size: 13px; font-weight: 700; margin-bottom: 12px; }}
        .offer-button {{
            margin-top: auto;
            background: #ff4b1f;
            color: white;
            text-decoration: none;
            text-align: center;
            border-radius: 9px;
            padding: 12px;
            font-weight: 700;
        }}
        .message {{
            background: white;
            margin-top: 20px;
            padding: 16px;
            border-radius: 12px;
            box-shadow: 0 4px 14px rgba(0,0,0,.05);
            line-height: 1.45;
        }}
        .message.error {{ border-left: 5px solid #d92d20; }}
        .message.success {{ border-left: 5px solid #16883f; }}
        footer {{ text-align: center; color: #777; padding: 30px 15px; }}
        @media (max-width: 650px) {{
            form {{ flex-direction: column; }}
            button {{ width: 100%; }}
        }}
    </style>
</head>
<body>
<header>
    <h1>🔥 Promo Radar</h1>
    <p>Encontre produtos e compare ofertas do Mercado Livre</p>
</header>

<main class="container">
    <section class="search-box">
        <form method="get" action="/">
            <input type="text" name="q" value="{html.escape(query, quote=True)}"
                   placeholder="Ex.: iPhone 15, TV 50, notebook..." required>
            <button type="submit">🔎 Buscar ofertas</button>
        </form>

        <div class="status-row">
            <span class="status {connection_class}">{connection_text}</span>
            <a class="connect-button" href="/conectar-mercado-livre">Conectar novamente</a>
            <a href="/status-ml">Testar conexão</a>
        </div>
    </section>

    {feedback}
    {results_title}
    <section class="grid">{cards}</section>
</main>

<footer>Promo Radar · Comparador de ofertas</footer>
</body>
</html>"""


def create_app():
    app = Flask(__name__)

    @app.get("/")
    def home():
        # O Mercado Livre retorna o Authorization Code para o redirect_uri.
        code = request.args.get("code", "").strip()
        if code:
            ok, message = _exchange_authorization_code(code)
            if ok:
                return redirect("/?ml=connected")
            return _page(error=f"Falha ao conectar Mercado Livre: {message}")

        notice = None
        if request.args.get("ml") == "connected":
            notice = (
                "Mercado Livre conectado. O token ficou ativo nesta instância. "
                "Para sobreviver a reinícios do Render, mantenha também o Access Token e "
                "Refresh Token configurados nas variáveis de ambiente."
            )

        query = request.args.get("q", "").strip()
        if not query:
            return _page(notice=notice)

        offers, error = _collect_offers(query)
        return _page(query=query, offers=offers, error=error, notice=notice)

    @app.get("/conectar-mercado-livre")
    def connect_ml():
        client_id = _env("MELI_CLIENT_ID")
        if not client_id:
            return _page(error="MELI_CLIENT_ID não está configurado no Render.")

        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": _redirect_uri(),
        }
        return redirect(f"{ML_AUTH}?{urlencode(params)}")

    @app.get("/status-ml")
    def status_ml():
        if not _access_token():
            return _page(error="Nenhum Access Token configurado.")

        response = _api_get("/users/me")
        if response.ok:
            data = _safe_json(response)
            nickname = data.get("nickname", "conta autorizada")
            return _page(notice=f"Conexão OK com o Mercado Livre: {nickname}.")

        if response.status_code == 403:
            return _page(
                error=(
                    "Mercado Livre respondeu 403. O token existe, mas alguma política/escopo "
                    "da aplicação não autorizou o acesso. Revise as permissões no DevCenter e "
                    "gere uma nova autorização. Detalhe: "
                    + _ml_error_message(response)
                )
            )

        return _page(
            error=f"Mercado Livre respondeu {response.status_code}: {_ml_error_message(response)}"
        )

    return app
'''

out = Path("/mnt/data/__init__.py")
out.write_text(code, encoding="utf-8")
print(f"Arquivo criado: {out}")
print(f"Linhas: {len(code.splitlines())}")
