"""Which PyPI distributions provide an import name (#16).

Most distributions are imported under their own name, or a predictable variant
of it (``python-dateutil`` -> ``dateutil``, ``pyyaml`` -> ``yaml``,
``google-cloud-storage`` -> ``google``). ``provides`` handles those by rule.
``IMPORT_NAMES`` lists the rest: imports whose distribution has an unrelated
name. Its keys are also known to be real, so they are never looked up on PyPI.
"""

from __future__ import annotations

import re

from slopfence.registry import normalize

IMPORT_NAMES: dict[str, tuple[str, ...]] = {
    "_pytest": ("pytest",),
    "adafruit_blinka": ("adafruit-blinka",),
    "allauth": ("django-allauth",),
    "apiclient": ("google-api-python-client",),
    "argon2": ("argon2-cffi",),
    "attr": ("attrs",),
    "Bio": ("biopython",),
    "board": ("adafruit-blinka",),
    "bs4": ("beautifulsoup4",),
    "bson": ("pymongo",),
    "busio": ("adafruit-blinka",),
    "cairo": ("pycairo",),
    "community": ("python-louvain",),
    "corsheaders": ("django-cors-headers",),
    "crispy_forms": ("django-crispy-forms",),
    "Crypto": ("pycryptodome", "pycrypto"),
    "Cryptodome": ("pycryptodomex",),
    "cv2": (
        "opencv-python",
        "opencv-contrib-python",
        "opencv-python-headless",
        "opencv-contrib-python-headless",
    ),
    "dateutil": ("python-dateutil",),
    "debug_toolbar": ("django-debug-toolbar",),
    "decouple": ("python-decouple",),
    "digitalio": ("adafruit-blinka",),
    "distutils": ("setuptools",),
    "django_filters": ("django-filter",),
    "dns": ("dnspython",),
    "docx": ("python-docx",),
    "dotenv": ("python-dotenv",),
    "editor": ("python-editor",),
    "engineio": ("python-engineio",),
    "environ": ("django-environ",),
    "factory": ("factory-boy",),
    "faiss": ("faiss-cpu", "faiss-gpu"),
    "fitz": ("pymupdf",),
    "gi": ("pygobject",),
    "git": ("gitpython",),
    "google": ("protobuf", "google-api-core", "googleapis-common-protos"),
    "googleapiclient": ("google-api-python-client",),
    "gridfs": ("pymongo",),
    "grpc": ("grpcio",),
    "igraph": ("python-igraph", "igraph"),
    "imblearn": ("imbalanced-learn",),
    "jose": ("python-jose",),
    "jwt": ("pyjwt",),
    "kafka": ("kafka-python",),
    "keras": ("keras", "tensorflow"),
    "ldap": ("python-ldap",),
    "Levenshtein": ("levenshtein", "python-levenshtein"),
    "libfuturize": ("future",),
    "libpasteurize": ("future",),
    "magic": ("python-magic",),
    "memcache": ("python-memcached",),
    "mpl_toolkits": ("matplotlib",),
    "multipart": ("python-multipart",),
    "MySQLdb": ("mysqlclient",),
    "nacl": ("pynacl",),
    "newspaper": ("newspaper3k",),
    "OpenGL": ("pyopengl",),
    "OpenSSL": ("pyopenssl",),
    "osgeo": ("gdal",),
    "past": ("future",),
    "PIL": ("pillow",),
    "pkg_resources": ("setuptools",),
    "pptx": ("python-pptx",),
    "psycopg2": ("psycopg2", "psycopg2-binary"),
    "pylab": ("matplotlib",),
    "pythoncom": ("pywin32",),
    "pywintypes": ("pywin32",),
    "pywt": ("pywavelets",),
    "rest_framework": ("djangorestframework",),
    "rest_framework_simplejwt": ("djangorestframework-simplejwt",),
    "RPi": ("rpi-gpio",),
    "serial": ("pyserial",),
    "skimage": ("scikit-image",),
    "sklearn": ("scikit-learn",),
    "skopt": ("scikit-optimize",),
    "slugify": ("python-slugify",),
    "socketio": ("python-socketio",),
    "socks": ("pysocks",),
    "storages": ("django-storages",),
    "telegram": ("python-telegram-bot",),
    "tflite_runtime": ("tflite-runtime",),
    "umap": ("umap-learn",),
    "usb": ("pyusb",),
    "websocket": ("websocket-client",),
    "win32api": ("pywin32",),
    "win32com": ("pywin32",),
    "win32con": ("pywin32",),
    "win32gui": ("pywin32",),
    "win32process": ("pywin32",),
    "wx": ("wxpython",),
    "xdist": ("pytest-xdist",),
    "Xlib": ("python-xlib",),
    "yaml": ("pyyaml",),
    "zmq": ("pyzmq",),
    # Imported under their own name, but too common to look up every time.
    "jinja2": ("jinja2",),
    "lxml": ("lxml",),
    "markdown": ("markdown",),
    "pydantic_core": ("pydantic-core",),
    "pytest": ("pytest",),
    "sentry_sdk": ("sentry-sdk",),
    "setuptools": ("setuptools",),
    "six": ("six",),
    "tensorflow": ("tensorflow",),
    "torch": ("torch",),
    "torchvision": ("torchvision",),
    "typing_extensions": ("typing-extensions",),
}

_PREFIXES = ("python-", "py-", "py")
_SUFFIXES = ("-python", "python", "-py", "-py3", "-binary", "-headless")


def _squash(name: str) -> str:
    """Lowercase with all separators removed (``Speech_Recognition`` -> ``speechrecognition``)."""
    return re.sub(r"[-_.]+", "", name).lower()


def provides(distribution: str, module: str) -> bool:
    """Whether installing ``distribution`` plausibly provides ``import module``."""
    dist, mod = normalize(distribution), normalize(module)
    if _squash(dist) == _squash(mod):
        return True
    if dist in IMPORT_NAMES.get(module, ()):
        return True
    # Namespace packages: google-cloud-storage, azure-storage-blob, zope.interface.
    if dist.startswith(mod + "-"):
        return True
    for prefix in _PREFIXES:
        if dist.startswith(prefix) and _squash(dist[len(prefix) :]) == _squash(mod):
            return True
    return any(
        dist.endswith(suffix) and _squash(dist[: -len(suffix)]) == _squash(mod)
        for suffix in _SUFFIXES
    )
