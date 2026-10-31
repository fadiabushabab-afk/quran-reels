"""
AI backgrounds from OpenAI's image API (the model behind ChatGPT images).

Needs the environment variable OPENAI_API_KEY (stored as a GitHub secret).
Optional: OPENAI_IMAGE_MODEL (default gpt-image-2), OPENAI_IMAGE_QUALITY (default medium).

Scenes follow the user's "Holy Quran" mood board: warm golden light, mashrabiya
lattice windows, arches, mosque skylines, starry nights. Every prompt asks for a calm,
empty centre (the verses go there) and forbids people, animals and any text.
"""
import base64, json, os, random, urllib.request

SCENES = [
    "interior of a serene traditional mosque at golden hour, warm sunlight streaming through an ornate pointed-arch mashrabiya window with an eight-pointed-star lattice, patterned golden light and soft shadows on cream stone walls and a polished marble floor, soft volumetric light rays and floating dust",
    "a long Islamic arcade corridor with repeating pointed arches and carved lattice screens, warm sunlight casting star-shaped light patterns on a polished marble floor, cream and golden stone, soft light rays",
    "golden hour over a historic city of mosques, silhouetted domes and tall minarets in warm haze along the bottom, a soft glowing sun low in an amber and cream sky, a small flock of birds in the distance",
    "dark atmospheric mosque interior at dawn, a single tall arched window with an intricate geometric star lattice glowing with light, dramatic god rays and dust falling diagonally onto an ornate tiled floor, warm gold light against dark stone",
    "a peaceful prayer corner, a closed Quran on a carved wooden rehal stand on a soft prayer rug, a glowing brass lantern, warm sunlight through an arched lattice window casting patterned shadows on cream plaster walls, a small olive plant in a clay pot",
    "a tall arched window seen from inside a cream marble room, through it a calm deep-blue night sky with stars and a thin crescent moon above a distant skyline of domes and minarets, soft warm lamp light inside",
    "a quiet courtyard of a historic mosque at sunrise, a still reflecting pool, carved stone arches with blue and gold tilework, soft warm morning light and long gentle shadows",
    "soft dreamy misty mosque skyline in pale cream and white tones, delicate domes and slender minarets fading into fog along the bottom, airy light sky above, minimal and elegant",
    "the courtyard of the Masjid al-Haram in Makkah at blue hour seen from far away, the Kaaba small in the distance with soft lights, calm night sky, serene, no crowds visible in detail",
    "hanging brass lanterns with intricate cut-out patterns glowing warmly inside a dark carved wooden mosque interior, soft bokeh lights, warm amber atmosphere",
]

STYLE = ("Photorealistic, cinematic, warm gold, amber and cream palette, serene and spiritual mood, "
         "shallow depth of field, high detail. Vertical composition. The middle of the frame is calm, "
         "softly lit and uncluttered, leaving empty space for text overlay. "
         "No people, no faces, no animals except distant birds, no text, no letters, no calligraphy, "
         "no writing, no logos, no watermark.")


def available():
    return bool(os.environ.get("OPENAI_API_KEY"))


def generate(rng, dest, scene=None):
    """Generate one background to `dest` (PNG/JPEG). Returns the scene text used."""
    scene = scene or rng.choice(SCENES)
    body = {
        "model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2"),
        "prompt": f"{scene}. {STYLE}",
        "size": "1024x1536",
        "quality": os.environ.get("OPENAI_IMAGE_QUALITY", "medium"),
        "n": 1,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenAI image API {e.code}: {e.read()[:400]!r}")
    item = data["data"][0]
    if item.get("b64_json"):
        raw = base64.b64decode(item["b64_json"])
    else:
        with urllib.request.urlopen(item["url"], timeout=120) as r:
            raw = r.read()
    with open(dest, "wb") as f:
        f.write(raw)
    return scene
