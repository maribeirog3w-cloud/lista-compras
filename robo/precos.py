"""Busca o preço dos produtos de produtos.txt nos sites do Atacadão e do Carrefour
e grava precos.json, que o app lê. Roda uma vez por dia pelo GitHub Actions."""
import json, re, time, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timezone

SITES = {
    "Atacadão": "https://www.atacadao.com.br",
    "Carrefour": "https://mercado.carrefour.com.br",
}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*", "Accept-Language": "pt-BR,pt;q=0.9"}
STOP = {"de", "do", "da", "com", "e", "tipo", "integral"}  # "integral" fica opcional

def norm(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"(\d)\s*(kg|g|ml|l|un|rolos?)\b", r"\1\2", t)  # "5 kg" -> "5kg"
    return re.sub(r"\s+", " ", t).strip()

SIZE = re.compile(r"\b(\d+(?:[.,]\d+)?)(kg|g|ml|l|un|rolos?)\b")

def size_of(t):
    m = SIZE.search(norm(t))
    if not m:
        return None
    n, u = float(m.group(1).replace(",", ".")), m.group(2)
    if u == "kg": n, u = n * 1000, "g"
    if u == "l": n, u = n * 1000, "ml"
    if u.startswith("rolo"): u = "rolo"
    return (round(n), u)

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))

def parse_products(products, base):
    out = []
    for p in products:
        for it in p.get("items", []):
            o = next((s.get("commertialOffer", {}) for s in it.get("sellers", [])
                      if s.get("commertialOffer", {}).get("Price") and s["commertialOffer"].get("AvailableQuantity", 0) > 0), None)
            if o:
                out.append({"produto": p.get("productName"), "preco": round(float(o["Price"]), 2),
                            "url": f"{base}/{p.get('linkText')}/p"})
                break
    return out

def search(base, q):
    qe = urllib.parse.quote(q)
    tries = [
        ("legacy", f"{base}/api/catalog_system/pub/products/search?ft={qe}&_from=0&_to=49", lambda j: j),
        ("is", f"{base}/api/io/_v/api/intelligent-search/product_search/?query={qe}&count=50&page=1&locale=pt-BR&hideUnavailableItems=true", lambda j: j.get("products", [])),
        ("is-tp", f"{base}/api/io/_v/api/intelligent-search/product_search/trade-policy/1?query={qe}&count=50&page=1&locale=pt-BR", lambda j: j.get("products", [])),
    ]
    errs = []
    for name, url, pick in tries:
        try:
            offers = parse_products(pick(get(url)), base)
            if offers:
                return offers, None
            errs.append(f"{name}: vazio")
        except Exception as e:
            errs.append(f"{name}: {e}")
    return [], "; ".join(errs)

def matches(q, nome):
    """Todas as palavras importantes do pedido aparecem no produto, e o tamanho bate."""
    nq, nn = norm(q), norm(nome)
    words = [w for w in SIZE.sub("", nq).split() if w not in STOP and len(w) > 1]
    if not all(re.search(r"\b" + re.escape(w), nn) for w in words):
        return False
    sq = size_of(q)
    return sq is None or size_of(nome) == sq

def main():
    produtos = [l.strip() for l in open("produtos.txt", encoding="utf-8") if l.strip() and not l.startswith("#")]
    result = {"atualizado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "produtos": {}, "erros": []}
    for q in produtos:
        entry = {}
        for site, base in SITES.items():
            offers, err = search(base, q)
            good = [o for o in offers if matches(q, o["produto"])]
            if good:
                entry[site] = min(good, key=lambda o: o["preco"])
                print(f"OK  {site:10} {q:28} R$ {entry[site]['preco']:.2f}  {entry[site]['produto']}")
            else:
                msg = err or f"nenhum dos {len(offers)} resultados bate com o nome/tamanho"
                result["erros"].append(f"{site} / {q}: {msg}")
                print(f"--  {site:10} {q:28} {msg}")
            time.sleep(1.5)
        key = re.sub(r"\s+", " ", unicodedata.normalize("NFD", q.lower())).strip()
        key = "".join(c for c in key if unicodedata.category(c) != "Mn")
        result["produtos"][key] = {"nome": q, "lojas": entry}
    with open("precos.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
