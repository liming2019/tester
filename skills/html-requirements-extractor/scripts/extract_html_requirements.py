#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 HTML 原型提取统一 requirements.json。"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen


TEXT_TAGS = {"script", "style", "svg"}
BLOCK_TAGS = {"p", "li", "tr", "td", "th", "div", "section", "article", "br", "h1", "h2", "h3", "h4"}


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def normalize_version(value: str) -> str:
    text = normalize_space(value).upper()
    if text and not text.startswith("V"):
        text = f"V{text}"
    return text


def split_notes(text: str) -> list[str]:
    text = normalize_space(text)
    if not text:
        return []
    marker = "␟"
    protected = re.sub(r"(?<!\d)[。；;](?!\d)", marker, text)
    items = [normalize_space(part) for part in protected.split(marker)]
    return [item for item in items if item]


def stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(parts).encode("utf-8", errors="ignore")
    return f"{prefix}-{hashlib.sha1(raw).hexdigest()[:10]}"


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    parent: "Node | None" = None
    children: list["Node | str"] = field(default_factory=list)

    def append(self, child: "Node | str") -> None:
        self.children.append(child)

    def attr(self, name: str, default: str = "") -> str:
        return self.attrs.get(name, default)

    def has_class(self, class_name: str) -> bool:
        return class_name in self.attr("class").split()

    def text(self, include_hidden: bool = True) -> str:
        chunks: list[str] = []

        def walk(node: "Node | str", skip_depth: int = 0) -> None:
            if isinstance(node, str):
                if skip_depth == 0:
                    chunks.append(node)
                return
            next_skip = skip_depth
            if node.tag in TEXT_TAGS:
                next_skip += 1
            if node.tag in BLOCK_TAGS:
                chunks.append(" ")
            if not include_hidden and is_hidden(node):
                next_skip += 1
            for child in node.children:
                walk(child, next_skip)
            if node.tag in BLOCK_TAGS:
                chunks.append(" ")

        walk(self)
        return normalize_space("".join(chunks))

    def find_all(self, predicate) -> list["Node"]:
        result: list[Node] = []

        def walk(node: Node) -> None:
            if predicate(node):
                result.append(node)
            for child in node.children:
                if isinstance(child, Node):
                    walk(child)

        walk(self)
        return result

    def direct_children(self, tag: str | None = None) -> list["Node"]:
        nodes = [child for child in self.children if isinstance(child, Node)]
        if tag:
            return [node for node in nodes if node.tag == tag]
        return nodes


class TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.root = Node("document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag.lower(), {k.lower(): v or "" for k, v in attrs}, self.stack[-1])
        self.stack[-1].append(node)
        if tag.lower() not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1].append(data)

    def handle_entityref(self, name: str) -> None:
        self.stack[-1].append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.stack[-1].append(f"&#{name};")


def is_hidden(node: Node) -> bool:
    if "hidden" in node.attrs:
        return True
    style = node.attr("style").replace(" ", "").lower()
    if "display:none" in style or "visibility:hidden" in style:
        return True
    classes = set(node.attr("class").split())
    return "hidden" in classes or "is-hidden" in classes


def has_class(node: Node, keyword: str) -> bool:
    return any(keyword in part for part in node.attr("class").split())


def nearest_section(node: Node) -> dict[str, str]:
    cur = node.parent
    while cur:
        if cur.tag in {"section", "article", "main", "aside"}:
            heading = ""
            headings = cur.find_all(lambda n: n.tag in {"h1", "h2", "h3"})
            if headings:
                heading = headings[0].text()
            return {
                "id": cur.attr("id"),
                "class": cur.attr("class"),
                "title": heading,
                "hidden": str(is_hidden(cur)).lower(),
            }
        cur = cur.parent
    return {"id": "", "class": "", "title": "", "hidden": "false"}


def parse_tree(source: str) -> Node:
    parser = TreeParser()
    parser.feed(source)
    return parser.root


def read_source(args: argparse.Namespace) -> tuple[str, str]:
    if args.file:
        path = Path(args.file)
        return path.read_text(encoding="utf-8"), str(path.resolve())
    return read_url(args.url, args.timeout)


def read_url(url: str, timeout: int) -> tuple[str, str]:
    request = Request(url, headers={"User-Agent": "Codex HTML requirements extractor"})
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace"), url


def extract_title(root: Node) -> str:
    titles = root.find_all(lambda n: n.tag == "title")
    if titles:
        return titles[0].text()
    headings = root.find_all(lambda n: n.tag == "h1")
    return headings[0].text() if headings else ""


def extract_description_items(cell: Node) -> list[str]:
    list_items = [item.text() for item in cell.find_all(lambda n: n.tag == "li")]
    list_items = [item for item in list_items if item]
    if list_items:
        return list_items
    return split_notes(cell.text())


def requirement_key(content: str) -> str:
    text = normalize_space(content)
    replacements = {
        "广告账户数据-": "",
        "小红书乘风-": "小红书",
        "商品推广明细页": "商品推广明细",
        "直播推广明细页": "直播推广明细",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"[\s\-_/：:，,。；;（）()]+", "", text)


def extract_rows(root: Node, target_version: str, media: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    target = normalize_version(target_version)
    tables = root.find_all(lambda n: n.tag == "table")

    for table in tables:
        tr_nodes = table.find_all(lambda n: n.tag == "tr")
        if not tr_nodes:
            continue
        header_cells = tr_nodes[0].find_all(lambda n: n.tag in {"th", "td"})
        headers = [cell.text() for cell in header_cells]
        if not {"版本", "版本内容", "说明"}.issubset(set(headers)):
            continue

        section = nearest_section(table)
        for tr in tr_nodes[1:]:
            cells = tr.find_all(lambda n: n.tag == "td")
            if len(cells) < 3:
                continue
            version = cells[0].text()
            content = cells[1].text()
            description = cells[2].text()
            if not version or not content or not description:
                continue
            normalized = normalize_version(version)
            version_match = "exact" if normalized == target else "excluded"
            if "+" in normalized and target in normalized:
                version_match = "mixed"
            included = version_match in {"exact", "mixed"}
            row_media = tr.attr("data-page-requirements-media") or tr.attr("data-flow-media") or tr.attr("data-media")
            if media and row_media and row_media != media:
                included = False
            if not included:
                continue
            rows.append(
                {
                    "版本": normalize_space(version),
                    "版本内容": normalize_space(content),
                    "说明": extract_description_items(cells[2]),
                    "version_match": version_match,
                    "included_in_target_version": True,
                    "source_section": section,
                    "source_media": row_media,
                }
            )

    by_content: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = requirement_key(row["版本内容"])
        current = by_content.get(key)
        if current is None:
            by_content[key] = row
            continue
        current_len = len("".join(current.get("说明", [])))
        next_len = len("".join(row.get("说明", [])))
        if next_len > current_len:
            row["duplicate_sources"] = current.get("duplicate_sources", []) + [current.get("source_section", {})]
            by_content[key] = row
        else:
            current.setdefault("duplicate_sources", []).append(row.get("source_section", {}))

    return list(by_content.values())


def extract_buttons(root: Node) -> list[dict[str, str]]:
    buttons = []
    for button in root.find_all(lambda n: n.tag in {"button", "a"}):
        text = button.text()
        if not text:
            continue
        buttons.append(
            {
                "text": text,
                "tag": button.tag,
                "id": button.attr("id"),
                "class": button.attr("class"),
                "data_media": button.attr("data-media"),
                "data_tab": button.attr("data-tab"),
                "href": button.attr("href"),
            }
        )
    return buttons


def extract_components(root: Node) -> dict[str, Any]:
    buttons = extract_buttons(root)
    media_tabs = [b["text"] for b in buttons if b.get("data_media")]
    function_tabs = [b["text"] for b in buttons if b.get("data_tab")]

    labels = []
    for label in root.find_all(lambda n: n.tag == "label"):
        text = label.text()
        if text:
            labels.append(text)
    for node in root.find_all(lambda n: n.attr("aria-label")):
        value = node.attr("aria-label")
        if value and value not in labels:
            labels.append(value)

    nav = []
    for link in root.find_all(lambda n: n.tag == "a" and has_class(n, "side-nav-link")):
        text = link.text()
        if text:
            nav.append({"text": text, "href": link.attr("href")})

    table_headers = []
    for table in root.find_all(lambda n: n.tag == "table"):
        first = table.find_all(lambda n: n.tag == "tr")
        if not first:
            continue
        headers = [cell.text() for cell in first[0].find_all(lambda n: n.tag in {"th", "td"}) if cell.text()]
        if headers:
            table_headers.append(headers)

    return {
        "media_tabs": media_tabs,
        "function_tabs": function_tabs,
        "filters_and_labels": sorted(set(labels)),
        "buttons": buttons,
        "side_navigation": nav,
        "table_headers": table_headers,
    }


def extract_text_notes(root: Node) -> list[dict[str, str]]:
    notes = []
    selectors = [
        lambda n: has_class(n, "requirements-intro"),
        lambda n: has_class(n, "flow-note"),
        lambda n: "note" in n.attr("class").lower(),
        lambda n: "notice" in n.attr("class").lower(),
    ]
    for node in root.find_all(lambda n: any(selector(n) for selector in selectors)):
        text = node.text()
        if not text:
            continue
        section = nearest_section(node)
        notes.append(
            {
                "位置": section.get("title") or section.get("id") or node.attr("class"),
                "关联字段": "",
                "文案": text,
            }
        )
    dedup = {}
    for note in notes:
        dedup[note["文案"]] = note
    return list(dedup.values())


def extract_fields(node: Node) -> list[dict[str, str]]:
    fields = []
    for label in node.find_all(lambda n: n.tag == "label"):
        text = label.text()
        if text:
            fields.append({"name": text, "type": "label", "required": "", "default": "", "options": "", "description": ""})
    for control in node.find_all(lambda n: n.tag in {"input", "select", "textarea"}):
        name = control.attr("placeholder") or control.attr("name") or control.attr("id") or control.attr("aria-label")
        if name:
            fields.append({"name": name, "type": control.tag, "required": str("required" in control.attrs).lower(), "default": control.attr("value"), "options": "", "description": ""})
    dedup = {}
    for field_item in fields:
        dedup[field_item["name"]] = field_item
    return list(dedup.values())


def extract_interactions(root: Node) -> tuple[list[dict[str, Any]], list[str]]:
    interactions = []
    candidates = root.find_all(
        lambda n: n.tag in {"div", "section", "aside"}
        and (
            has_class(n, "modal")
            or has_class(n, "drawer")
            or has_class(n, "popover")
            or "dialog" in n.attr("role").lower()
        )
    )
    for node in candidates:
        text = node.text()
        if not text:
            continue
        title_nodes = node.find_all(lambda n: n.tag in {"h1", "h2", "h3", "strong"} or has_class(n, "modal-title") or has_class(n, "drawer-title"))
        title = title_nodes[0].text() if title_nodes else text[:40]
        actions = [b["text"] for b in extract_buttons(node)]
        result_type = "drawer" if has_class(node, "drawer") else "modal" if has_class(node, "modal") else "popover"
        interactions.append(
            {
                "trigger": title,
                "trigger_type": "static_container",
                "interaction": "click",
                "result_type": result_type,
                "title": title,
                "fields": extract_fields(node),
                "actions": actions,
                "notes": split_notes(text),
                "screenshot": "",
            }
        )

    trigger_words = ("新增", "编辑", "删除", "详情", "导出", "字段设置", "绑定", "查看", "Tab")
    visible_triggers = [b["text"] for b in extract_buttons(root) if any(word in b["text"] for word in trigger_words)]
    warnings = []
    if visible_triggers and not interactions:
        warnings.append("页面存在明显交互入口，但未提取到弹窗、抽屉或隐藏交互态；建议使用浏览器自动化补抓。")
    return interactions, warnings


def target_version_base_url(source_ref: str, target_version: str) -> str:
    parsed = urlparse(source_ref)
    target = normalize_version(target_version)
    replaced_path = re.sub(r"/V\d+(?:\.\d+)*/", f"/{target}/", parsed.path, count=1)
    return urlunparse(parsed._replace(path=replaced_path, params="", query="", fragment=""))


def crawl_candidates(source_ref: str, href: str, target_version: str) -> list[str]:
    href = html.unescape(href or "")
    if not href or href.startswith("javascript:"):
        return []
    version_base = target_version_base_url(source_ref, target_version)
    candidates = [urljoin(version_base, href), urljoin(source_ref, href)]
    deduped: list[str] = []
    seen = set()
    for item in candidates:
        clean = item
        if clean not in seen:
            seen.add(clean)
            deduped.append(clean)
    return deduped


def discover_link_targets(root: Node, source_ref: str, args: argparse.Namespace) -> list[dict[str, str]]:
    if args.file or args.no_crawl_links:
        return []
    target = normalize_version(args.version)
    targets = []
    seen_urls = set()
    for link in root.find_all(lambda n: n.tag == "a" and has_class(n, "side-nav-link")):
        text = link.text()
        href = link.attr("href")
        if target not in normalize_space(text) or not href:
            continue
        if href.startswith("#"):
            continue
        for candidate in crawl_candidates(source_ref, href, args.version):
            try:
                page_html, final_url = read_url(candidate, args.timeout)
            except Exception:
                continue
            key = urlunparse(urlparse(final_url)._replace(fragment=""))
            if key in seen_urls:
                break
            seen_urls.add(key)
            targets.append({"url": final_url, "label": text, "html": page_html})
            break
    return targets


def merge_requirement_rows(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for page in pages:
        for row in page.get("prototype_structured", []):
            candidate = dict(row)
            candidate["source_page"] = {
                "page_name": page.get("page_name", ""),
                "page_url": page.get("page_url", ""),
            }
            key = requirement_key(candidate.get("版本内容", ""))
            current = merged.get(key)
            if current is None:
                merged[key] = candidate
                continue
            current_len = len("".join(current.get("说明", [])))
            next_len = len("".join(candidate.get("说明", [])))
            if next_len > current_len:
                candidate["duplicate_requirements"] = current.get("duplicate_requirements", []) + [
                    {
                        "版本内容": current.get("版本内容", ""),
                        "source_page": current.get("source_page", {}),
                        "说明条数": len(current.get("说明", [])),
                    }
                ]
                merged[key] = candidate
            else:
                current.setdefault("duplicate_requirements", []).append(
                    {
                        "版本内容": candidate.get("版本内容", ""),
                        "source_page": candidate.get("source_page", {}),
                        "说明条数": len(candidate.get("说明", [])),
                    }
                )
    return list(merged.values())


def build_page(source_html: str, source_ref: str, args: argparse.Namespace, page_label: str = "") -> tuple[dict[str, Any], list[str]]:
    root = parse_tree(source_html)
    parsed = urlparse(source_ref)
    query = parse_qs(parsed.query)
    media = args.media or (query.get("media", [""])[0] or "")
    tab = args.tab or (query.get("tab", [""])[0] or "")
    title = extract_title(root)
    rows = extract_rows(root, args.version, media if args.media else None)
    components = extract_components(root)
    text_notes = extract_text_notes(root)
    interactions, warnings = extract_interactions(root)
    raw_text = root.text()

    page = {
        "page_name": page_label or title or Path(parsed.path).name or "HTML 原型",
        "page_url": source_ref,
        "page_group": "HTML 原型",
        "page_module": "需求说明",
        "screenshot": "",
        "prototype_structured": rows,
        "canvas_annotations": [],
        "canvas_text_notes": text_notes,
        "interaction_states": interactions,
        "right_panel_notes": [],
        "raw_prototype_text": raw_text[:20000],
        "page_components": components,
    }
    return page, warnings


def build_output(source_html: str, source_ref: str, args: argparse.Namespace) -> dict[str, Any]:
    root = parse_tree(source_html)
    parsed = urlparse(source_ref)
    query = parse_qs(parsed.query)
    media = args.media or (query.get("media", [""])[0] or "")
    tab = args.tab or (query.get("tab", [""])[0] or "")
    title = extract_title(root)

    source_pages: list[dict[str, str]] = []
    canonical = target_version_base_url(source_ref, args.version)
    if canonical and canonical != source_ref:
        try:
            canonical_html, canonical_url = read_url(canonical, args.timeout)
            source_pages.append({"url": canonical_url, "label": f"{normalize_version(args.version)} 入口页", "html": canonical_html})
            root = parse_tree(canonical_html)
            title = extract_title(root) or title
        except Exception:
            pass
    source_pages.append({"url": source_ref, "label": title or "入口页", "html": source_html})
    source_pages.extend(discover_link_targets(root, source_ref, args))

    pages: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen_pages = set()
    for source_page in source_pages:
        key = urlunparse(urlparse(source_page["url"])._replace(fragment=""))
        if key in seen_pages:
            continue
        seen_pages.add(key)
        page, page_warnings = build_page(source_page["html"], source_page["url"], args, source_page.get("label", ""))
        pages.append(page)
        warnings.extend(page_warnings)

    merged_requirements = merge_requirement_rows(pages)
    return {
        "source": {
            "platform": "html-prototype",
            "version": normalize_version(args.version),
            "title": title,
            "url": source_ref,
            "path": unquote(parsed.path) if parsed.scheme else str(Path(source_ref)),
            "media": media,
            "tab": tab,
            "hash": parsed.fragment,
            "crawled_page_count": len(pages),
        },
        "pages": pages,
        "requirements_index": merged_requirements,
        "quality_warnings": sorted(set(warnings)),
        "statistics": {
            "requirement_count": len(merged_requirements),
            "page_count": len(pages),
            "text_note_count": sum(len(page.get("canvas_text_notes", [])) for page in pages),
            "interaction_state_count": sum(len(page.get("interaction_states", [])) for page in pages),
            "button_count": sum(len(page.get("page_components", {}).get("buttons", [])) for page in pages),
        },
    }


def write_summary(data: dict[str, Any], output: Path) -> None:
    source = data["source"]
    requirements = data.get("requirements_index") or data["pages"][0].get("prototype_structured", [])
    lines = [
        f"# {source.get('version')} HTML 原型需求提取摘要",
        "",
        f"- 来源：{source.get('title')}",
        f"- 地址：{source.get('url')}",
        f"- 媒体：{source.get('media') or '未限定'}",
        f"- Tab：{source.get('tab') or '未限定'}",
        f"- 抓取页面数：{source.get('crawled_page_count', 1)}",
        f"- 需求条数：{len(requirements)}",
        "",
        "## 需求明细",
        "",
    ]
    for index, item in enumerate(requirements, start=1):
        lines.append(f"### {index}. {item.get('版本内容')}")
        lines.append("")
        source_page = item.get("source_page") or {}
        if source_page.get("page_url"):
            lines.append(f"- 来源页面：{source_page.get('page_name')} {source_page.get('page_url')}")
        for note in item.get("说明", []):
            lines.append(f"- {note}")
        lines.append("")
    warnings = data.get("quality_warnings") or []
    if warnings:
        lines.extend(["## 质量提示", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从 HTML 原型提取 requirements.json")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="HTML 原型 URL")
    source.add_argument("--file", help="本地 HTML 文件")
    parser.add_argument("--version", required=True, help="目标版本，例如 V1.6.1")
    parser.add_argument("--media", help="目标媒体平台")
    parser.add_argument("--tab", help="目标 Tab")
    parser.add_argument("--output", required=True, help="输出 requirements.json")
    parser.add_argument("--summary-md", help="输出 Markdown 摘要")
    parser.add_argument("--raw-html", help="保存原始 HTML")
    parser.add_argument("--no-crawl-links", action="store_true", help="只提取当前 HTML，不抓取左侧同版本链接页")
    parser.add_argument("--timeout", type=int, default=20, help="URL 读取超时时间，单位秒")
    args = parser.parse_args(argv)

    try:
        source_html, source_ref = read_source(args)
        data = build_output(source_html, source_ref, args)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.summary_md:
            summary = Path(args.summary_md)
            summary.parent.mkdir(parents=True, exist_ok=True)
            write_summary(data, summary)
        if args.raw_html:
            raw = Path(args.raw_html)
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_text(source_html, encoding="utf-8")
    except Exception as exc:
        print(f"提取失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
