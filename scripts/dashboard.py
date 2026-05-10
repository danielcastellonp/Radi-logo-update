"""
dashboard.py — Builds the static HTML dashboard for GitHub Pages.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
import markdown

logger = logging.getLogger(__name__)

TOPIC_COLORS = {
    "infecciones": "#e74c3c",
    "epid": "#8e44ad",
    "neoplasia": "#2980b9",
    "nodulo": "#27ae60",
    "epoc_via_aerea": "#f39c12",
    "tep_htp": "#c0392b",
    "cardiopatia_isquemica": "#e67e22",
    "miocardiopatias": "#d35400",
    "rm_toracica": "#16a085",
    "imagen_cardiaca": "#2c3e50",
    "ia_radiologia": "#1abc9c",
}

TOPIC_ICONS = {
    "infecciones": "🦠",
    "epid": "🫁",
    "neoplasia": "🔬",
    "nodulo": "⭕",
    "epoc_via_aerea": "💨",
    "tep_htp": "🩸",
    "cardiopatia_isquemica": "❤️",
    "miocardiopatias": "🫀",
    "rm_toracica": "🧲",
    "imagen_cardiaca": "📡",
    "ia_radiologia": "🤖",
}


def _render_markdown(md_text: str) -> str:
    try:
        return markdown.markdown(md_text, extensions=["tables", "fenced_code", "nl2br"])
    except Exception:
        return f"<pre>{md_text}</pre>"


def _topic_card(ts: dict) -> str:
    topic_id = ts["topic_id"]
    color = TOPIC_COLORS.get(topic_id, "#34495e")
    icon = TOPIC_ICONS.get(topic_id, "📄")
    is_adhoc = ts.get("is_adhoc", False)
    adhoc_badge = '<span class="adhoc-badge">Ad-hoc</span>' if is_adhoc else ""
    summary_html = _render_markdown(ts["summary"])

    return f"""
    <div class="topic-card" id="{topic_id}">
        <div class="topic-header" style="border-left: 5px solid {color}; background: linear-gradient(135deg, {color}15, transparent);">
            <div class="topic-title">
                <span class="topic-icon">{icon}</span>
                <h2>{ts['topic_name']}</h2>
                {adhoc_badge}
            </div>
            <div class="topic-meta">
                <span class="article-count">📚 {ts.get('article_count', 0)} artículos analizados</span>
                <button class="toggle-btn" onclick="toggleCard('{topic_id}')">▼ Ver resumen</button>
            </div>
        </div>
        <div class="topic-body collapsed" id="body-{topic_id}">
            <div class="summary-content">
                {summary_html}
            </div>
        </div>
    </div>
    """


def build_dashboard(
    content: dict,
    output_dir: str = "docs",
    podcast_filename: str | None = None,
    podcast_filename_part2: str | None = None,
    podcast_script_filename: str | None = None,
) -> None:

    month_year = content.get("month_year", datetime.today().strftime("%B %Y"))
    generated_at = content.get("generated_at", datetime.today().isoformat())
    topic_summaries = content.get("topic_summaries", [])

    nav_items = ""
    for ts in topic_summaries:
        topic_id = ts["topic_id"]
        icon = TOPIC_ICONS.get(topic_id, "📄")
        is_adhoc = ts.get("is_adhoc", False)
        adhoc_mark = " ✦" if is_adhoc else ""
        nav_items += f'<li><a href="#{topic_id}">{icon} {ts["topic_name"]}{adhoc_mark}</a></li>\n'

    cards_html = ""
    for ts in topic_summaries:
        cards_html += _topic_card(ts)

    # Podcast section
    podcast_section = ""
    if podcast_filename:
        part2_player = ""
        if podcast_filename_part2:
            part2_player = f"""
            <div style="margin-top:15px;">
                <div style="font-size:0.85rem; color:#7f8c8d; margin-bottom:8px;">Parte 2</div>
                <audio controls class="podcast-player">
                    <source src="{podcast_filename_part2}" type="audio/mpeg">
                </audio>
                <div style="margin-top:8px;">
                    <a href="{podcast_filename_part2}" download class="download-btn">⬇️ Descargar Parte 2</a>
                </div>
            </div>
            """

        podcast_section = f"""
        <div class="podcast-section" id="podcast">
            <div class="podcast-header">
                <span class="podcast-icon">🎙️</span>
                <div>
                    <h2>Podcast del Mes</h2>
                    <p>Resumen en audio de las novedades — {month_year}</p>
                </div>
            </div>
            <div style="font-size:0.85rem; color:#7f8c8d; margin-bottom:8px;">Parte 1</div>
            <audio controls class="podcast-player">
                <source src="{podcast_filename}" type="audio/mpeg">
                Tu navegador no soporta el reproductor de audio.
            </audio>
            <div class="podcast-download">
                <a href="{podcast_filename}" download class="download-btn">⬇️ Descargar Parte 1</a>
                {f'<a href="{podcast_script_filename}" class="download-btn secondary">📄 Ver guion</a>' if podcast_script_filename else ''}
            </div>
            {part2_player}
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Radiología Torácica — Actualización {month_year}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f6fa;
            color: #2c3e50;
            line-height: 1.6;
        }}
        .layout {{ display: flex; min-height: 100vh; }}

        .sidebar {{
            width: 280px;
            background: #1a2332;
            color: #ecf0f1;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
            padding: 20px 0;
            z-index: 100;
        }}
        .sidebar-logo {{ padding: 0 20px 20px; border-bottom: 1px solid #2c3e50; margin-bottom: 15px; }}
        .sidebar-logo h1 {{ font-size: 1rem; font-weight: 700; color: #3498db; line-height: 1.3; }}
        .sidebar-logo .subtitle {{ font-size: 0.75rem; color: #7f8c8d; margin-top: 4px; }}
        .sidebar nav ul {{ list-style: none; padding: 0 10px; }}
        .sidebar nav ul li a {{
            display: block; padding: 8px 12px; color: #bdc3c7;
            text-decoration: none; font-size: 0.82rem; border-radius: 6px;
            transition: all 0.2s; margin-bottom: 2px;
        }}
        .sidebar nav ul li a:hover {{ background: #2c3e50; color: #ecf0f1; padding-left: 18px; }}
        .sidebar-footer {{ padding: 15px 20px; border-top: 1px solid #2c3e50; margin-top: 15px; font-size: 0.7rem; color: #7f8c8d; }}

        .main {{ margin-left: 280px; flex: 1; padding: 0; }}

        .page-header {{
            background: linear-gradient(135deg, #1a2332, #2c3e50);
            color: white; padding: 40px; position: relative; overflow: hidden;
        }}
        .page-header h1 {{ font-size: 1.8rem; font-weight: 800; margin-bottom: 8px; }}
        .page-header .meta {{ font-size: 0.85rem; color: #7f8c8d; }}
        .header-stats {{ display: flex; gap: 20px; margin-top: 20px; flex-wrap: wrap; }}
        .stat-box {{ background: rgba(255,255,255,0.08); border-radius: 8px; padding: 12px 20px; text-align: center; }}
        .stat-box .value {{ font-size: 1.5rem; font-weight: 700; color: #3498db; }}
        .stat-box .label {{ font-size: 0.7rem; color: #95a5a6; text-transform: uppercase; letter-spacing: 0.5px; }}

        .content {{ padding: 30px 40px; max-width: 1100px; }}

        .podcast-section {{
            background: linear-gradient(135deg, #1a2332, #2c4a6e);
            border-radius: 12px; padding: 25px 30px; margin-bottom: 30px; color: white;
        }}
        .podcast-header {{ display: flex; align-items: center; gap: 15px; margin-bottom: 20px; }}
        .podcast-icon {{ font-size: 2.5rem; }}
        .podcast-header h2 {{ font-size: 1.3rem; margin-bottom: 4px; }}
        .podcast-header p {{ color: #7f8c8d; font-size: 0.85rem; }}
        .podcast-player {{ width: 100%; margin-bottom: 15px; border-radius: 8px; }}
        .podcast-download {{ display: flex; gap: 10px; flex-wrap: wrap; }}
        .download-btn {{
            background: #3498db; color: white; padding: 8px 16px;
            border-radius: 6px; text-decoration: none; font-size: 0.85rem; transition: background 0.2s;
        }}
        .download-btn:hover {{ background: #2980b9; }}
        .download-btn.secondary {{ background: #2c3e50; }}

        .topic-card {{
            background: white; border-radius: 12px; margin-bottom: 16px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.06); overflow: visible;
        }}
        .topic-header {{
            padding: 18px 24px; display: flex; justify-content: space-between;
            align-items: center; cursor: pointer;
        }}
        .topic-title {{ display: flex; align-items: center; gap: 12px; }}
        .topic-icon {{ font-size: 1.5rem; }}
        .topic-header h2 {{ font-size: 1rem; font-weight: 600; color: #2c3e50; }}
        .adhoc-badge {{
            background: #f39c12; color: white; font-size: 0.65rem;
            padding: 2px 8px; border-radius: 10px; font-weight: 700; text-transform: uppercase;
        }}
        .topic-meta {{ display: flex; align-items: center; gap: 12px; }}
        .article-count {{ font-size: 0.75rem; color: #7f8c8d; }}
        .toggle-btn {{
            background: #ecf0f1; border: none; padding: 6px 14px; border-radius: 6px;
            cursor: pointer; font-size: 0.8rem; color: #2c3e50; transition: background 0.2s; white-space: nowrap;
        }}
        .toggle-btn:hover {{ background: #d5d8dc; }}

        .topic-body {{
            padding: 0 24px;
            overflow: visible;
            max-height: none;
            display: none;
        }}
        .topic-body.expanded {{
            display: block;
            padding-top: 0;
            padding-bottom: 20px;
        }}

        .summary-content {{ padding: 20px 0; border-top: 1px solid #ecf0f1; }}
        .summary-content h2 {{ font-size: 1.1rem; color: #2c3e50; margin: 20px 0 10px; padding-bottom: 6px; border-bottom: 2px solid #ecf0f1; }}
        .summary-content h3 {{ font-size: 0.95rem; color: #34495e; margin: 15px 0 8px; }}
        .summary-content p {{ margin-bottom: 10px; font-size: 0.9rem; color: #445; }}
        .summary-content ul {{ padding-left: 20px; margin-bottom: 10px; }}
        .summary-content ul li {{ font-size: 0.9rem; color: #445; margin-bottom: 4px; }}
        .summary-content a {{ color: #3498db; text-decoration: none; }}
        .summary-content a:hover {{ text-decoration: underline; }}
        .summary-content strong {{ color: #2c3e50; }}

        .section-title {{
            font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: 1px; color: #95a5a6; margin: 30px 0 15px;
        }}

        @media (max-width: 768px) {{
            .sidebar {{ display: none; }}
            .main {{ margin-left: 0; }}
            .content {{ padding: 20px; }}
            .page-header {{ padding: 25px 20px; }}
        }}
    </style>
</head>
<body>
<div class="layout">
    <aside class="sidebar">
        <div class="sidebar-logo">
            <h1>🫁 Radiología Torácica</h1>
            <div class="subtitle">Actualización Científica Mensual</div>
        </div>
        <nav>
            <ul>
                <li><a href="#podcast">🎙️ Podcast del Mes</a></li>
                {nav_items}
            </ul>
        </nav>
        <div class="sidebar-footer">
            Generado: {generated_at[:10]}<br>
            Powered by PubMed · Semantic Scholar · Claude AI
        </div>
    </aside>

    <main class="main">
        <div class="page-header">
            <h1>Radiología Torácica — {month_year}</h1>
            <div class="meta">Actualización científica mensual automatizada</div>
            <div class="header-stats">
                <div class="stat-box">
                    <div class="value">{len(topic_summaries)}</div>
                    <div class="label">Temas</div>
                </div>
                <div class="stat-box">
                    <div class="value">{sum(ts.get('article_count', 0) for ts in topic_summaries)}</div>
                    <div class="label">Artículos analizados</div>
                </div>
                <div class="stat-box">
                    <div class="value">14</div>
                    <div class="label">Revistas monitorizadas</div>
                </div>
            </div>
        </div>

        <div class="content">
            {podcast_section}
            <div class="section-title">Resúmenes por Tema</div>
            {cards_html}
        </div>
    </main>
</div>

<script>
    function toggleCard(topicId) {{
        const body = document.getElementById('body-' + topicId);
        const btn = body.previousElementSibling.querySelector('.toggle-btn');
        body.classList.toggle('expanded');
        btn.textContent = body.classList.contains('expanded') ? '▲ Cerrar' : '▼ Ver resumen';
    }}

    document.querySelectorAll('.sidebar a[href^="#"]').forEach(a => {{
        a.addEventListener('click', e => {{
            e.preventDefault();
            const target = document.querySelector(a.getAttribute('href'));
            if (target) {{
                target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                const topicId = a.getAttribute('href').replace('#', '');
                const body = document.getElementById('body-' + topicId);
                if (body && !body.classList.contains('expanded')) {{
                    toggleCard(topicId);
                }}
            }}
        }});
    }});
</script>
</body>
</html>"""

    output_path = Path(output_dir) / "index.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info(f"Dashboard written to {output_path}")

    if content.get("podcast_script"):
        script_path = Path(output_dir) / "podcast_script.txt"
        script_path.write_text(content["podcast_script"], encoding="utf-8")
        logger.info(f"Podcast script written to {script_path}")
