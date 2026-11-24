# Glyphbridge

**Tradução gratuita, offline e de código aberto para todas as escritas — das línguas modernas ao turco otomano, aos hieróglifos e à escrita cuneiforme.**

🌐 [English](../../README.md) · [Türkçe](README.tr.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · **Português** · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md) · [中文](README.zh.md) · [日本語](README.ja.md)

> ⚠️ **Status: desenvolvimento inicial.** O Glyphbridge está sendo construído de forma aberta. Os recursos marcados como *planejados* ainda não existem — adoraríamos sua ajuda.

## Por que Glyphbridge?

- **Grátis para sempre** — código aberto sob a licença Apache 2.0, sem cadastro; chaves de API só se você expuser seu próprio servidor.
- **Privado e offline** — tudo roda no seu computador; seus documentos nunca saem dele.
- **Leve** — projetado para rodar bem em um PC comum com **8 GB de RAM**, sem GPU.
- **Honesto sobre a qualidade** — cada tradução vem com uma **pontuação de confiança**, e publicamos a qualidade medida (COMET / chrF) por par de idiomas.
- **Para todas as escritas** — texto, fotos, documentos, fala e sistemas de escrita históricos.

## Recursos e roteiro

| Versão | Recurso | Status |
|---|---|---|
| **v0.1** | Tradução de texto, primeiros 10–20 idiomas, linha de comando + interface simples, modelo quantizado (int8) | 🚧 Em andamento |
| **v0.2** | Tradução de texto em **imagens** (OCR) e **documentos** (PDF, DOCX) mantendo o layout; filtro de confiança | 📋 Planejado |
| **v0.3** | Tradução de **voz**: fala → texto → tradução → fala | 📋 Planejado |
| **v0.4** | **Turco otomano**: OCR impresso e manuscrito (rika, divani), transliteração, turco moderno | 📋 Planejado |
| **Experimental** | **Hieróglifos egípcios** e **cuneiforme** (acádio, sumério), em colaboração com pesquisadores | 🔬 Pesquisa |

## Use em qualquer lugar (planejado)

| Interface | Exemplo |
|---|---|
| Biblioteca Python | `glyphbridge.translate("Merhaba", to="en")` |
| Linha de comando | `glyphbridge translate file.pdf --to de` |
| API REST | `glyphbridge serve` → `POST /v1/translate` (chave de API opcional) |
| Agentes de IA (MCP) | Use como ferramenta no Claude e em outros assistentes de IA |
| Endpoint compatível com OpenAI | Conecte a ferramentas de IA existentes sem mudar o código |

Tudo é auto-hospedado e gratuito. As chaves de API protegem seu servidor quando você o expõe em uma rede.

## Contribuir

- 🌍 Traduza este README para o seu idioma — uma ótima primeira contribuição
- 🧪 Teste traduções na sua língua materna e relate erros
- 🐍 Escreva código (Python) — procure issues com `good first issue`
- 📜 Ajude com escritas históricas se você for linguista, historiador ou egiptólogo

Veja [CONTRIBUTING.md](../../CONTRIBUTING.md) para começar.

## Licença

[Apache 2.0](../../LICENSE) — livre para usar, modificar e compartilhar, inclusive comercialmente.
