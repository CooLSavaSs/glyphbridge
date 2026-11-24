# Glyphbridge

**Traducción gratuita, sin conexión y de código abierto para todas las escrituras: desde los idiomas modernos hasta el turco otomano, los jeroglíficos y la escritura cuneiforme.**

🌐 [English](../../README.md) · [Türkçe](README.tr.md) · **Español** · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md) · [中文](README.zh.md) · [日本語](README.ja.md)

> ⚠️ **Estado: desarrollo temprano.** Glyphbridge se construye de forma abierta. Las funciones marcadas como *planificadas* aún no existen: nos encantaría que nos ayudaras a crearlas.

## ¿Por qué Glyphbridge?

- **Gratis para siempre**: código abierto con licencia Apache 2.0, sin registro; las claves de API solo se usan si expones tu propio servidor.
- **Privado y sin conexión**: todo se ejecuta en tu propio ordenador; tus documentos nunca salen de él.
- **Ligero**: diseñado para funcionar bien en un PC normal con **8 GB de RAM**, sin GPU.
- **Honesto con la calidad**: cada traducción incluye una **puntuación de confianza**, y publicamos la calidad medida (COMET / chrF) por par de idiomas.
- **Para todas las escrituras**: texto, fotos, documentos, voz y sistemas de escritura históricos.

## Funciones y hoja de ruta

| Versión | Función | Estado |
|---|---|---|
| **v0.1** | Traducción de texto, primeros 10–20 idiomas, línea de comandos + interfaz sencilla, modelo cuantizado (int8) | 🚧 En desarrollo |
| **v0.2** | Traducción de texto en **imágenes** (OCR) y **documentos** (PDF, DOCX) conservando el formato; filtro de confianza | 📋 Planificado |
| **v0.3** | Traducción de **voz**: voz → texto → traducción → voz | 📋 Planificado |
| **v0.4** | **Turco otomano**: OCR impreso y manuscrito (rika, divani), transliteración, turco moderno | 📋 Planificado |
| **Experimental** | **Jeroglíficos egipcios** y **cuneiforme** (acadio, sumerio), en colaboración con investigadores | 🔬 Investigación |

## Úsalo en cualquier lugar (planificado)

| Interfaz | Ejemplo |
|---|---|
| Biblioteca de Python | `glyphbridge.translate("Merhaba", to="en")` |
| Línea de comandos | `glyphbridge translate file.pdf --to de` |
| API REST | `glyphbridge serve` → `POST /v1/translate` (Clave de API opcional) |
| Agentes de IA (MCP) | Úsalo como herramienta desde Claude y otros asistentes de IA |
| Endpoint compatible con OpenAI | Conéctalo a herramientas de IA existentes sin cambiar código |

Todo es autoalojado y gratuito. Las claves de API protegen tu servidor cuando lo expones a una red.

## Contribuir

- 🌍 Traduce este README a tu idioma: una primera contribución perfecta
- 🧪 Prueba las traducciones en tu lengua materna e informa de errores
- 🐍 Escribe código (Python): busca issues con la etiqueta `good first issue`
- 📜 Ayuda con escrituras históricas si eres lingüista, historiador o egiptólogo

Consulta [CONTRIBUTING.md](../../CONTRIBUTING.md) para empezar.

## Licencia

[Apache 2.0](../../LICENSE) — libre para usar, modificar y compartir, también con fines comerciales.
