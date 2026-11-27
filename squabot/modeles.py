"""Téléchargement unique des modèles gratuits (voix, profondeur), gardés en cache."""
import os, urllib.request
from pathlib import Path

CACHE = Path(os.environ.get("SQUABOT_CACHE", Path.home() / ".cache" / "squabot"))
FICHIERS = {
    "kokoro.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
    "depth.onnx": "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model.onnx",
    # Real-ESRGAN général x4 (BSD-3) : deux fichiers qui doivent rester côte à côte
    "esrgan/model.onnx": "https://huggingface.co/TheGuy444/Real-ESRGAN-ONNX/resolve/main/onnx/model.onnx",
    "clip/model_quantized.onnx": "https://huggingface.co/onnx-community/clip-vit-base-patch32-ONNX/resolve/main/onnx/model_quantized.onnx",
    "clip/tokenizer.json": "https://huggingface.co/onnx-community/clip-vit-base-patch32-ONNX/resolve/main/tokenizer.json",
    "esrgan/model.data": "https://huggingface.co/TheGuy444/Real-ESRGAN-ONNX/resolve/main/onnx/model.data",
}


def chemin(nom):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / nom
    p.parent.mkdir(parents=True, exist_ok=True)
    if nom == "esrgan/model.onnx": chemin("esrgan/model.data")
    if not p.exists() or p.stat().st_size == 0:
        print(f"Téléchargement de {nom}…", flush=True)
        tmp = p.with_suffix(".part")
        urllib.request.urlretrieve(FICHIERS[nom], tmp)
        tmp.rename(p)
    return str(p)
