# Glyphbridge

**Traduction gratuite, hors ligne et open source pour toutes les écritures : des langues modernes au turc ottoman, aux hiéroglyphes et à l'écriture cunéiforme.**

🌐 [English](../../README.md) · [Türkçe](README.tr.md) · [Español](README.es.md) · **Français** · [Deutsch](README.de.md) · [Português](README.pt.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md) · [中文](README.zh.md) · [日本語](README.ja.md)

> ⚠️ **Statut : développement précoce.** Glyphbridge est construit en public. Les fonctionnalités marquées *prévues* n'existent pas encore — votre aide est la bienvenue.

## Pourquoi Glyphbridge ?

- **Gratuit pour toujours** : open source sous licence Apache 2.0, sans inscription ; clés API uniquement si vous exposez votre propre serveur.
- **Privé et hors ligne** : tout fonctionne sur votre ordinateur ; vos documents ne le quittent jamais.
- **Léger** : conçu pour bien fonctionner sur un PC ordinaire avec **8 Go de RAM**, sans GPU.
- **Honnête sur la qualité** : chaque traduction a un **score de confiance**, et nous publions la qualité mesurée (COMET / chrF) pour chaque paire de langues.
- **Pour toutes les écritures** : texte, photos, documents, parole et systèmes d'écriture historiques.

## Fonctionnalités et feuille de route

| Version | Fonctionnalité | Statut |
|---|---|---|
| **v0.1** | Traduction de texte, 10 à 20 premières langues, ligne de commande + interface simple, modèle quantifié (int8) | 🚧 En cours |
| **v0.2** | Traduction du texte dans les **images** (OCR) et les **documents** (PDF, DOCX) en conservant la mise en page ; filtre de confiance | 📋 Prévu |
| **v0.3** | Traduction **vocale** : parole → texte → traduction → parole | 📋 Prévu |
| **v0.4** | **Turc ottoman** : OCR imprimé et manuscrit (rika, divani), translittération, turc moderne | 📋 Prévu |
| **Expérimental** | **Hiéroglyphes égyptiens** et **cunéiforme** (akkadien, sumérien), en collaboration avec des chercheurs | 🔬 Recherche |

## Utilisable partout (prévu)

| Interface | Exemple |
|---|---|
| Bibliothèque Python | `glyphbridge.translate("Merhaba", to="en")` |
| Ligne de commande | `glyphbridge translate file.pdf --to de` |
| API REST | `glyphbridge serve` → `POST /v1/translate` (clé API facultative) |
| Agents IA (MCP) | Utilisez-le comme outil depuis Claude et d'autres assistants IA |
| Endpoint compatible OpenAI | Connectez-le aux outils IA existants sans modifier le code |

Tout est auto-hébergé et gratuit. Les clés API protègent votre serveur lorsque vous l'exposez sur un réseau.

## Contribuer

- 🌍 Traduisez ce README dans votre langue — une première contribution idéale
- 🧪 Testez les traductions dans votre langue maternelle et signalez les erreurs
- 🐍 Écrivez du code (Python) — cherchez les issues `good first issue`
- 📜 Aidez-nous sur les écritures historiques si vous êtes linguiste, historien ou égyptologue

Voir [CONTRIBUTING.md](../../CONTRIBUTING.md) pour commencer.

## Licence

[Apache 2.0](../../LICENSE) — libre d'utilisation, de modification et de partage, y compris commercialement.
