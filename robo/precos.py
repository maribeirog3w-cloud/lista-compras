"""Busca o preço dos produtos de produtos.txt nos sites do Atacadão e do Carrefour
e grava precos.json, que o app lê. Roda uma vez por dia pelo GitHub Actions."""
import json, re, time, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timezone

SITES = {
    "Atacadão": "https://www.atacadao.com.br",
    "Carrefour": "https://mercado.carrefour.com.br",
}
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36",
      "Accept": "application/json"}

def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip()

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))

def offers_legacy(base, q):
    url = f"{base}/api/catalog_system/pub/products/search?ft={urllib.parse.quote(q)}&_from=0&_to=9"
    out = []
    for p in get(url):
        for it in p.get("items", []):
            for s in it.get("sellers", []):
                o = s.get("commertialOffer", {})
                if o.get("Price") and o.get("AvailableQuantity", 0) > 0:
                    out.append({"produto": p.get("productName"), "preco": round(float(o["Price"]), 2),
                                "url": f"{base}/{p.get('linkText')}/p"})
                    break
            if out and out[-1]["produto"] == p.get("productName"):
                break
    return out

def offers_is(base, q):
    url = f"{base}/api/io/_v/api/intelligent-search/product_search/?query={urllib.parse.quote(q)}&count=10&page=1&locale=pt-BR"
    out = []
    for p in get(url).get("products", []):
        for it in p.get("items", []):
            for s in it.get("sellers", []):
                o = s.get("commertialOffer", {})
                if o.get("Price") and o.get("AvailableQuantity", 0) > 0:
                    out.append({"produto": p.get("productName"), "preco": round(float(o["Price"]), 2),
                                "url": f"{base}/{p.get('linkText')}/p"})
                    break
            else:
                continue
            break
    return out

def relevance(q, nome):
    qw = [w for w in norm(q).split() if len(w) > 1]
    nn = norm(nome or "")
    return sum(1 for w in qw if w in nn) / max(len(qw), 1)

def main():
    produtos = [l.strip() for l in open("produtos.txt", encoding="utf-8") if l.strip() and not l.startswith("#")]
    result = {"atualizado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "produtos": {}, "erros": []}
    for q in produtos:
        entry = {}
        for site, base in SITES.items():
            offers, err = [], None
            for fn in (offers_legacy, offers_is):
                try:
                    offers = fn(base, q)
                    if offers:
                        break
                except Exception as e:
                    err = f"{fn.__name__}: {e}"
            if offers:
                # entre os resultados mais parecidos com o nome, fica o mais barato
                best_rel = max(relevance(q, o["produto"]) for o in offers)
                cand = [o for o in offers if relevance(q, o["produto"]) >= best_rel - 1e-9]
                entry[site] = min(cand, key=lambda o: o["preco"])
                print(f"OK  {site:10} {q:28} R$ {entry[site]['preco']:.2f}  {entry[site]['produto']}")
            else:
                result["erros"].append(f"{site} / {q}: {err or 'nada encontrado'}")
                print(f"--  {site:10} {q:28} {err or 'nada encontrado'}")
            time.sleep(1.5)
        result["produtos"][norm(q)] = {"nome": q, "lojas": entry}
    with open("precos.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
