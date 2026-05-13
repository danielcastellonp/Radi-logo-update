"""
main.py — Monthly pipeline orchestrator.
Runs the full pipeline: fetch → generate → audio → dashboard.

Usage:
  python scripts/main.py                    # Full run
  python scripts/main.py --no-audio         # Skip TTS (faster for testing)
  python scripts/main.py --topics-only      # Only fetch + summarize, no podcast
  python scripts/main.py --dry-run          # Only fetch articles, no AI calls
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from fetcher import fetch_for_topic, fetch_adhoc_topic
from generator import generate_all
from audio import generate_podcast_audio_openai
from dashboard import build_dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pipeline.log"),
    ],
)
logger = logging.getLogger("main")


def load_config():
    config_dir = Path(__file__).parent.parent / "config"
    with open(config_dir / "topics.yaml") as f:
        topics = yaml.safe_load(f)["topics"]
    with open(config_dir / "journals.yaml") as f:
        journals = yaml.safe_load(f)["journals"]
    adhoc_file = config_dir / "adhoc_topics.yaml"
    adhoc_topics = []
    if adhoc_file.exists():
        data = yaml.safe_load(adhoc_file.read_text())
        adhoc_topics = data.get("adhoc_topics") or []
    return topics, journals, adhoc_topics


def save_cache(data, cache_path):
    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Cache saved: {cache_path}")


def run(args):
    start_time = datetime.now()
    month_str = datetime.today().strftime("%Y-%m")
    output_dir = "docs"
    cache_dir = f".cache/{month_str}"

    logger.info(f"=== Radiología Torácica Update — {month_str} ===")

    topics, journals, adhoc_topics = load_config()
    journal_ta_list = [j["pubmed_ta"] for j in journals]
    journal_issn_set = {j["issn"] for j in journals} | {
        j.get("eissn", "") for j in journals if j.get("eissn")
    }

    logger.info(f"Topics: {len(topics)} + {len(adhoc_topics)} ad-hoc")
    logger.info(f"Journals: {len(journal_ta_list)}")

    # 1. Fetch articles
    articles_cache = f"{cache_dir}/articles.json"
    if not args.no_cache and Path(articles_cache).exists():
        logger.info("Loading articles from cache...")
        all_topic_data = json.loads(Path(articles_cache).read_text())
    else:
        all_topic_data = []
        for topic in topics:
            topic_data = fetch_for_topic(
                topic=topic,
                journal_ta_list=journal_ta_list,
                journal_issn_set=journal_issn_set,
                months_back=1,
            )
            all_topic_data.append(topic_data)
        for adhoc in adhoc_topics:
            if adhoc.get("name") and adhoc.get("query"):
                all_topic_data.append(fetch_adhoc_topic(adhoc))
        save_cache(all_topic_data, articles_cache)

    if args.dry_run:
        total = sum(
            len(td.get("pubmed_articles", [])) + len(td.get("top_cited_articles", []))
            for td in all_topic_data
        )
        logger.info(f"Dry run complete. Total articles found: {total}")
        return

    # 2. Generate summaries + podcast script
    content_cache = f"{cache_dir}/content.json"
    if not args.no_cache and Path(content_cache).exists():
        logger.info("Loading generated content from cache...")
        content = json.loads(Path(content_cache).read_text())
    else:
        content = generate_all(all_topic_data)
        save_cache(content, content_cache)

    if args.topics_only:
        build_dashboard(content, output_dir=output_dir)
        logger.info("Topics-only mode complete.")
        return

    # 3. Generate podcast audio (two parts)
    podcast_filename = None
    podcast_filename_part2 = None

    if not args.no_audio:
        audio_dir = Path(output_dir) / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        podcast_path = str(audio_dir / f"podcast_{month_str}.mp3")

        if os.getenv("OPENAI_API_KEY"):
            success = generate_podcast_audio_openai(
                content["podcast_script"],
                podcast_path,
            )
            if success:
                podcast_filename = f"audio/podcast_{month_str}.mp3"
                part2_path = Path(output_dir) / f"audio/podcast_{month_str}_part2.mp3"
                if part2_path.exists():
                    podcast_filename_part2 = f"audio/podcast_{month_str}_part2.mp3"
                logger.info(f"Podcast audio: {podcast_filename}")
                if podcast_filename_part2:
                    logger.info(f"Podcast part 2: {podcast_filename_part2}")
            else:
                logger.warning("Audio generation failed or skipped.")
        else:
            logger.warning("OPENAI_API_KEY not set. Skipping audio.")
    else:
        logger.info("Skipping audio generation (--no-audio)")

    # 4. Build dashboard
    build_dashboard(
        content=content,
        output_dir=output_dir,
        podcast_filename=podcast_filename,
        podcast_filename_part2=podcast_filename_part2,
        podcast_script_filename="podcast_script.txt",
    )

    elapsed = (datetime.now() - start_time).total_seconds()
    total_articles = sum(
        len(td.get("pubmed_articles", [])) + len(td.get("top_cited_articles", []))
        for td in all_topic_data
    )
    logger.info(f"=== Pipeline complete in {elapsed:.0f}s ===")
    logger.info(f"Articles analyzed: {total_articles}")
    logger.info(f"Dashboard: {output_dir}/index.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monthly radiology update pipeline")
    parser.add_argument("--no-audio", action="store_true", help="Skip TTS audio generation")
    parser.add_argument("--topics-only", action="store_true", help="Only summaries, no podcast")
    parser.add_argument("--dry-run", action="store_true", help="Only fetch articles, no AI")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached results")
    args = parser.parse_args()
    run(args)
