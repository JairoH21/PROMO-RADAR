import requests

def search_mercado_livre(term, limit=20):
    response = requests.get(
        "https://api.mercadolibre.com/sites/MLB/search",
        params={"q": term, "limit": limit},
        timeout=15
    )
    response.raise_for_status()
    result = []
    for item in response.json().get("results", []):
        price = item.get("price")
        old = item.get("original_price")
        discount = None
        if price is not None and old and old > price:
            discount = round((1 - price / old) * 100, 1)
        if discount is not None and discount >= 40:
            score = "Excelente"
        elif discount is not None and discount >= 20:
            score = "Boa"
        else:
            score = "Normal"
        result.append({
            "source": "Mercado Livre",
            "external_id": item.get("id"),
            "title": item.get("title", ""),
            "url": item.get("permalink", ""),
            "image_url": item.get("thumbnail", ""),
            "price": price,
            "old_price": old,
            "discount": discount,
            "score": score,
        })
    return result

def search_all(term):
    return search_mercado_livre(term)
