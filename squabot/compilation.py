"""Compilation longue pour YouTube (format qui rapporte le plus) : les meilleures vidéos d'un compte bout à bout,
en 16:9, avec un fond flou, un carton d'ouverture et un numéro par histoire."""
import json, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from . import config
from .rendu import police, hexa, ajuste

LW, LH = 1920, 1080


def carton(texte, sous, couleurs, sortie, duree=3.0):
    fond, orr, pap = hexa(couleurs["fond"]), hexa(couleurs["or"]), hexa(couleurs["papier"])
    im = Image.new("RGB", (LW, LH), fond); d = ImageDraw.Draw(im)
    d.text((LW / 2, LH / 2 - 40), texte.upper(), font=ajuste(texte.upper(), "noir", 120, 1700), fill=orr, anchor="mm")
    if sous: d.text((LW / 2, LH / 2 + 70), sous, font=ajuste(sous, "mono", 44, 1600), fill=pap, anchor="mm")
    png = str(sortie) + ".png"; im.save(png)
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-loop", "1", "-i", png, "-f", "lavfi", "-i",
                    "anullsrc=r=48000:cl=stereo", "-t", str(duree), "-vf", "fade=in:0:12,fade=out:st=%.2f:d=0.4" % (duree - 0.4),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-shortest", str(sortie)], check=True)


def en_paysage(src, sortie):
    """9:16 -> 16:9 : la vidéo au centre, la même vidéo floutée et agrandie derrière."""
    vf = ("[0:v]split[a][b];[a]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=30:3,"
          "eq=brightness=-0.12[fond];[b]scale=-2:1080[av];[fond][av]overlay=(W-w)/2:0,fps=30,format=yuv420p")
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src), "-filter_complex", vf,
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(sortie)], check=True)


def compiler(compte_id, titre, videos, sortie, travail):
    c = config.compte(compte_id); coul = c["theme_detail"]["style_visuel"]["couleurs"]
    travail = Path(travail); travail.mkdir(parents=True, exist_ok=True)
    morceaux = [travail / "00-ouverture.mp4"]
    carton(titre, c["nom"], coul, morceaux[0], 3.5)
    for i, (t, f) in enumerate(videos, 1):
        cart = travail / f"{i:02d}a.mp4"; carton(f"N°{i}", t, coul, cart, 2.0)
        corps = travail / f"{i:02d}b.mp4"; en_paysage(f, corps)
        morceaux += [cart, corps]
    liste = travail / "liste.txt"
    liste.write_text("".join(f"file '{m.resolve()}'\n" for m in morceaux))
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(liste),
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", str(sortie)], check=True)
    return sortie
