"""
generator.py — Uses Claude API to generate:
  1. State-of-the-art summary per topic (structured markdown)
  2. Full podcast dialogue script (~30 min, 2 speakers)
"""

import os
import json
import logging
import anthropic
from datetime import datetime

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = "claude-opus-4-5"

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _articles_to_text(articles: list[dict], max_articles: int = 20) -> str:
    """Formats article list as readable text for the prompt."""
    lines = []
    for i, art in enumerate(articles[:max_articles], 1):
        citations = f" [Citas: {art['citation_count']}]" if art.get("citation_count") else ""
        lines.append(
            f"{i}. [{art['journal']} | {art['pub_date']}]{citations}\n"
            f"   Título: {art['title']}\n"
            f"   Autores: {art['authors']}\n"
            f"   Abstract: {art['abstract'][:600]}...\n"
            f"   URL: {art['url']}\n"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Per-topic summary
# ─────────────────────────────────────────────

SUMMARY_SYSTEM = """Eres un radiólogo torácico experto con amplio conocimiento clínico e investigador. 
Tu tarea es analizar artículos científicos recientes y elaborar resúmenes ejecutivos de alta calidad 
para actualización profesional de radiólogos. 
Escribe siempre en español científico claro, preciso y sin jerga innecesaria.
Estructura el contenido de forma didáctica y orientada a la práctica clínica."""

SUMMARY_PROMPT = """Analiza los siguientes artículos científicos publicados recientemente sobre el tema: **{topic_name}**

Periodo cubierto: {date_from} a {date_to}

=== ARTÍCULOS DE REVISTAS SELECCIONADAS ===
{curated_articles}

=== TOP 10 MÁS CITADOS (otras revistas) ===
{top_cited}

Elabora un **resumen ejecutivo de actualización (State of the Art)** con la siguiente estructura:

## {topic_name} — Actualización {month_year}

### Puntos Clave
(3-5 bullets con los hallazgos más importantes del periodo)

### Contexto y Tendencias
(2-3 párrafos sobre el estado actual del conocimiento y hacia dónde evoluciona el campo)

### Novedades Principales
(Para cada artículo relevante: título, revista, hallazgo principal y relevancia clínica práctica)

### Implicaciones para la Práctica
(Cómo estos hallazgos cambian o refuerzan la práctica radiológica actual)

### Artículos de Referencia del Periodo
(Lista bibliográfica de los artículos más importantes con URL)

---
Sé crítico y selectivo: destaca solo lo verdaderamente relevante. Omite trabajos metodológicamente débiles.
Incluye siempre la relevancia clínica práctica de cada hallazgo.
"""


def generate_topic_summary(topic_data: dict) -> str:
    """Generates a markdown summary for one topic."""
    topic_name = topic_data["topic_name"]
    month_year = datetime.today().strftime("%B %Y")

    curated_text = _articles_to_text(topic_data.get("pubmed_articles", []))
    top_cited_text = _articles_to_text(topic_data.get("top_cited_articles", []))

    if not curated_text and not top_cited_text:
        return f"## {topic_name}\n\n*No se encontraron artículos relevantes en el periodo analizado.*\n"

    prompt = SUMMARY_PROMPT.format(
        topic_name=topic_name,
        date_from=topic_data.get("date_from", ""),
        date_to=topic_data.get("date_to", ""),
        curated_articles=curated_text or "No se encontraron artículos en las revistas seleccionadas.",
        top_cited=top_cited_text or "No se encontraron artículos adicionales.",
        month_year=month_year,
    )

    logger.info(f"Generating summary for: {topic_name}")
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=3000,
            system=SUMMARY_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Summary generation error for {topic_name}: {e}")
        return f"## {topic_name}\n\n*Error generando resumen: {e}*\n"


# ─────────────────────────────────────────────
# Podcast script
# ─────────────────────────────────────────────

PODCAST_SYSTEM = """Eres un guionista especializado en podcasts médicos científicos de alta calidad.
Creas diálogos naturales, didácticos y entretenidos entre dos radiólogos expertos.
El podcast debe sonar como una conversación real entre colegas: fluida, con opiniones, matices y ejemplos clínicos.
Escribe siempre en español neutro, sin tecnicismos innecesarios, accesible para cualquier médico especialista."""

PODCAST_PROMPT = """Crea el guion completo de un podcast de 30 minutos sobre las novedades más relevantes 
en radiología torácica del último mes.

RESÚMENES DE CADA TEMA:
{all_summaries}

FORMATO DEL GUION:
- Dos presentadores: **Ana** (radióloga generalista con subespecialidad torácica) y **Carlos** (radiólogo especialista cardiovascular)
- Duración objetivo: 30 minutos (~4500 palabras de diálogo)
- Tono: profesional pero cercano, como una conversación entre colegas expertos
- Estructura:
  * [00:00] Intro y bienvenida (1 min)
  * [01:00] Resumen rápido de los temas del episodio
  * [03:00] Desarrollo de cada tema (~2-3 min por tema, priorizando los más relevantes)
  * [28:00] Conclusiones y "artículo del mes"
  * [29:30] Cierre

INSTRUCCIONES:
- Incluye marcas de tiempo [MM:SS] cada cierto tiempo
- Marca cada turno de palabra con **ANA:** o **CARLOS:**
- Incluye referencias naturales a los artículos ("en el estudio de Radiology de este mes...")
- Añade comentarios de valor clínico práctico
- Incluye 1-2 momentos de debate o discrepancia leve entre los presentadores
- Termina con un "artículo del mes" elegido consensuadamente

Genera el guion completo ahora:"""


def generate_podcast_script(all_topic_summaries: list[dict]) -> str:
    """Generates a complete ~30 min podcast script from all topic summaries."""
    # Condense summaries for the prompt (avoid token overflow)
    condensed = []
    for ts in all_topic_summaries:
        condensed.append(
            f"### {ts['topic_name']}\n"
            f"{ts['summary'][:1500]}\n---\n"
        )

    all_summaries_text = "\n".join(condensed)

    prompt = PODCAST_PROMPT.format(all_summaries=all_summaries_text)

    logger.info("Generating podcast script...")
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=6000,
            system=PODCAST_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Podcast script generation error: {e}")
        return f"Error generando guion del podcast: {e}"


# ─────────────────────────────────────────────
# Full report
# ─────────────────────────────────────────────

def generate_all(all_topic_data: list[dict]) -> dict:
    """
    Main entry point. Generates summaries for all topics + podcast script.
    Returns dict with all content ready for rendering.
    """
    month_year = datetime.today().strftime("%B %Y").capitalize()
    topic_summaries = []

    for topic_data in all_topic_data:
        summary_md = generate_topic_summary(topic_data)
        topic_summaries.append({
            "topic_id": topic_data["topic_id"],
            "topic_name": topic_data["topic_name"],
            "is_adhoc": topic_data.get("is_adhoc", False),
            "summary": summary_md,
            "article_count": len(topic_data.get("pubmed_articles", [])) +
                             len(topic_data.get("top_cited_articles", [])),
        })

    podcast_script = generate_podcast_script(topic_summaries)

    return {
        "month_year": month_year,
        "generated_at": datetime.today().isoformat(),
        "topic_summaries": topic_summaries,
        "podcast_script": podcast_script,
    }
