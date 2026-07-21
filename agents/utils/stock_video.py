import os
import time
import threading
import shutil
import requests
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from utils.subprocess_helper import safe_run, register_temp_dir
from utils.cost_tracker import log_stock_call
try:
    from utils.health_monitor import pexels_breaker, pixabay_breaker
except ImportError:
    from types import SimpleNamespace
    _noop_breaker = SimpleNamespace(
        is_available=lambda: True, record_success=lambda: None, record_failure=lambda: None
    )
    pexels_breaker = _noop_breaker
    pixabay_breaker = _noop_breaker

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

CLIPS_DIR = Path(__file__).parent.parent / "tmp" / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)
register_temp_dir(str(CLIPS_DIR))

_API_CACHE = {}
_PIXABAY_BLOCKED_UNTIL = 0.0
_PIXABAY_LOCK = threading.Lock()
_API_LAST_CALL = 0.0


def _rate_limit_delay():
    global _API_LAST_CALL
    now = time.time()
    elapsed = now - _API_LAST_CALL
    if elapsed < 0.35:
        time.sleep(0.35 - elapsed)
    _API_LAST_CALL = time.time()


PEXELS_KEYWORD_MAP = {
    # ── Core AI / ML / Tech ──────────────────────────────────────
    "neural": ["neural network", "deep learning", "AI brain"],
    "data": ["data center", "server room", "big data"],
    "code": ["computer code", "programming", "developer coding"],
    "robot": ["robot", "automation", "robotic arm"],
    "chip": ["microchip", "processor", "circuit board"],
    "network": ["network", "cloud computing", "internet"],
    "analytics": ["data analytics", "dashboard", "statistics"],
    "brain": ["human brain", "neuroscience", "thinking"],
    "ai": ["artificial intelligence", "machine learning", "AI"],
    "phone": ["smartphone", "mobile app", "technology device"],
    "screen": ["computer screen", "monitor", "display"],
    "cloud": ["cloud computing", "cloud storage", "server cloud"],
    "cybersecurity": ["cybersecurity", "data protection", "encryption"],
    "algorithm": ["algorithm", "data flow", "binary code"],
    "computer": ["computer lab", "computing", "pc"],
    "math": ["mathematics", "formula", "equations"],
    "presentation": ["presentation", "conference", "tech talk"],
    "transformer": ["transformer architecture", "neural network", "data processing"],
    "attention": ["attention mechanism", "data streams", "neural connections"],
    "embedding": ["vector space", "data mapping", "3d visualization"],
    "backprop": ["neural network layers", "network flow", "deep learning"],
    "gradient": ["data optimization", "mathematical function", "algorithm"],
    "token": ["text processing", "data encoding", "language model"],
    "training": ["machine learning training", "model optimization", "AI training"],
    "inference": ["AI processing", "neural computation", "model inference"],
    "layer": ["neural network layers", "deep learning", "network architecture"],
    "weight": ["neural weights", "network parameters", "AI model"],
    "loss": ["loss function", "optimization curve", "data analysis"],
    "latent": ["latent space", "data distribution", "abstract visualization"],
    "encoder": ["encoder decoder", "data transformation", "code transformation"],
    "llm": ["large language model", "AI text generation", "language AI"],
    "rag": ["retrieval augmented generation", "knowledge retrieval", "AI search"],
    "diffusion": ["diffusion model", "AI image generation", "creative AI"],
    "transformer model": ["transformer architecture", "attention mechanism", "encoder decoder"],
    "gpu": ["graphics card", "GPU server", "data center hardware"],
    "server": ["server room", "data center", "network server"],
    "database": ["database server", "data storage", "sql"],
    "blockchain": ["blockchain technology", "cryptocurrency", "distributed ledger"],
    "quantum computing": ["quantum computer", "qubit", "quantum processor"],

    # ── Science & Research ───────────────────────────────────────
    "science": ["laboratory", "scientist", "research"],
    "scientist": ["data scientist", "researcher", "lab work"],
    "research": ["research paper", "scientific study", "analysis"],
    "physics": ["physics experiment", "quantum", "particle physics", "pendulum", "light prism", "energy", "wave"],
    "chemistry": ["chemistry lab", "chemical reaction", "molecule", "periodic table", "science experiment", "beaker"],
    "biology": ["biology lab", "dna", "cells", "microscope", "evolution", "genetics"],
    "genetics": ["dna sequencing", "genome", "gene editing", "crispr", "chromosome"],
    "neuroscience": ["brain scan", "neuron", "neural activity", "brain mapping", "synapse"],
    "mathematics": ["math visualization", "geometry", "abstract math", "numbers", "fractal", "calculus", "statistics"],
    "logic": ["logic puzzle", "reasoning", "critical thinking", "problem solving", "brain teaser"],
    "laboratory": ["science lab", "experiment", "test tube", "microscope", "research lab"],
    "microscope": ["microscope footage", "cells under microscope", "scientific imaging"],
    "particle physics": ["particle accelerator", "cern", "subatomic", "quantum particles"],
    "astronomy": ["telescope", "night sky", "milky way", "astronomy", "stars", "nebula", "solar system"],
    "telescope": ["observatory", "radio telescope", "space telescope", "stargazing"],
    "geology": ["rocks", "minerals", "volcano", "earthquake", "tectonic plates", "fossil"],
    "paleontology": ["dinosaur fossil", "dig site", "fossil excavation", "prehistoric"],
    "archaeology": ["archaeological dig", "ancient artifact", "ruins excavation", "antiquity"],
    "anthropology": ["human evolution", "ancient civilization", "cultural anthropology", "tribal"],
    "oceanography": ["deep sea", "ocean exploration", "underwater", "marine biology", "coral reef"],

    # ── History & Civilization ───────────────────────────────────
    "history": ["historical", "ancient", "old document", "history archive", "vintage", "medieval", "ruins"],
    "ancient egypt": ["egyptian pyramid", "sphinx", "pharaoh", "hieroglyphics", "temple"],
    "ancient greece": ["greek ruins", "acropolis", "parthenon", "ancient greek philosophy"],
    "roman empire": ["roman ruins", "colosseum", "roman architecture", "ancient rome"],
    "medieval": ["medieval castle", "knight", "cathedral", "middle ages", "feudal"],
    "renaissance": ["renaissance art", "da vinci", "sistine chapel", "florence"],
    "industrial revolution": ["factory", "steam engine", "industrial machinery", "assembly line"],
    "world war": ["war archive", "vintage military", "historical battle", "soldier"],
    "cold war": ["cold war archive", "space race", "berlin wall", "nuclear"],
    "space race": ["apollo mission", "moon landing", "rocket launch historical", "nasa archive"],

    # ── Nature & Environment ─────────────────────────────────────
    "nature": ["nature landscape", "wildlife", "forest", "ocean", "mountains", "sunrise", "nature documentary"],
    "wildlife": ["wild animals", "nature wildlife", "animal documentary", "safari", "predator", "birds", "marine life"],
    "forest": ["deep forest", "rainforest", "woodland", "redwood", "jungle", "canopy"],
    "ocean": ["deep ocean", "waves", "sea", "coastline", "beach", "underwater"],
    "mountains": ["mountain range", "alps", "himalayas", "peak", "snow capped mountain"],
    "desert": ["desert landscape", "sahara", "dunes", "arid", "cactus", "sandstorm"],
    "arctic": ["iceberg", "glacier", "polar bear", "snow", "frozen tundra", "aurora borealis"],
    "rainforest": ["amazon rainforest", "tropical forest", "canopy", "exotic plants"],
    "volcano": ["volcanic eruption", "lava", "volcano documentary", "magma"],
    "weather": ["storm", "hurricane", "lightning", "rain", "snowstorm", "tornado", "clouds"],
    "climate change": ["global warming", "melting ice", "renewable energy", "climate documentary", "carbon emissions"],
    "environment": ["environment", "climate change", "renewable energy", "solar panels", "wind turbine", "green planet", "ecology"],
    "sustainability": ["sustainable", "eco friendly", "recycling", "green technology", "carbon neutral", "clean energy"],
    "earth": ["earth from space", "planet earth", "globe", "world map", "aerial earth"],

    # ── Space & Astronomy ────────────────────────────────────────
    "space": ["stars", "galaxy", "space", "planet"],
    "space exploration": ["rocket launch", "space station", "astronaut", "satellite", "space exploration", "nasa", "spacecraft"],
    "solar system": ["planets", "sun", "orbits", "solar system animation", "venus", "mars"],
    "galaxy": ["milky way", "spiral galaxy", "andromeda", "deep space", "nebula"],
    "black hole": ["black hole simulation", "event horizon", "gravity well", "spacetime"],
    "exoplanet": ["exoplanet", "distant world", "alien planet", "habitable zone"],
    "mars": ["mars rover", "red planet", "mars colonization", "spacex starship"],

    # ── Technology & Engineering ─────────────────────────────────
    "engineering": ["mechanical engineering", "bridge", "construction", "factory", "machine", "industrial design", "gears", "blueprint", "technical drawing"],
    "innovation": ["innovation", "future technology", "invention", "scientific breakthrough", "modern tech", "futuristic"],
    "programming": ["programming code", "software engineer", "developer", "coding screen", "agile", "software architecture"],
    "software": ["software development", "computer programming", "code review", "devops", "clean code"],
    "hardware": ["computer hardware", "electronics", "circuit board", "processor", "microchip"],
    "robotics": ["robot arm", "automation factory", "humanoid robot", "drone", "autonomous"],
    "drones": ["drone footage", "quadcopter", "aerial drone", "uav", "drone technology"],
    "electric vehicle": ["electric car", "tesla", "ev charging", "electric battery", "sustainable transport"],
    "renewable energy": ["solar farm", "wind turbine", "hydroelectric dam", "clean energy", "geothermal"],
    "nuclear": ["nuclear power plant", "nuclear reactor", "cooling tower", "atomic"],
    "biotechnology": ["biotech lab", "gene editing", "bioengineering", "lab grown", "biotech research"],
    "nanotechnology": ["nano particles", "microscopic", "nano materials", "atomic scale"],
    "internet": ["internet infrastructure", "wifi", "fiber optic", "global network"],
    "telecommunications": ["cell tower", "satellite dish", "5g network", "communication"],
    "vr": ["virtual reality", "vr headset", "augmented reality", "metaverse"],
    "semiconductor": ["wafer", "semiconductor fab", "chip manufacturing", "silicon wafer"],

    # ── Business & Economics ─────────────────────────────────────
    "business": ["office", "business meeting", "corporate", "entrepreneur", "startup", "conference room", "strategy"],
    "finance": ["finance", "money", "investment", "stock market", "trading", "banking", "cryptocurrency", "economic growth"],
    "entrepreneurship": ["startup", "entrepreneur", "small business", "founder", "pitch deck"],
    "economics": ["economic graph", "gdp", "market trends", "global economy", "supply chain"],
    "manufacturing": ["factory", "assembly line", "manufacturing plant", "industrial production"],
    "supply chain": ["logistics", "shipping container", "warehouse", "transportation", "cargo ship"],
    "marketing": ["marketing strategy", "advertising", "branding", "social media marketing"],
    "global trade": ["cargo ship", "container port", "international trade", "import export", "globalization"],

    # ── Health & Medicine ────────────────────────────────────────
    "health": ["healthcare", "medical", "hospital", "doctor", "stethoscope", "medicine", "health", "wellness"],
    "medicine": ["medical research", "laboratory research", "dna", "microscope", "vaccine", "pharmaceutical"],
    "surgery": ["operating room", "surgical robot", "medical surgery", "hospital surgery"],
    "human body": ["human anatomy", "body systems", "circulatory system", "organs"],
    "vaccine": ["vaccination", "immunization", "covid vaccine", "medical syringe", "pharmaceutical research"],
    "mental health": ["therapy", "meditation", "mental wellness", "brain health", "counseling"],

    # ── Education & Documentary ──────────────────────────────────
    "education": ["online learning", "e-learning", "study", "classroom", "student"],
    "biography": ["inventor", "historical figure", "great mind", "portrait", "legacy", "pioneer"],
    "documentary": ["documentary footage", "archival video", "interview setup", "behind the scenes"],
    "explanation": ["explainer video", "educational", "science animation"],
    "tutorial": ["tutorial video", "educational animation", "how it works"],
    "university": ["campus", "lecture hall", "college", "academic", "graduation"],
    "lecture": ["professor lecturing", "classroom teaching", "academic presentation"],
    "library": ["library", "books", "archive", "research library", "manuscript"],
    "museum": ["museum exhibit", "gallery", "art exhibition", "historical artifact"],

    # ── Psychology & Humanities ──────────────────────────────────
    "psychology": ["psychology", "human mind", "cognitive", "behavior", "therapy", "mental health", "personality"],
    "philosophy": ["philosophy", "contemplation", "deep thought", "meditation", "wisdom", "ancient philosophy", "ethics"],
    "sociology": ["society", "community", "social dynamics", "urban life", "population"],
    "linguistics": ["language", "speech", "communication", "writing", "translation"],
    "religion": ["religious ceremony", "church", "temple", "mosque", "spiritual", "faith"],
    "ethics": ["ethics debate", "moral philosophy", "ethical dilemma", "bioethics"],
    "artificial consciousness": ["consciousness", "sentient ai", "philosophy of mind", "self awareness"],
    "mythology": ["mythology", "legend", "greek myth", "folklore", "epic story"],

    # ── Culture & Society ────────────────────────────────────────
    "culture": ["cultural diversity", "traditions", "festival", "world cultures", "cultural heritage"],
    "documentary filmmaking": ["behind the scenes", "camera crew", "film production", "interview", "b roll"],
    "journalism": ["newsroom", "journalist", "press conference", "interview", "broadcast"],
    "photography": ["photographer", "camera", "time lapse", "photography studio"],
    "music": ["orchestra", "musician", "concert", "piano", "instruments", "music production"],
    "art": ["artist painting", "sculpture", "modern art", "art studio", "gallery"],
    "cinema": ["movie theater", "film reel", "director", "film history", "hollywood"],
    "architecture": ["modern architecture", "skyscraper", "building design", "city skyline", "brutalist"],
    "urban": ["city street", "urban landscape", "downtown", "city life", "skyline"],
    "rural": ["countryside", "farmland", "rural village", "agriculture", "pastoral"],
    "agriculture": ["farm", "tractor", "harvest", "crops", "organic farming", "livestock"],
    "food": ["food preparation", "cooking", "kitchen", "cuisine", "gastronomy"],
    "travel": ["travel destinations", "tourist", "landmark", "adventure travel", "exploration"],

    # ── Arts & Media ─────────────────────────────────────────────
    "animation": ["motion graphics", "2d animation", "3d animation", "animated explainer"],
    "design": ["graphic design", "industrial design", "product design", "ui design"],
    "writing": ["writer typing", "author", "creative writing", "typewriter", "journal"],
    "publishing": ["printing press", "book publishing", "editorial", "magazine"],
    "podcast": ["podcast studio", "microphone", "audio recording", "broadcasting"],

    # ── Geography & Exploration ──────────────────────────────────
    "geography": ["world map", "globe", "topography", "cartography", "satellite imagery"],
    "exploration": ["explorer", "expedition", "discovery", "adventure", "voyage"],
    "aerial": ["drone landscape", "birds eye view", "aerial photography", "helicopter view"],
    "map": ["world map animation", "historical map", "navigation", "cartography"],
    "timelapse": ["time lapse", "hyperlapse", "city timelapse", "nature timelapse"],

    # ── Short documentary / character ────────────────────────────
    "inventor": ["inventor workshop", "innovation lab", "prototype", "invention"],
    "pioneer": ["trailblazer", "first achievement", "historical breakthrough", "explorer"],
    "scientist portrait": ["scientist thinking", "lab coat", "researcher portrait", "academic"],
    "expert": ["expert interview", "thought leader", "keynote speaker", "conference"],
    "debate": ["debate stage", "discussion", "argument", "panel discussion"],
    "interview": ["interview setting", "talking head", "video interview", "conversation"],
    "timeline": ["historical timeline", "chronology", "progress bar", "milestone"],

    # ── Music & Audio ────────────────────────────────────────────
    "orchestra": ["symphony orchestra", "conductor", "classical music", "violin", "piano"],
    "sound": ["sound waves", "audio frequency", "acoustic", "sound visualization"],
    "audio production": ["recording studio", "mixing console", "music producer", "audio engineer"],

    # ── Abstract & Visualization ─────────────────────────────────
    "diagram": ["diagram animation", "flowchart", "technical illustration"],
    "visualization": ["data visualization", "3d visualization", "molecular visualization"],
    "simulation": ["scientific simulation", "particle simulation", "physics simulation"],
    "model": ["3d model", "architecture model", "mathematical model"],
    "chart": ["animated chart", "graph animation", "data chart"],
    "infographic": ["animated infographic", "data graphic", "information design"],
    "3d rendering": ["3d render", "product rendering", "architectural visualization"],
    "particle system": ["particle effect", "particle animation", "abstract particles"],

    # ── Specific Documentary Topics ──────────────────────────────
    "cybersecurity documentary": ["hacker", "cyber attack", "security breach", "encryption"],
    "social media": ["social media app", "smartphone screen", "social network", "influencer"],
    "privacy": ["data privacy", "surveillance", "cctv", "digital footprint", "encryption"],
    "surveillance": ["security camera", "cctv footage", "surveillance state", "monitoring"],
    "gaming": ["video game", "esports", "gaming setup", "game developer"],
    "cryptocurrency": ["bitcoin", "crypto mining", "blockchain", "ethereum", "nft"],
    "startup culture": ["startup office", "tech company", "silicon valley", "coworking"],
    "automation": ["automated factory", "robotic automation", "self driving car", "ai automation"],
    "big tech": ["tech campus", "google", "apple", "microsoft", "silicon valley"],
    "remote work": ["home office", "remote working", "zoom call", "digital nomad"],

    # ── Documentary Production ───────────────────────────────────
    "archival footage": ["archive film", "historical footage", "vintage film", "old newsreel"],
    "slow motion": ["slow motion", "high speed camera", "slow mo"],
    "cinematic": ["cinematic shot", "film look", "movie scene", "cinematic lighting"],
    "time lapse city": ["city timelapse", "urban timelapse", "traffic timelapse", "skyline timelapse"],
    "nature timelapse": ["flower blooming", "clouds moving", "sunset timelapse", "season change"],
    "establishing shot": ["wide landscape", "cityscape", "aerial wide", "exterior shot"],
    "interview backdrop": ["office background", "bookshelf", "modern interior", "professional setting"],

    # ── Sports & Human Achievement ───────────────────────────────
    "sports": ["stadium", "athlete", "competition", "olympics", "training"],
    "exploration history": ["age of exploration", "sailing ship", "explorer map", "voyage"],
    "human achievement": ["milestone", "record breaking", "human potential", "great accomplishment"],
    "competition": ["contest", "tournament", "championship", "race", "final match"],
    "innovation lab": ["research and development", "innovation center", "prototype workshop", "tech incubator"],
}


def _keyword_expand(base_keyword: str) -> list[str]:
    base = base_keyword.lower().strip()
    for key, aliases in PEXELS_KEYWORD_MAP.items():
        if key in base or base in key:
            return aliases
    return [base, base + " animation", base + " visualization", base + " educational"]


def _handle_rate_limit(resp: requests.Response, source: str, max_retries: int = 1) -> requests.Response:
    """Handle 429 rate limit. Sets cooldown for Pixabay, logs for Pexels."""
    global _PIXABAY_BLOCKED_UNTIL
    if resp.status_code != 429:
        return resp
    if source == "Pixabay":
        cooldown = 60
        print(f"[stock_video] Pixabay rate limited (429) — blocking for {cooldown}s")
        with _PIXABAY_LOCK:
            _PIXABAY_BLOCKED_UNTIL = time.time() + cooldown
        return resp
    wait_time = 10
    retry_header = resp.headers.get('Retry-After')
    if retry_header:
        try:
            wait_time = int(retry_header)
        except ValueError:
            pass
    for attempt in range(max_retries):
        print(f"[stock_video] {source} rate limited (429). Waiting {wait_time}s before retry {attempt+1}/{max_retries}")
        time.sleep(wait_time)
        new_resp = requests.get(resp.url, headers=resp.request.headers, timeout=15)
        if new_resp.status_code != 429:
            return new_resp
        wait_time *= 2
    print(f"[stock_video] {source} still rate limited after {max_retries} retries")
    return resp


def _search_cached(key: str, source: str, orientation: str) -> list[dict]:
    cache_key = f"{source}:{key}:{orientation}"
    if cache_key in _API_CACHE:
        return _API_CACHE[cache_key]
    if source == "pexels":
        result = _search_pexels_uncached(key, orientation)
    else:
        result = _search_pixabay_uncached(key)
    _API_CACHE[cache_key] = result
    return result


def _search_pexels_uncached(query: str, orientation: str = "landscape") -> list[dict]:
    if not PEXELS_API_KEY:
        print("[stock_video] PEXELS_API_KEY is empty — set it in GitHub secrets")
        return []
    if not pexels_breaker.is_available():
        print("[stock_video] Pexels circuit breaker open — skipping")
        return []
    _rate_limit_delay()
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 5, "orientation": orientation}
    try:
        resp = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=15)
        log_stock_call("pexels")
        resp = _handle_rate_limit(resp, "Pexels")
        if resp.status_code == 403:
            print("[stock_video] Pexels API key invalid (403)")
            pexels_breaker.record_failure()
            return []
        resp.raise_for_status()
        pexels_breaker.record_success()
        data = resp.json()
        results = []
        for v in data.get("videos", []):
            vf = v.get("video_files", [])
            if not vf:
                continue
            best = max(vf, key=lambda f: f.get("width", 0) * f.get("height", 0))
            if best.get("width", 0) < 1920 or best.get("height", 0) < 1080:
                continue
            results.append({
                "id": v["id"],
                "url": best.get("link") or best.get("url", ""),
                "width": best.get("width", 1920),
                "height": best.get("height", 1080),
                "duration": v.get("duration", 5),
                "fps": best.get("fps", 30),
                "size": best.get("size", 0),
                "source": "pexels",
                "query": query,
            })
        return results
    except requests.exceptions.HTTPError as e:
        print(f"[stock_video] Pexels HTTP error: {e}")
        pexels_breaker.record_failure()
        return []
    except Exception as e:
        print(f"[stock_video] Pexels search error: {e}")
        pexels_breaker.record_failure()
        return []


def _search_pixabay_uncached(query: str) -> list[dict]:
    if not PIXABAY_API_KEY:
        print("[stock_video] PIXABAY_API_KEY is empty — set it in GitHub secrets")
        return []
    if not pixabay_breaker.is_available():
        print("[stock_video] Pixabay circuit breaker open — skipping")
        return []
    with _PIXABAY_LOCK:
        if time.time() < _PIXABAY_BLOCKED_UNTIL:
            remaining = int(_PIXABAY_BLOCKED_UNTIL - time.time())
            print(f"[stock_video] Pixabay blocked for {remaining}s more — skipping")
            return []
    _rate_limit_delay()
    params = {
        "key": PIXABAY_API_KEY,
        "q": query,
        "video_type": "all",
        "per_page": 5,
        "safesearch": "true",
    }
    try:
        resp = requests.get("https://pixabay.com/api/videos/", params=params, timeout=15)
        log_stock_call("pixabay")
        resp = _handle_rate_limit(resp, "Pixabay")
        if resp.status_code == 403:
            print("[stock_video] Pixabay API key invalid (403)")
            pixabay_breaker.record_failure()
            return []
        resp.raise_for_status()
        pixabay_breaker.record_success()
        data = resp.json()
        results = []
        for v in data.get("hits", []):
            videos = v.get("videos", {})
            if not videos:
                continue
            best_key = max(videos.keys(), key=lambda k: videos[k].get("width", 0))
            best = videos[best_key]
            if best.get("width", 0) < 1920 or best.get("height", 0) < 1080:
                continue
            results.append({
                "id": v["id"],
                "url": best.get("url", ""),
                "width": best.get("width", 1920),
                "height": best.get("height", 1080),
                "duration": v.get("duration", 5),
                "fps": best.get("fps", 30),
                "size": best.get("size", 0),
                "source": "pixabay",
                "query": query,
            })
        return results
    except requests.exceptions.HTTPError as e:
        print(f"[stock_video] Pixabay HTTP error: {e}")
        pixabay_breaker.record_failure()
        return []
    except Exception as e:
        print(f"[stock_video] Pixabay search error: {e}")
        pixabay_breaker.record_failure()
        return []


def download_clip(video_url: str, output_path: Path, timeout: int = 30) -> bool:
    if not video_url:
        return False
    try:
        resp = requests.get(video_url, stream=True, timeout=timeout)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        if output_path.stat().st_size < 1000:
            output_path.unlink(missing_ok=True)
            return False
        return True
    except requests.exceptions.Timeout:
        print(f"[stock_video] Download timeout for {video_url[:50]}")
        return False
    except Exception as e:
        print(f"[stock_video] Download error: {e}")
        return False


def _ffprobe_cmd() -> str:
    env_path = os.getenv("FFPROBE_PATH", "")
    if env_path and os.path.exists(env_path):
        return env_path
    candidates = [
        "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe",
        "/usr/local/bin/ffprobe",
        "/usr/bin/ffprobe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return "ffprobe"


def get_video_duration(file_path: str) -> float:
    try:
        result = safe_run(
            [_ffprobe_cmd(), "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _search_archive_org(query: str) -> list[dict]:
    """Search Internet Archive for CC0/public-domain stock video."""
    import xml.etree.ElementTree as ET
    try:
        url = "https://archive.org/advancedsearch.php"
        params = {
            "q": query + " AND mediatype:(movies)",
            "fl[]": ["identifier", "title", "description", "downloads"],
            "sort[]": "downloads desc",
            "rows": 5,
            "page": 1,
            "output": "xml",
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"opensearch": "http://a9.com/-/spec/opensearch/1.1/"}
        results = []
        for doc in root.findall(".//doc", ns):
            identifier = doc.findtext("str[@name='identifier']") or ""
            title = doc.findtext("str[@name='title']") or ""
            if not identifier:
                continue
            vid_url = f"https://archive.org/download/{identifier}/{identifier}.mp4"
            results.append({
                "id": f"ia_{identifier}",
                "url": vid_url,
                "width": 1920,
                "height": 1080,
                "duration": 30,
                "fps": 30,
                "size": 0,
                "source": "archive_org",
                "query": query,
                "title": title,
            })
        return results
    except Exception as e:
        print(f"[stock_video] Internet Archive search error: {e}")
        return []


def _search_wikimedia(query: str) -> list[dict]:
    """Search Wikimedia Commons for free-license video files."""
    try:
        url = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": f"{query} filetype:video",
            "srlimit": 5,
            "format": "json",
            "srnamespace": 6,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            page_id = item.get("pageid", 0)
            if not title or not page_id:
                continue
            encoded = title.replace(" ", "_")
            vid_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded}"
            results.append({
                "id": f"wm_{page_id}",
                "url": vid_url,
                "width": 1920,
                "height": 1080,
                "duration": 30,
                "fps": 30,
                "size": 0,
                "source": "wikimedia",
                "query": query,
                "title": title.replace("File:", ""),
            })
        return results
    except Exception as e:
        print(f"[stock_video] Wikimedia search error: {e}")
        return []
def _search_providers(keywords: list[str], orientation: str, per_page: int = 5) -> list[dict]:
    all_results = []
    for kw in keywords:
        results = _search_cached(kw, "pexels", orientation)
        all_results.extend(results)
        if results:
            continue
        results = _search_cached(kw, "pixabay", orientation)
        all_results.extend(results)
        if results:
            continue
        archive_results = _search_archive_org(kw)
        all_results.extend(archive_results)
        if archive_results:
            continue
        wm_results = _search_wikimedia(kw)
        all_results.extend(wm_results)
    return all_results


def search_and_download(
    scene_keyword: str,
    target_duration: float = 5.0,
    orientation: str = "landscape",
    scene_idx: int = 0,
) -> Optional[dict]:
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    expanded = _keyword_expand(scene_keyword)
    all_candidates = _search_providers(expanded, orientation)

    if not all_candidates:
        fallback_kw = [scene_keyword, scene_keyword + " video", scene_keyword + " footage"]
        all_candidates = _search_providers(fallback_kw, orientation, per_page=3)

    seen_ids = set()
    unique = []
    for c in all_candidates:
        cid = f"{c['source']}_{c['id']}"
        if cid not in seen_ids:
            seen_ids.add(cid)
            unique.append(c)

    for candidate in unique:
        filename = f"clip_{scene_idx:03d}_{candidate['source']}_{candidate['id']}.mp4"
        output_path = CLIPS_DIR / filename
        if output_path.exists():
            duration = get_video_duration(str(output_path))
            if duration > 0:
                return {
                    "path": str(output_path),
                    "duration": duration,
                    "width": candidate["width"],
                    "height": candidate["height"],
                    "source": candidate["source"],
                    "keyword": candidate["query"],
                }

        if download_clip(candidate["url"], output_path):
            duration = get_video_duration(str(output_path))
            if duration > 0:
                return {
                    "path": str(output_path),
                    "duration": duration,
                    "width": candidate["width"],
                    "height": candidate["height"],
                    "source": candidate["source"],
                    "keyword": candidate["query"],
                }

    print(f"[stock_video] No video found for: {scene_keyword}")
    return None


def _search_single_scene(args: tuple) -> dict | None:
    i, scene, orientation, max_retries = args
    keyword = scene.get("keyword", scene.get("description", ""))
    target_dur = scene.get("target_duration", 5.0)
    for attempt in range(max_retries):
        if attempt > 0:
            time.sleep(2)
        clip = search_and_download(keyword, target_duration=target_dur, orientation=orientation, scene_idx=i)
        if clip:
            print(f"[stock_video] Scene {i+1}: '{keyword}' -> {clip['path']} ({clip['duration']:.1f}s)")
            return clip
    print(f"[stock_video] Scene {i+1}: FAILED for '{keyword}' after {max_retries} attempts")
    return None


def search_videos_for_scenes(scenes: list[dict], orientation: str = "landscape") -> list[dict]:
    max_retries_per_scene = 2
    n = len(scenes)
    from concurrent.futures import ThreadPoolExecutor, as_completed

    args_list = [(i, scene, orientation, max_retries_per_scene) for i, scene in enumerate(scenes)]
    clip_map = {}
    with ThreadPoolExecutor(max_workers=min(n, 8)) as executor:
        futures = {executor.submit(_search_single_scene, args): i for i, args in enumerate(args_list)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                clip = future.result()
                if clip:
                    clip_map[idx] = clip
            except Exception as e:
                print(f"[stock_video] Scene {idx+1} search failed: {e}")

    clips = [clip_map[i] for i in sorted(clip_map) if clip_map[i] is not None]

    return clips
