# Glyphbridge

**Kostenlose, offline nutzbare Open-Source-Übersetzung für jede Schrift – von modernen Sprachen bis zu Osmanisch-Türkisch, Hieroglyphen und Keilschrift.**

🌐 [English](../../README.md) · [Türkçe](README.tr.md) · [Español](README.es.md) · [Français](README.fr.md) · **Deutsch** · [Português](README.pt.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md) · [中文](README.zh.md) · [日本語](README.ja.md)

> ⚠️ **Status: frühe Entwicklung.** Glyphbridge wird offen entwickelt. Als *geplant* markierte Funktionen gibt es noch nicht – wir freuen uns über deine Hilfe.

## Warum Glyphbridge?

- **Für immer kostenlos** – Open Source unter Apache-2.0-Lizenz, ohne Registrierung; API-Schlüssel nur, wenn du deinen eigenen Server freigibst.
- **Privat und offline** – alles läuft auf deinem eigenen Computer; deine Dokumente verlassen ihn nie.
- **Leicht** – ausgelegt für einen normalen PC mit **8 GB RAM**, ohne GPU.
- **Ehrlich bei der Qualität** – jede Übersetzung hat einen **Konfidenzwert**, und wir veröffentlichen gemessene Qualität (COMET / chrF) pro Sprachpaar.
- **Für jede Schrift** – Text, Fotos, Dokumente, Sprache und historische Schriftsysteme.

## Funktionen und Roadmap

| Version | Funktion | Status |
|---|---|---|
| **v0.1** | Textübersetzung, erste 10–20 Sprachen, Kommandozeile + einfache Oberfläche, quantisiertes Modell (int8) | 🚧 In Arbeit |
| **v0.2** | Text in **Bildern** (OCR) und **Dokumenten** (PDF, DOCX) mit erhaltenem Layout übersetzen; Konfidenzfilter | 📋 Geplant |
| **v0.3** | **Sprach**übersetzung: Sprache → Text → Übersetzung → Sprache | 📋 Geplant |
| **v0.4** | **Osmanisch-Türkisch**: OCR für Druck- und Handschrift (Rika, Divani), Transliteration, modernes Türkisch | 📋 Geplant |
| **Experimentell** | **Ägyptische Hieroglyphen** und **Keilschrift** (Akkadisch, Sumerisch) – gemeinsam mit Forschenden | 🔬 Forschung |

## Überall nutzbar (geplant)

| Schnittstelle | Beispiel |
|---|---|
| Python-Bibliothek | `glyphbridge.translate("Merhaba", to="en")` |
| Kommandozeile | `glyphbridge translate file.pdf --to de` |
| REST-API | `glyphbridge serve` → `POST /v1/translate` (optionaler API-Schlüssel) |
| KI-Agenten (MCP) | Als Werkzeug in Claude und anderen KI-Assistenten nutzen |
| OpenAI-kompatibler Endpunkt | Ohne Codeänderung an bestehende KI-Tools anbinden |

Alles ist selbst gehostet und kostenlos. API-Schlüssel schützen deinen Server, wenn du ihn im Netzwerk freigibst.

## Mitmachen

- 🌍 Übersetze diese README in deine Sprache – ein idealer erster Beitrag
- 🧪 Teste Übersetzungen in deiner Muttersprache und melde Fehler
- 🐍 Schreibe Code (Python) – suche nach Issues mit `good first issue`
- 📜 Hilf bei historischen Schriften, wenn du Linguist:in, Historiker:in oder Ägyptolog:in bist

Siehe [CONTRIBUTING.md](../../CONTRIBUTING.md) für den Einstieg.

## Lizenz

[Apache 2.0](../../LICENSE) — frei nutzbar, veränderbar und teilbar, auch kommerziell.
