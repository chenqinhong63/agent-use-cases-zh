#!/usr/bin/env python3
"""每日更新：从 agentusecases.ai 同步新增案例到 data/cases.json。

逻辑：
  1. 读本地 data/cases.json 的 slug 集合；
  2. 下载 https://agentusecases.ai/sitemap.xml，取全部 /use-case/ slug；
  3. 新增 = sitemap 有、本地没有的；逐个抓详情页解析；
  4. 有 DASHSCOPE_API_KEY 时用 DashScope OpenAI 兼容接口翻译成中文
     （模型 deepseek-v4-pro-0813，失败回退 qwen-plus）；
     无 Key 时 title_zh/summary_zh 留英文原文，translated=false，prompt_zh 留空；
  5. 新条目追加到末尾写回 data/cases.json。

只用 Python 标准库。详情页请求间隔 0.5 秒，单个失败跳过不中断全程。
用法：python scripts/update.py [--dry-run]
"""

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA_PATH = BASE / "data" / "cases.json"
SITEMAP_URL = "https://agentusecases.ai/sitemap.xml"
DETAIL_URL = "https://agentusecases.ai/use-case/{slug}"
USER_AGENT = "Mozilla/5.0 (compatible; agent-use-cases-zh updater)"
REQUEST_INTERVAL = 0.5

# 详情页 Topic 文本 -> 中文分类（11 类，与现有数据一致）
TOPIC_MAP = {
    "Software & DevOps": "软件与运维",
    "Work & Operations": "运营与效率",
    "Life Admin & Home": "生活与家庭",
    "Sales, Marketing & Support": "增长与营销",
    "Money, Bills & Benefits": "金钱账单与权益",
    "Research & Knowledge": "研究与分析",
    "Shopping & Errands": "购物与比价",
    "Content & Creative": "创意与内容",
    "Travel & Bookings": "出行与旅行",
    "Games & Simulations": "游戏",
    "Security, Science & Hardware": "科学",
}

DASHSCOPE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
MODELS = ["deepseek-v4-pro-0813", "qwen-plus"]


def fetch_text(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse_sitemap(xml_text):
    """返回 sitemap 里全部 /use-case/ slug（去重、保序）。"""
    root = ET.fromstring(xml_text)
    slugs, seen = [], set()
    for el in root.iter():
        if el.tag.endswith("loc") and el.text and "/use-case/" in el.text:
            slug = el.text.strip().rstrip("/").split("/use-case/")[-1]
            if slug and slug not in seen:
                seen.add(slug)
                slugs.append(slug)
    return slugs


def text_lines(html_text):
    """去掉 script/style，把标签换成换行，得到非空文本行列表。"""
    t = re.sub(r"<script.*?</script>", " ", html_text, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = html.unescape(t)
    return [line.strip() for line in t.splitlines() if line.strip()]


def parse_detail(html_text, slug):
    """解析详情页。返回 dict 或 None（结构对不上时返回 None）。

    实测结构（2026-11-21）：
      … "All" / "2,263" / "use cases" / <Topic> / <标题> / <简介> /
      "·" / <日期> / "Done with" / <缩写> / <Agent名> … / "What they did" /
      … / "Try it yourself" / "with" / <Agent名> / "Copy prompt" / <提示词原文> /
      … / "Source: xxx ·" / …
    """
    lines = text_lines(html_text)
    topic_idx = next((i for i, l in enumerate(lines) if l in TOPIC_MAP), None)
    if topic_idx is None or topic_idx + 2 >= len(lines):
        return None
    title_en = lines[topic_idx + 1]
    summary_en = lines[topic_idx + 2]
    if summary_en == "·" and topic_idx + 3 < len(lines):
        summary_en = lines[topic_idx + 3]
    if not title_en or not summary_en:
        return None

    # Agent： "Done with" 后的成对行（缩写 / 全名），取每对的第二行
    agents = []
    done_idx = next(
        (i for i, l in enumerate(lines) if l == "Done with" or l.startswith("Done with ")),
        None,
    )
    if done_idx is not None:
        done_line = lines[done_idx]
        if done_line.startswith("Done with a"):
            agents = ["Custom agent"]
        else:
            end = next(
                (i for i in range(done_idx + 1, len(lines)) if lines[i] == "What they did"),
                len(lines),
            )
            seg = lines[done_idx + 1 : end]
            agents = [seg[i] for i in range(1, len(seg), 2) if seg[i]]
            if not agents:  # 兜底：取长度 > 3 的行
                agents = [s for s in seg if len(s) > 3]

    # 提示词原文："Copy prompt" 的下一行
    prompt_en = ""
    cp_idx = next((i for i, l in enumerate(lines) if l == "Copy prompt"), None)
    if cp_idx is not None and cp_idx + 1 < len(lines):
        prompt_en = lines[cp_idx + 1]

    # 来源数："N / more / accounts / of this"
    accounts = None
    for i, l in enumerate(lines):
        if l == "more" and i + 1 < len(lines) and lines[i + 1] == "accounts":
            if i > 0 and lines[i - 1].isdigit():
                accounts = int(lines[i - 1])
            break

    # 来源与日期
    source = ""
    for l in lines:
        if l.startswith("Source:"):
            source = l[len("Source:"):].split("·")[0].strip()
            break
    date = ""
    for l in lines:
        if re.match(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2}, \d{4}$", l):
            date = l
            break

    return {
        "slug": slug,
        "title_en": title_en,
        "summary_en": summary_en,
        "prompt_en": prompt_en,
        "category_zh": TOPIC_MAP[lines[topic_idx]],
        "agents": agents,
        "accounts": accounts,
        "source": source,
        "date": date,
        "url": DETAIL_URL.format(slug=slug),
    }


def dashscope_chat(api_key, model, messages):
    """调一次 DashScope OpenAI 兼容接口，返回 message content；失败抛异常。"""
    body = json.dumps(
        {"model": model, "messages": messages, "temperature": 0.3}
    ).encode("utf-8")
    req = urllib.request.Request(
        DASHSCOPE_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def translate(api_key, title_en, summary_en, prompt_en):
    """翻译标题/简介，并按简介写一条带 [ ] 占位符的中文提示词模板。

    返回 (title_zh, summary_zh, prompt_zh)，任一模型失败返回 None。
    """
    user_text = (
        "把下面这条 AI Agent 用例翻译成自然简洁的中文，并写一条可直接复制的中文提示词模板。\n"
        "要求：只返回 JSON，不要其他文字，字段为 title_zh、summary_zh、prompt_zh；"
        "保留产品/工具英文名和关键数字，不夸大结果；prompt_zh 为 1-3 句，带 [ ] 占位符，"
        "如 [你的需求]；不要声称它是原站提示词。\n"
        f"标题：{title_en}\n简介：{summary_en}\n"
        f"英文提示词（仅供参考）：{prompt_en or '（无）'}"
    )
    for model in MODELS:
        try:
            content = dashscope_chat(
                api_key, model, [{"role": "user", "content": user_text}]
            )
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.S)
            obj = json.loads(content)
            if obj.get("title_zh") and obj.get("summary_zh") and obj.get("prompt_zh"):
                return obj["title_zh"], obj["summary_zh"], obj["prompt_zh"]
            print(f"  翻译返回缺字段（模型 {model}），尝试下一个模型", flush=True)
        except Exception as e:  # noqa: BLE001 - 翻译失败即回退/降级，不中断更新
            print(f"  翻译失败（模型 {model}）：{e}", flush=True)
    return None


def main():
    ap = argparse.ArgumentParser(description="同步 agentusecases.ai 新增案例")
    ap.add_argument("--dry-run", action="store_true", help="只打印将新增的 slug，不写文件、不调翻译接口")
    args = ap.parse_args()

    cases = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    existing = {c["slug"] for c in cases}
    print(f"本地已有 {len(cases)} 条")

    sitemap_slugs = parse_sitemap(fetch_text(SITEMAP_URL))
    print(f"sitemap 共 {len(sitemap_slugs)} 条")
    new_slugs = [s for s in sitemap_slugs if s not in existing]
    print(f"新增 {len(new_slugs)} 条")
    if args.dry_run:
        for s in new_slugs:
            print(f"  + {s}")
        return 0
    if not new_slugs:
        return 0

    api_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if api_key:
        print("翻译：使用 DASHSCOPE_API_KEY")
    else:
        print("翻译：未设置 DASHSCOPE_API_KEY，新增条目标记为待翻译（translated=false）")

    added, translated_ok, pending = 0, 0, 0
    for slug in new_slugs:
        time.sleep(REQUEST_INTERVAL)
        try:
            parsed = parse_detail(fetch_text(DETAIL_URL.format(slug=slug)), slug)
        except Exception as e:  # noqa: BLE001 - 单条失败跳过
            print(f"  跳过 {slug}：抓取失败 {e}", flush=True)
            continue
        if not parsed:
            print(f"  跳过 {slug}：详情页结构解析失败", flush=True)
            continue

        entry = {
            "slug": slug,
            "title_zh": parsed["title_en"],
            "summary_zh": parsed["summary_en"],
            "prompt_zh": "",
            "category_zh": parsed["category_zh"],
            "agents": parsed["agents"],
            "accounts": parsed["accounts"],
            "url": parsed["url"],
            "translated": False,
            "prompt_en": parsed["prompt_en"],
        }
        if parsed.get("source"):
            entry["source"] = parsed["source"]
        if parsed.get("date"):
            entry["date"] = parsed["date"]

        if api_key:
            result = translate(api_key, parsed["title_en"], parsed["summary_en"], parsed["prompt_en"])
            if result:
                entry["title_zh"], entry["summary_zh"], entry["prompt_zh"] = result
                entry["translated"] = True
                translated_ok += 1
            else:
                print(f"  {slug}：翻译失败，记为待翻译", flush=True)
                pending += 1
        else:
            pending += 1

        cases.append(entry)
        added += 1
        print(f"  + {slug}（{entry['category_zh']}，{'已翻译' if entry['translated'] else '待翻译'}）", flush=True)

    DATA_PATH.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完成：新增 {added} 条，翻译成功 {translated_ok} 条，待翻译 {pending} 条，总计 {len(cases)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
