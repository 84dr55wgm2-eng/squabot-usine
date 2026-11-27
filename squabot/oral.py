"""Texte écrit -> texte « à dire » : on parle comme on parle vraiment (registre jeune), et on corrige ce que les voix
de synthèse prononcent mal (lettres muettes). Les sous-titres gardent le texte écrit ; seule la voix lit ceci."""
import re

# (motif, remplacement) appliqués dans l'ordre, insensibles à la casse ; \b = limite de mot
FR_PRONONCIATION = [                      # pour toutes les voix et tous les registres
    (r"\battends\b", "attend"), (r"\bentends\b", "entend"), (r"\bprends\b", "prend"), (r"\bcomprends\b", "comprend"),
    (r"\bvends\b", "vend"), (r"\bréponds\b", "répond"), (r"\bdescends\b", "descend"), (r"\bdéfends\b", "défend"),
    (r"\bmets\b", "met"), (r"\bsais\b", "sai"), (r"\bfais\b", "fai"), (r"\bvais\b", "vai"),
    (r"\bplus\s+(?=jamais|rien|personne|du tout)", "plu "),
]
FR_JEUNE = [
    (r"\bje ne sais pas\b", "j'sais pas"), (r"\bje ne\b", "j'"), (r"\bne\s+(?=\w+\s+(pas|plus|jamais|rien|personne)\b)", ""),
    (r"\bn'(?=\w+\s+(pas|plus|jamais|rien|personne)\b)", ""),
    (r"\bpersonne ne\b", "personne"), (r"\brien ne\b", "rien"),
    (r"\bil y a\b", "y a"), (r"\bil n'y a\b", "y a"), (r"\bje suis\b", "j'suis"), (r"\btu es\b", "t'es"), (r"\btu as\b", "t'as"),
    (r"\bje te\b", "j'te"), (r"\bje me\b", "j'me"), (r"\bje le\b", "j'le"), (r"\bce que\b", "c'que"), (r"\bparce que\b", "pasque"),
    (r"\bde l'", "d'l'"), (r"\bde le\b", "du"), (r"\bque tu\b", "qu'tu"), (r"\bpeut-être\b", "p't-être"),
    (r"\bje\s+(?=[bcdfghjklmnpqrstvwxz])", "j'"), (r"\bcelui-là\b", "c'lui-là"), (r"\bpetit\b", "p'tit"), (r"\bpetite\b", "p'tite"),
]
EN_JEUNE = [
    (r"\bgoing to\b", "gonna"), (r"\bwant to\b", "wanna"), (r"\bgot to\b", "gotta"), (r"\bkind of\b", "kinda"),
    (r"\bsort of\b", "sorta"), (r"\bout of\b", "outta"), (r"\bdo not\b", "don't"), (r"\bcannot\b", "can't"), (r"\bit is\b", "it's"),
    (r"\bthat is\b", "that's"), (r"\bthey are\b", "they're"), (r"\byou are\b", "you're"), (r"\bI am\b", "I'm"), (r"\bdid not\b", "didn't"),
    (r"\bwas not\b", "wasn't"), (r"\bwould have\b", "would've"), (r"\bcould have\b", "could've"), (r"\bshould have\b", "should've"),
]
ES_JEUNE = [
    (r"\bpara el\b", "pa'l"), (r"\bpara\b", "pa'"), (r"\btodo el\b", "to' el"), (r"\bestá\b", "'tá"), (r"\bestás\b", "'tás"),
    (r"\bnada\b", "na'"), (r"\bpues\b", "pos"), (r"\bmuy\b", "re" ),
]
ES_JEUNE_AR = ES_JEUNE                      # « re » (très) est surtout argentin ; retiré ailleurs ci-dessous
REGLES = {"fr": (FR_PRONONCIATION, FR_JEUNE), "en": ([], EN_JEUNE), "es": ([], [r for r in ES_JEUNE if r[1] != "re"])}


def _appliquer(texte, regles):
    for motif, remp in regles:
        def r(m, remp=remp):
            s = m.group(0)
            out = re.sub(motif, remp, s, flags=re.I) if "\\" in remp else remp
            return out[0].upper() + out[1:] if s[:1].isupper() and out else out
        texte = re.sub(motif, r, texte, flags=re.I)
    return re.sub(r"'\s+", "'", texte)


def a_dire(texte, langue="fr", registre="jeune", accent=None):
    prononciation, jeune = REGLES.get(langue, ([], []))
    if langue == "es" and accent == "es-AR": jeune = ES_JEUNE_AR
    t = _appliquer(texte, prononciation)
    if registre == "jeune": t = _appliquer(t, jeune)
    return t


# Indication d'émotion par phrase (VoxCPM2) : déduite de la ponctuation et des mots, pour que le ton ne retombe pas
def emotion(phrase, registre="jeune"):
    p = phrase.strip()
    if registre == "pose": return "calm, intriguing, slow"
    if p.endswith("?"): return "curious, surprised, rising intonation"
    if p.endswith("!"): return "excited, energetic"
    if re.search(r"\b(pire|incroyable|dingue|fou|folle|jamais|personne|insane|crazy|wild|locura|nadie)\b", p, re.I):
        return "amazed, emphatic, energetic"
    if p.endswith("…") or p.endswith("..."): return "suspenseful, teasing"
    return "lively, friendly, smiling"


def phrases(texte):
    return [x.strip() for x in re.split(r"(?<=[.!?…])\s+|\n+", texte) if x.strip()]
