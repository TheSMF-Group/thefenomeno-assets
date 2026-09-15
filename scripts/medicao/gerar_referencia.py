"""Gera UM render de referência (ground truth), não asset: hair_buzz sobre a base escura raw/tmp_4.png.

Por que: o halo de pele junto ao pelo, em tom escuro, vinha sendo medido contra r*base, que é o
próprio modelo em disputa. Um render real do gerador sobre tmp_4 (que é MST-10 no canvas de 1254:
k tmp_4/tmp_1 = 0,1299/0,1515/0,1771, igual ao tones.json; IoU de silhueta 0,9941 contra tmp_1)
mostra como o gerador resolve a relação pele-pelo em tom escuro. Não substitui nenhuma camada.

Gerador: o mesmo dos renders de raw/ (C2PA: "OpenAI Media Service API"), endpoint de edição, com
duas imagens: tmp_4.png (a editar) e hair_buzz.png (o corte a copiar). Saída em raw/_referencia/.

Uso:
  OPENAI_API_KEY=... python scripts/medicao/gerar_referencia.py [--model gpt-image-1] [--n 1] [--size auto]

Modo de falha registrado no NOTES: ~14% dos envios voltam vazios sem erro; reenviar sem mudar nada.
"""
import argparse, base64, io, json, mimetypes, os, sys, urllib.request, uuid

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(ROOT, "raw", "_referencia")

PROMPT = (
    "Two images are attached. Image 1 is a bald 3D mannequin head with dark brown skin, front view, "
    "white background. Image 2 is the same mannequin with lighter skin wearing a very short buzz cut. "
    "Edit image 1: add exactly the same buzz cut from image 2 to the head in image 1 - same hair "
    "length, same hairline shape, same hair colour (dark), same deep shadows between the strands. "
    "Keep everything else in image 1 pixel-identical: same face, same dark skin tone, same lighting, "
    "same white background, same framing and size. Do not lighten the skin anywhere. Photorealistic render."
)


def multipart(fields, files):
    boundary = "----ref" + uuid.uuid4().hex
    body = io.BytesIO()
    for k, v in fields.items():
        body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for k, path in files:
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{os.path.basename(path)}\"\r\n"
                   f"Content-Type: {ctype}\r\n\r\n".encode())
        body.write(open(path, "rb").read())
        body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())
    return body.getvalue(), f"multipart/form-data; boundary={boundary}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-image-1")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--size", default="auto")
    ap.add_argument("--quality", default="high")
    ap.add_argument("--tag", default="hair_buzz_tmp4")
    a = ap.parse_args()

    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("OPENAI_API_KEY ausente no ambiente")
    os.makedirs(OUT_DIR, exist_ok=True)

    fields = {"model": a.model, "prompt": PROMPT, "n": str(a.n), "size": a.size, "quality": a.quality}
    files = [("image[]", os.path.join(ROOT, "raw", "tmp_4.png")), ("image[]", os.path.join(ROOT, "raw", "hair_buzz.png"))]
    data, ctype = multipart(fields, files)
    req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=data, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read()[:2000].decode(errors='replace')}")

    items = resp.get("data") or []
    if not items:
        sys.exit("resposta vazia (modo de falha conhecido: reenviar)")
    written = []
    for i, it in enumerate(items):
        b64 = it.get("b64_json")
        if not b64:
            print(f"item {i} sem b64_json: {list(it.keys())}")
            continue
        p = os.path.join(OUT_DIR, f"{a.tag}_{i+1}.png")
        open(p, "wb").write(base64.b64decode(b64))
        written.append(p)
    meta = {"model": a.model, "size": a.size, "quality": a.quality, "prompt": PROMPT,
            "inputs": [os.path.relpath(f, ROOT) for _, f in files], "usage": resp.get("usage"), "files": [os.path.relpath(p, ROOT) for p in written]}
    open(os.path.join(OUT_DIR, f"{a.tag}.json"), "w", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    for p in written:
        from PIL import Image
        im = Image.open(p); print(p, im.size, im.mode, os.path.getsize(p), "bytes")


if __name__ == "__main__":
    main()
