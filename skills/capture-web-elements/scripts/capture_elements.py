#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "Missing dependency: playwright. Install with "
        "`python -m pip install playwright` and `playwright install chromium`.",
        file=sys.stderr,
    )
    raise SystemExit(2)

try:
    import yaml
except ImportError:
    print(
        "Missing dependency: pyyaml. Install with `python -m pip install pyyaml`.",
        file=sys.stderr,
    )
    raise SystemExit(2)


DOM_SNAPSHOT_JS = r"""
(options) => {
  const captureMode = options.captureMode || "business";
  const includeHidden = Boolean(options.includeHidden);
  const includeDomPath = Boolean(options.includeDomPath);
  const scopeSelector = options.scopeSelector || null;
  const maxElements = Number(options.maxElements || 0);

  const interactiveTags = new Set([
    "a",
    "area",
    "button",
    "details",
    "input",
    "label",
    "option",
    "select",
    "summary",
    "textarea",
  ]);

  const interactiveRoles = new Set([
    "button",
    "checkbox",
    "combobox",
    "gridcell",
    "link",
    "listbox",
    "menuitem",
    "menuitemcheckbox",
    "menuitemradio",
    "option",
    "radio",
    "scrollbar",
    "searchbox",
    "slider",
    "spinbutton",
    "switch",
    "tab",
    "textbox",
    "treeitem",
  ]);

  const locatorPriority = {
    data_testid_css: 115,
    data_testid_xpath: 114,
    id_css: 112,
    id_xpath: 111,
    role_name: 108,
    name_css: 104,
    name_xpath: 103,
    aria_label_css: 102,
    aria_label_xpath: 101,
    placeholder_css: 100,
    placeholder_xpath: 99,
    title_css: 98,
    title_xpath: 97,
    href_css: 96,
    href_xpath: 95,
    text_xpath: 92,
    text_playwright: 91,
    class_combo_css: 84,
    class_single_css: 80,
    class_xpath: 78,
    css_path: 70,
    xpath_absolute: 60,
  };

  const shellKeywords = [
    "menu",
    "nav",
    "navigation",
    "sidebar",
    "sider",
    "header",
    "topbar",
    "breadcrumb",
    "avatar",
    "profile",
  ];

  const paginationKeywords = [
    "pagination",
    "pager",
    "jumper",
    "btn-prev",
    "btn-next",
    "page-size",
  ];

  const tableStructureTags = new Set(["table", "thead", "tbody", "tr", "colgroup", "col"]);

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function hasMeaningfulText(value) {
    const text = normalizeText(value);
    if (!text) {
      return false;
    }

    if (text.length > 160) {
      return false;
    }

    return !/^\d+$/.test(text);
  }

  function firstMeaningful(values) {
    for (const value of values) {
      if (hasMeaningfulText(value)) {
        return normalizeText(value);
      }
    }

    return "";
  }

  function attributeValue(element, name) {
    if (!(element instanceof Element)) {
      return "";
    }

    return normalizeText(element.getAttribute(name));
  }

  function elementSummary(element) {
    if (!(element instanceof Element)) {
      return "";
    }

    const parts = [
      element.tagName ? element.tagName.toLowerCase() : "",
      attributeValue(element, "class"),
      attributeValue(element, "id"),
      attributeValue(element, "role"),
      attributeValue(element, "aria-label"),
    ];
    return parts.join(" ").toLowerCase();
  }

  function matchesKeywords(text, keywords) {
    return keywords.some((keyword) => text.includes(keyword));
  }

  function hasAncestorKeyword(element, keywords, maxDepth = 10) {
    let current = element;
    let depth = 0;

    while (current && depth < maxDepth) {
      const summary = elementSummary(current);
      if (matchesKeywords(summary, keywords)) {
        return true;
      }
      if (current.tagName) {
        const tag = current.tagName.toLowerCase();
        if (["nav", "header", "aside", "footer"].includes(tag)) {
          return true;
        }
      }
      current = current.parentElement;
      depth += 1;
    }

    return false;
  }

  function cssEscapeValue(value) {
    if (globalThis.CSS && typeof globalThis.CSS.escape === "function") {
      return globalThis.CSS.escape(value);
    }

    return String(value).replace(/([ !"#$%&'()*+,./:;<=>?@[\\\]^`{|}~])/g, "\\$1");
  }

  function xpathLiteral(value) {
    if (!String(value).includes("'")) {
      return "'" + value + "'";
    }

    if (!String(value).includes('"')) {
      return '"' + value + '"';
    }

    const parts = String(value).split("'");
    return "concat(" + parts.map((part, index) => {
      const piece = "'" + part + "'";
      if (index === parts.length - 1) {
        return piece;
      }
      return piece + ', "\"", ';
    }).join("") + ")";
  }

  function isVisible(element) {
    if (!(element instanceof Element)) {
      return false;
    }

    const style = getComputedStyle(element);
    if (style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse") {
      return false;
    }

    if (Number(style.opacity || "1") === 0) {
      return false;
    }

    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function isEnabled(element) {
    if ("disabled" in element && element.disabled) {
      return false;
    }

    return element.getAttribute("aria-disabled") !== "true";
  }

  function inferRole(element) {
    const explicitRole = normalizeText(element.getAttribute("role"));
    if (explicitRole) {
      return explicitRole;
    }

    const tag = element.tagName.toLowerCase();
    const inputType = normalizeText(element.getAttribute("type")).toLowerCase();

    if (tag === "a" && element.hasAttribute("href")) {
      return "link";
    }
    if (tag === "button") {
      return "button";
    }
    if (tag === "summary") {
      return "button";
    }
    if (tag === "select") {
      return element.multiple ? "listbox" : "combobox";
    }
    if (tag === "textarea") {
      return "textbox";
    }
    if (tag === "option") {
      return "option";
    }
    if (tag === "input") {
      if (["button", "submit", "reset"].includes(inputType)) {
        return "button";
      }
      if (inputType === "checkbox") {
        return "checkbox";
      }
      if (inputType === "radio") {
        return "radio";
      }
      if (inputType === "range") {
        return "slider";
      }
      if (inputType === "number") {
        return "spinbutton";
      }
      return "textbox";
    }

    return "";
  }

  function accessibleName(element) {
    const ariaLabel = normalizeText(element.getAttribute("aria-label"));
    if (ariaLabel) {
      return ariaLabel;
    }

    const labelledBy = normalizeText(element.getAttribute("aria-labelledby"));
    if (labelledBy) {
      const labelText = labelledBy
        .split(/\s+/)
        .map((id) => document.getElementById(id))
        .filter(Boolean)
        .map((node) => normalizeText(node.innerText || node.textContent))
        .filter(Boolean)
        .join(" ");
      if (labelText) {
        return labelText;
      }
    }

    if (element instanceof HTMLInputElement) {
      if (["button", "submit", "reset"].includes((element.type || "").toLowerCase())) {
        return normalizeText(element.value);
      }
    }

    const alt = normalizeText(element.getAttribute("alt"));
    if (alt) {
      return alt;
    }

    const title = normalizeText(element.getAttribute("title"));
    if (title) {
      return title;
    }

    const placeholder = normalizeText(element.getAttribute("placeholder"));
    if (placeholder) {
      return placeholder;
    }

    return normalizeText(element.innerText || element.textContent);
  }

  function nearestWrapper(element) {
    return (
      element.closest(".el-form-item") ||
      element.closest(".el-select") ||
      element.closest(".el-cascader") ||
      element.closest(".el-date-editor") ||
      element.closest(".el-input") ||
      element.closest(".el-textarea") ||
      element.parentElement
    );
  }

  function findNearbyDescriptor(element) {
    const wrapper = nearestWrapper(element);
    if (!wrapper) {
      return "";
    }

    const directCandidates = [
      attributeValue(wrapper, "placeholder"),
      attributeValue(wrapper, "aria-label"),
      attributeValue(wrapper, "title"),
    ];
    const directValue = firstMeaningful(directCandidates);
    if (directValue) {
      return directValue;
    }

    const nodes = wrapper.querySelectorAll(
      [
        "[placeholder]",
        "[aria-label]",
        "[title]",
        ".el-select__placeholder",
        ".el-select__selected-item",
        ".el-input__inner",
        ".el-textarea__inner",
        ".el-form-item__label",
      ].join(","),
    );

    for (const node of nodes) {
      const candidate = firstMeaningful([
        attributeValue(node, "placeholder"),
        attributeValue(node, "aria-label"),
        attributeValue(node, "title"),
        normalizeText(node.innerText || node.textContent),
      ]);
      if (candidate) {
        return candidate;
      }
    }

    return "";
  }

  function findFormLabel(element) {
    const formItem = element.closest(".el-form-item");
    if (!formItem) {
      return "";
    }

    const labelNode = formItem.querySelector(".el-form-item__label, label");
    if (!labelNode) {
      return "";
    }

    const clone = labelNode.cloneNode(true);
    clone.querySelectorAll(".label-box--dd, .label-box--dt").forEach((node) => node.remove());
    const text = normalizeText(clone.innerText || clone.textContent || "");
    if (text) {
      return text;
    }

    return normalizeText(labelNode.innerText || labelNode.textContent || "");
  }

  function getTextSnippet(element) {
    const text = normalizeText(element.innerText || element.textContent || "");
    return text.slice(0, 160);
  }

  function getAttributes(element) {
    const attributes = {};
    for (const attr of Array.from(element.attributes)) {
      attributes[attr.name] = attr.value;
    }
    return attributes;
  }

  function getDomPath(element) {
    const parts = [];
    let current = element;
    while (current && current.nodeType === Node.ELEMENT_NODE) {
      const tag = current.tagName.toLowerCase();
      const id = normalizeText(current.getAttribute("id"));
      const className = normalizeText(current.getAttribute("class"));
      parts.unshift({
        tag,
        id,
        class_name: className,
      });
      current = current.parentElement;
    }
    return parts;
  }

  function buildAbsoluteXPath(element) {
    const segments = [];
    let current = element;

    while (current && current.nodeType === Node.ELEMENT_NODE) {
      const tag = current.tagName.toLowerCase();
      let index = 1;
      let sibling = current.previousElementSibling;
      while (sibling) {
        if (sibling.tagName === current.tagName) {
          index += 1;
        }
        sibling = sibling.previousElementSibling;
      }
      segments.unshift(tag + "[" + index + "]");
      current = current.parentElement;
    }

    return "/" + segments.join("/");
  }

  function isUniqueCss(selector) {
    try {
      return document.querySelectorAll(selector).length === 1;
    } catch (error) {
      return false;
    }
  }

  function xpathCount(selector) {
    try {
      return document.evaluate(
        "count(" + selector + ")",
        document,
        null,
        XPathResult.NUMBER_TYPE,
        null,
      ).numberValue;
    } catch (error) {
      return 0;
    }
  }

  function isUniqueXPath(selector) {
    return xpathCount(selector) === 1;
  }

  function buildCssPath(element) {
    const parts = [];
    let current = element;

    while (current && current.nodeType === Node.ELEMENT_NODE) {
      const tag = current.tagName.toLowerCase();
      const id = normalizeText(current.getAttribute("id"));
      if (id) {
        const idSelector = "#" + cssEscapeValue(id);
        parts.unshift(idSelector);
        if (isUniqueCss(parts.join(" > "))) {
          break;
        }
        current = current.parentElement;
        continue;
      }

      let part = tag;
      const classes = Array.from(current.classList).filter(Boolean).slice(0, 3);
      if (classes.length) {
        const classSuffix = classes.map((className) => "." + cssEscapeValue(className)).join("");
        const classSelector = part + classSuffix;
        if (isUniqueCss(classSelector)) {
          part = classSelector;
        } else {
          part += classSuffix;
        }
      }

      let index = 1;
      let sibling = current.previousElementSibling;
      while (sibling) {
        if (sibling.tagName === current.tagName) {
          index += 1;
        }
        sibling = sibling.previousElementSibling;
      }
      part += ":nth-of-type(" + index + ")";
      parts.unshift(part);

      const candidate = parts.join(" > ");
      if (isUniqueCss(candidate)) {
        break;
      }

      current = current.parentElement;
    }

    return parts.join(" > ");
  }

  function buildClassXPath(tag, classes) {
    const predicates = classes
      .map((className) => "contains(concat(' ', normalize-space(@class), ' '), " + xpathLiteral(" " + className + " ") + ")")
      .join(" and ");
    return "//" + tag + "[" + predicates + "]";
  }

  function addCandidate(target, seen, candidate) {
    if (!candidate.value) {
      return;
    }

    const key = candidate.strategy + "||" + candidate.value;
    if (seen.has(key)) {
      return;
    }

    seen.add(key);
    target.push(candidate);
  }

  function buildLocatorCandidates(element, tag, role, accessName, textSnippet, attributes) {
    const candidates = [];
    const seen = new Set();
    const id = normalizeText(attributes.id);
    const name = normalizeText(attributes.name);
    const title = normalizeText(attributes.title);
    const placeholder = normalizeText(attributes.placeholder);
    const href = normalizeText(attributes.href);
    const ariaLabel = normalizeText(attributes["aria-label"]);
    const dataTestId = normalizeText(
      attributes["data-testid"] || attributes["data-test"] || attributes["data-qa"] || "",
    );
    const classes = normalizeText(attributes.class)
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 3);

    const cssPath = buildCssPath(element);
    addCandidate(candidates, seen, {
      strategy: "css_path",
      selector_type: "css",
      value: cssPath,
      unique_in_frame: isUniqueCss(cssPath),
      source: "dom_path",
      priority: locatorPriority.css_path,
    });

    const absoluteXPath = buildAbsoluteXPath(element);
    addCandidate(candidates, seen, {
      strategy: "xpath_absolute",
      selector_type: "xpath",
      value: absoluteXPath,
      unique_in_frame: isUniqueXPath(absoluteXPath),
      source: "dom_path",
      priority: locatorPriority.xpath_absolute,
    });

    if (dataTestId) {
      const cssSelector = "[data-testid='" + dataTestId.replace(/'/g, "\\'") + "']";
      addCandidate(candidates, seen, {
        strategy: "data_testid_css",
        selector_type: "css",
        value: cssSelector,
        unique_in_frame: isUniqueCss(cssSelector),
        source: "data-testid",
        priority: locatorPriority.data_testid_css,
      });

      const xpathSelector = "//*[@data-testid=" + xpathLiteral(dataTestId) + "]";
      addCandidate(candidates, seen, {
        strategy: "data_testid_xpath",
        selector_type: "xpath",
        value: xpathSelector,
        unique_in_frame: isUniqueXPath(xpathSelector),
        source: "data-testid",
        priority: locatorPriority.data_testid_xpath,
      });
    }

    if (id) {
      const cssSelector = "#" + cssEscapeValue(id);
      addCandidate(candidates, seen, {
        strategy: "id_css",
        selector_type: "css",
        value: cssSelector,
        unique_in_frame: isUniqueCss(cssSelector),
        source: "id",
        priority: locatorPriority.id_css,
      });

      const xpathSelector = "//*[@id=" + xpathLiteral(id) + "]";
      addCandidate(candidates, seen, {
        strategy: "id_xpath",
        selector_type: "xpath",
        value: xpathSelector,
        unique_in_frame: isUniqueXPath(xpathSelector),
        source: "id",
        priority: locatorPriority.id_xpath,
      });
    }

    if (role && accessName) {
      const roleSelector = "page.getByRole(" + JSON.stringify(role) + ", { name: " + JSON.stringify(accessName) + " })";
      addCandidate(candidates, seen, {
        strategy: "role_name",
        selector_type: "playwright",
        value: roleSelector,
        unique_in_frame: null,
        source: "role+accessible_name",
        priority: locatorPriority.role_name,
      });
    }

    if (name) {
      const cssSelector = tag + "[name='" + name.replace(/'/g, "\\'") + "']";
      addCandidate(candidates, seen, {
        strategy: "name_css",
        selector_type: "css",
        value: cssSelector,
        unique_in_frame: isUniqueCss(cssSelector),
        source: "name",
        priority: locatorPriority.name_css,
      });

      const xpathSelector = "//" + tag + "[@name=" + xpathLiteral(name) + "]";
      addCandidate(candidates, seen, {
        strategy: "name_xpath",
        selector_type: "xpath",
        value: xpathSelector,
        unique_in_frame: isUniqueXPath(xpathSelector),
        source: "name",
        priority: locatorPriority.name_xpath,
      });
    }

    if (ariaLabel) {
      const cssSelector = tag + "[aria-label='" + ariaLabel.replace(/'/g, "\\'") + "']";
      addCandidate(candidates, seen, {
        strategy: "aria_label_css",
        selector_type: "css",
        value: cssSelector,
        unique_in_frame: isUniqueCss(cssSelector),
        source: "aria-label",
        priority: locatorPriority.aria_label_css,
      });

      const xpathSelector = "//" + tag + "[@aria-label=" + xpathLiteral(ariaLabel) + "]";
      addCandidate(candidates, seen, {
        strategy: "aria_label_xpath",
        selector_type: "xpath",
        value: xpathSelector,
        unique_in_frame: isUniqueXPath(xpathSelector),
        source: "aria-label",
        priority: locatorPriority.aria_label_xpath,
      });
    }

    if (placeholder) {
      const cssSelector = tag + "[placeholder='" + placeholder.replace(/'/g, "\\'") + "']";
      addCandidate(candidates, seen, {
        strategy: "placeholder_css",
        selector_type: "css",
        value: cssSelector,
        unique_in_frame: isUniqueCss(cssSelector),
        source: "placeholder",
        priority: locatorPriority.placeholder_css,
      });

      const xpathSelector = "//" + tag + "[@placeholder=" + xpathLiteral(placeholder) + "]";
      addCandidate(candidates, seen, {
        strategy: "placeholder_xpath",
        selector_type: "xpath",
        value: xpathSelector,
        unique_in_frame: isUniqueXPath(xpathSelector),
        source: "placeholder",
        priority: locatorPriority.placeholder_xpath,
      });
    }

    if (title) {
      const cssSelector = tag + "[title='" + title.replace(/'/g, "\\'") + "']";
      addCandidate(candidates, seen, {
        strategy: "title_css",
        selector_type: "css",
        value: cssSelector,
        unique_in_frame: isUniqueCss(cssSelector),
        source: "title",
        priority: locatorPriority.title_css,
      });

      const xpathSelector = "//" + tag + "[@title=" + xpathLiteral(title) + "]";
      addCandidate(candidates, seen, {
        strategy: "title_xpath",
        selector_type: "xpath",
        value: xpathSelector,
        unique_in_frame: isUniqueXPath(xpathSelector),
        source: "title",
        priority: locatorPriority.title_xpath,
      });
    }

    if (href) {
      const cssSelector = tag + "[href='" + href.replace(/'/g, "\\'") + "']";
      addCandidate(candidates, seen, {
        strategy: "href_css",
        selector_type: "css",
        value: cssSelector,
        unique_in_frame: isUniqueCss(cssSelector),
        source: "href",
        priority: locatorPriority.href_css,
      });

      const xpathSelector = "//" + tag + "[@href=" + xpathLiteral(href) + "]";
      addCandidate(candidates, seen, {
        strategy: "href_xpath",
        selector_type: "xpath",
        value: xpathSelector,
        unique_in_frame: isUniqueXPath(xpathSelector),
        source: "href",
        priority: locatorPriority.href_xpath,
      });
    }

    if (textSnippet && textSnippet.length <= 120) {
      const xpathSelector = "//" + tag + "[normalize-space(.)=" + xpathLiteral(textSnippet) + "]";
      addCandidate(candidates, seen, {
        strategy: "text_xpath",
        selector_type: "xpath",
        value: xpathSelector,
        unique_in_frame: isUniqueXPath(xpathSelector),
        source: "text",
        priority: locatorPriority.text_xpath,
      });

      const playwrightText = "page.getByText(" + JSON.stringify(textSnippet) + ", { exact: true })";
      addCandidate(candidates, seen, {
        strategy: "text_playwright",
        selector_type: "playwright",
        value: playwrightText,
        unique_in_frame: null,
        source: "text",
        priority: locatorPriority.text_playwright,
      });
    }

    if (classes.length) {
      const classCombo = tag + classes.map((className) => "." + cssEscapeValue(className)).join("");
      addCandidate(candidates, seen, {
        strategy: "class_combo_css",
        selector_type: "css",
        value: classCombo,
        unique_in_frame: isUniqueCss(classCombo),
        source: "class",
        priority: locatorPriority.class_combo_css,
      });

      for (const className of classes) {
        const cssSelector = "." + cssEscapeValue(className);
        addCandidate(candidates, seen, {
          strategy: "class_single_css",
          selector_type: "css",
          value: cssSelector,
          unique_in_frame: isUniqueCss(cssSelector),
          source: "class",
          priority: locatorPriority.class_single_css,
        });
      }

      const xpathSelector = buildClassXPath(tag, classes);
      addCandidate(candidates, seen, {
        strategy: "class_xpath",
        selector_type: "xpath",
        value: xpathSelector,
        unique_in_frame: isUniqueXPath(xpathSelector),
        source: "class",
        priority: locatorPriority.class_xpath,
      });
    }

    candidates.sort((left, right) => {
      if (left.priority !== right.priority) {
        return right.priority - left.priority;
      }
      if (left.unique_in_frame === right.unique_in_frame) {
        return 0;
      }
      if (left.unique_in_frame === true) {
        return -1;
      }
      if (right.unique_in_frame === true) {
        return 1;
      }
      return 0;
    });

    const preferredLocators = {
      primary: null,
      css: null,
      xpath: null,
      playwright: null,
    };

    for (const candidate of candidates) {
      if (!preferredLocators.primary && candidate.unique_in_frame !== false) {
        preferredLocators.primary = candidate;
      }
      if (!preferredLocators[candidate.selector_type]) {
        preferredLocators[candidate.selector_type] = candidate;
      }
    }

    return {
      locator_candidates: candidates,
      preferred_locators: preferredLocators,
    };
  }

  function interactiveDetails(element) {
    const reasons = [];
    const tag = element.tagName.toLowerCase();
    const role = inferRole(element);
    const style = getComputedStyle(element);

    if (interactiveTags.has(tag)) {
      reasons.push("interactive_tag");
    }
    if (interactiveRoles.has(role)) {
      reasons.push("interactive_role");
    }
    if (tag === "a" && element.hasAttribute("href")) {
      reasons.push("href");
    }
    if (element.hasAttribute("onclick") || typeof element.onclick === "function") {
      reasons.push("click_handler");
    }
    if (element.hasAttribute("contenteditable")) {
      reasons.push("contenteditable");
    }
    if (element.hasAttribute("tabindex") && Number(element.getAttribute("tabindex")) >= 0) {
      reasons.push("tabindex");
    }
    if (style.cursor === "pointer") {
      reasons.push("cursor_pointer");
    }

    return {
      interactive: reasons.length > 0,
      reasons,
      role,
    };
  }

  function inferBusinessType(element, role, attributes) {
    const tag = element.tagName.toLowerCase();
    const type = normalizeText(attributes.type).toLowerCase();
    const summary = elementSummary(element);

    if (tag === "th") {
      return "table_column";
    }

    if (tag === "button" || type === "button" || type === "submit" || type === "reset") {
      if (element.closest("table") || element.closest(".el-table")) {
        return "table_action";
      }
      return "action_button";
    }

    if (tag === "a") {
      return "link_action";
    }

    if (type === "checkbox" || role === "checkbox") {
      return "checkbox";
    }

    if (type === "radio" || role === "radio") {
      return "radio";
    }

    if (type === "number" || role === "spinbutton") {
      return "number_input";
    }

    if (summary.includes("el-cascader")) {
      return "cascader";
    }

    if (summary.includes("el-select") || role === "combobox" || tag === "select") {
      return "select";
    }

    if (summary.includes("date") || summary.includes("picker")) {
      return "date_input";
    }

    if (tag === "textarea") {
      return "textarea";
    }

    return "text_input";
  }

  function businessName(element, tag, role, accessName, textSnippet, attributes) {
    if (tag === "th") {
      return firstMeaningful([textSnippet, accessName, normalizeText(element.innerText || element.textContent)]);
    }

    const type = normalizeText(attributes.type).toLowerCase();
    const byText = tag === "button" || tag === "a" || type === "button" || type === "submit" || type === "reset";

    if (byText) {
      return firstMeaningful([accessName, textSnippet, attributeValue(element, "title")]);
    }

    return firstMeaningful([
      findFormLabel(element),
      accessName,
      findNearbyDescriptor(element),
      attributes.placeholder,
      attributes["aria-label"],
      attributes.title,
      attributes.name,
      textSnippet,
    ]);
  }

  function scopeTitleFromNode(root) {
    if (!(root instanceof Element)) {
      return "";
    }

    const selectors = [
      ".head .title",
      ".title",
      ".el-dialog__title",
      ".ant-modal-title",
      ".modal-title",
      "[class*='title']",
    ];

    for (const selector of selectors) {
      const node = root.querySelector(selector);
      const text = normalizeText(node ? (node.innerText || node.textContent || "") : "");
      if (hasMeaningfulText(text)) {
        return text;
      }
    }

    return "";
  }

  function nearestBusinessScope(element) {
    const dialog = element.closest("[data-capture-modal-root='true'], .el-dialog, [role='dialog'], .el-drawer, .ant-modal, .modal, .dialog");
    if (dialog) {
      const title = scopeTitleFromNode(dialog);
      if (title) {
        return title;
      }
    }

    const module = element.closest(".module");
    if (module) {
      const title = scopeTitleFromNode(module);
      if (title) {
        return title;
      }
    }

    const team = element.closest(".team");
    if (team) {
      const title = scopeTitleFromNode(team) || "团队管理";
      if (title) {
        return title;
      }
    }

    const head = element.closest(".head");
    if (head) {
      const title = scopeTitleFromNode(head);
      if (title) {
        return title;
      }
    }

    return "";
  }

  function businessDetails(element, role, accessName, textSnippet, attributes, interactive, interactiveReasons) {
    const tag = element.tagName.toLowerCase();
    const type = normalizeText(attributes.type).toLowerCase();
    const className = normalizeText(attributes.class).toLowerCase();
    const style = getComputedStyle(element);
    const businessScope = nearestBusinessScope(element);

    if (tableStructureTags.has(tag)) {
      if (tag !== "th") {
        return {
          business: false,
          reasons: ["table_structure"],
        };
      }
    }

    if (hasAncestorKeyword(element, shellKeywords)) {
      return {
        business: false,
        reasons: ["shell_container"],
      };
    }

    if (hasAncestorKeyword(element, paginationKeywords)) {
      return {
        business: false,
        reasons: ["pagination_control"],
      };
    }

    if (tag === "input" && ["hidden", "file", "image"].includes(type)) {
      return {
        business: false,
        reasons: ["unsupported_input_type"],
      };
    }

    if (tag === "th") {
      const name = businessName(element, tag, role, accessName, textSnippet, attributes);
      if (!hasMeaningfulText(name)) {
        return {
          business: false,
          reasons: ["empty_table_header"],
        };
      }

      return {
        business: true,
        business_type: "table_column",
        business_name: name,
        business_scope: businessScope,
        reasons: ["table_header"],
      };
    }

    if (hasAncestorKeyword(element, shellKeywords)) {
      return {
        business: false,
        reasons: ["shell_container"],
      };
    }

    const directControl =
      ["input", "textarea", "select", "button", "a"].includes(tag) ||
      ["checkbox", "radio", "combobox", "spinbutton", "switch"].includes(role);

    if (!directControl) {
      const customActionName = firstMeaningful([
        accessName,
        textSnippet,
        attributes["aria-label"],
        attributes.title,
        findNearbyDescriptor(element),
      ]);
      const customTriggerTags = new Set(["div", "span", "svg", "i", "li"]);
      const interactiveLike =
        interactive ||
        style.cursor === "pointer" ||
        element.hasAttribute("onclick") ||
        typeof element.onclick === "function";
      const actionLikeClass = className.includes("add") || className.includes("action") || className.includes("tool");

      if (
        customTriggerTags.has(tag) &&
        interactiveLike &&
        hasMeaningfulText(customActionName) &&
        (actionLikeClass || interactiveReasons.includes("cursor_pointer") || interactiveReasons.includes("click_handler"))
      ) {
        return {
          business: true,
          business_type: "custom_action",
          business_name: customActionName,
          business_scope: businessScope,
          reasons: ["custom_action", ...interactiveReasons],
        };
      }
    }

    if (!directControl) {
      return {
        business: false,
        reasons: ["non_control_tag"],
      };
    }

    const name = businessName(element, tag, role, accessName, textSnippet, attributes);
    const businessType = inferBusinessType(element, role, attributes);
    const reasons = [businessType];

    if (
      tag === "input" &&
      className.includes("el-select__input") &&
      !hasMeaningfulText(name)
    ) {
      return {
        business: false,
        reasons: ["empty_select_helper"],
      };
    }

    const requiresLabel = !["checkbox", "radio"].includes(businessType);
    if (requiresLabel && !hasMeaningfulText(name)) {
      return {
        business: false,
        reasons: ["missing_business_name"],
      };
    }

    return {
      business: true,
      business_type: businessType,
      business_name: name,
      business_scope: businessScope,
      reasons,
    };
  }

  function businessDedupeKey(item) {
    return [
      item.business_type || item.tag_name,
      normalizeText(item.business_scope || "").toLowerCase(),
      normalizeText(item.business_name || item.accessible_name || item.text).toLowerCase(),
    ].join("|");
  }

  function businessScore(item) {
    let score = 0;
    const className = normalizeText(item.attributes.class).toLowerCase();

    if (item.tag_name === "button") {
      score += 40;
    }
    if (item.tag_name === "input") {
      score += 35;
    }
    if (item.tag_name === "textarea") {
      score += 34;
    }
    if (item.tag_name === "select") {
      score += 33;
    }
    if (hasMeaningfulText(item.business_name)) {
      score += 15;
    }
    if (item.preferred_locators.primary && item.preferred_locators.primary.unique_in_frame === true) {
      score += 10;
    }
    if (item.preferred_locators.playwright) {
      score += 8;
    }
    if (attributeValue({ getAttribute: (name) => item.attributes[name] || "" }, "placeholder")) {
      score += 4;
    }
    if (className.includes("el-select__input")) {
      score -= 12;
    }
    if (className.includes("el-cascader__search-input")) {
      score -= 8;
    }

    return score;
  }

  function dedupeBusinessPayload(payload) {
    const chosen = new Map();

    for (const item of payload) {
      const key = businessDedupeKey(item);
      const current = chosen.get(key);
      if (!current || businessScore(item) > businessScore(current)) {
        chosen.set(key, item);
      }
    }

    return Array.from(chosen.values());
  }

  function collectElements(rootNode) {
    const collected = [];

    function walk(node) {
      if (!node) {
        return;
      }

      const walker = document.createTreeWalker(node, NodeFilter.SHOW_ELEMENT);
      if (node.nodeType === Node.ELEMENT_NODE) {
        collected.push(node);
      }

      while (walker.nextNode()) {
        const current = walker.currentNode;
        collected.push(current);
        if (current.shadowRoot) {
          walk(current.shadowRoot);
        }
      }
    }

    walk(rootNode);
    return collected;
  }

  const root = scopeSelector ? document.querySelector(scopeSelector) : document.documentElement;
  if (!root) {
    return {
      error: "scope selector not found: " + scopeSelector,
      total_dom_elements: 0,
      returned_count: 0,
      truncated: false,
      elements: [],
    };
  }

  const allElements = collectElements(root);
  const filtered = [];

  for (const element of allElements) {
    const { interactive, reasons, role } = interactiveDetails(element);
    const visible = isVisible(element);
    const enabled = isEnabled(element);
    const attributes = getAttributes(element);
    const textSnippet = getTextSnippet(element);
    const accessName = accessibleName(element);
    const businessInfo = businessDetails(
      element,
      role,
      accessName,
      textSnippet,
      attributes,
      interactive,
      reasons,
    );

    if (!includeHidden && !visible) {
      continue;
    }

    if (captureMode === "business" && !businessInfo.business) {
      continue;
    }

    if (captureMode === "interactive" && !interactive) {
      continue;
    }

    filtered.push({
      element,
      interactive,
      reasons,
      role,
      visible,
      enabled,
      attributes,
      textSnippet,
      accessName,
      businessInfo,
    });
  }

  const limited = maxElements > 0 ? filtered.slice(0, maxElements) : filtered;
  let payload = limited.map((item, index) => {
    const element = item.element;
    const tag = element.tagName.toLowerCase();
    const attributes = item.attributes;
    const textSnippet = item.textSnippet;
    const accessName = item.accessName;
    const rect = element.getBoundingClientRect();
    const locatorInfo = buildLocatorCandidates(
      element,
      tag,
      item.role,
      accessName,
      textSnippet,
      attributes,
    );

    const payload = {
      dom_index: index,
      tag_name: tag,
      text: textSnippet,
      accessible_name: accessName,
      visible: item.visible,
      enabled: item.enabled,
      interactable: item.interactive,
      interactable_reasons: item.reasons,
      role: item.role,
      business: Boolean(item.businessInfo.business),
      business_type: item.businessInfo.business_type || null,
      business_name: item.businessInfo.business_name || null,
      business_scope: item.businessInfo.business_scope || null,
      business_reasons: item.businessInfo.reasons || [],
      attributes,
      bbox: {
        x: Number(rect.x.toFixed(2)),
        y: Number(rect.y.toFixed(2)),
        width: Number(rect.width.toFixed(2)),
        height: Number(rect.height.toFixed(2)),
      },
      locator_candidates: locatorInfo.locator_candidates,
      preferred_locators: locatorInfo.preferred_locators,
    };

    if (includeDomPath) {
      payload.dom_path = getDomPath(element);
    }

    return payload;
  });

  if (captureMode === "business") {
    payload = dedupeBusinessPayload(payload);
    payload = payload.map((item, index) => ({
      ...item,
      dom_index: index,
    }));
  }

  return {
    error: null,
    total_dom_elements: allElements.length,
    returned_count: payload.length,
    truncated: maxElements > 0 && payload.length >= maxElements,
    elements: payload,
  };
}
"""


TABLE_HEADERS_JS = r"""
(scopeSelector) => {
  const root = scopeSelector ? document.querySelector(scopeSelector) : document;
  if (!root) {
    return [];
  }

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  const headers = [];
  const nodes = root.querySelectorAll("th");
  for (const node of nodes) {
    const text = normalizeText(node.innerText || node.textContent || "");
    if (!text || text.length > 80) {
      continue;
    }

    const xpath = `//th[.//*[normalize-space(text())='${text}'] or normalize-space(.)='${text}']`;
    headers.push({
      tag_name: "th",
      text,
      accessible_name: text,
      visible: true,
      enabled: true,
      interactable: false,
      interactable_reasons: [],
      role: "",
      business: true,
      business_type: "table_column",
      business_name: text,
      business_reasons: ["table_header"],
      attributes: Object.fromEntries(Array.from(node.attributes).map((attr) => [attr.name, attr.value])),
      bbox: (() => {
        const rect = node.getBoundingClientRect();
        return {
          x: Number(rect.x.toFixed(2)),
          y: Number(rect.y.toFixed(2)),
          width: Number(rect.width.toFixed(2)),
          height: Number(rect.height.toFixed(2)),
        };
      })(),
      locator_candidates: [
        {
          strategy: "text_xpath",
          selector_type: "xpath",
          value: xpath,
          unique_in_frame: true,
          source: "text",
          priority: 92,
        },
        {
          strategy: "text_playwright",
          selector_type: "playwright",
          value: `page.getByText(${JSON.stringify(text)}, { exact: true })`,
          unique_in_frame: null,
          source: "text",
          priority: 91,
        },
      ],
      preferred_locators: {
        primary: {
          strategy: "text_xpath",
          selector_type: "xpath",
          value: xpath,
          unique_in_frame: true,
          source: "text",
          priority: 92,
        },
        css: null,
        xpath: {
          strategy: "text_xpath",
          selector_type: "xpath",
          value: xpath,
          unique_in_frame: true,
          source: "text",
          priority: 92,
        },
        playwright: {
          strategy: "text_playwright",
          selector_type: "playwright",
          value: `page.getByText(${JSON.stringify(text)}, { exact: true })`,
          unique_in_frame: null,
          source: "text",
          priority: 91,
        },
      },
    });
  }

  return headers;
}
"""


TEAM_PANEL_JS = r"""
() => {
  const panel = document.querySelector(".team");
  if (!panel) {
    return [];
  }

  const normalizeText = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const attributes = (node) => Object.fromEntries(Array.from(node.attributes).map((attr) => [attr.name, attr.value]));
  const bbox = (node) => {
    const rect = node.getBoundingClientRect();
    return {
      x: Number(rect.x.toFixed(2)),
      y: Number(rect.y.toFixed(2)),
      width: Number(rect.width.toFixed(2)),
      height: Number(rect.height.toFixed(2)),
    };
  };
  const visible = (node) => {
    if (!node) {
      return false;
    }
    const style = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const candidate = (strategy, selectorType, value, source = "team_panel") => ({
    strategy,
    selector_type: selectorType,
    value,
    unique_in_frame: null,
    source,
    priority: selectorType === "css" ? 88 : 87,
  });
  const makeItem = (node, businessType, businessName, reasons, locatorCandidates, extra = {}) => ({
    tag_name: node.tagName ? node.tagName.toLowerCase() : "div",
    text: normalizeText(node.innerText || node.textContent || ""),
    accessible_name: businessName,
    visible: visible(node),
    enabled: true,
    interactable: ["team_panel_action", "team_panel_item", "team_panel_expand_toggle", "team_panel_item_menu"].includes(businessType),
    interactable_reasons: ["team_panel"],
    role: "",
    business: true,
    business_type: businessType,
    business_name: businessName,
    business_reasons: reasons,
    attributes: attributes(node),
    bbox: bbox(node),
    locator_candidates: locatorCandidates,
    preferred_locators: {
      primary: locatorCandidates[0] || null,
      css: locatorCandidates.find((item) => item.selector_type === "css") || null,
      xpath: locatorCandidates.find((item) => item.selector_type === "xpath") || null,
      playwright: null,
    },
    ...extra,
  });

  const items = [];
  items.push(makeItem(
    panel,
    "team_panel_container",
    "团队管理区",
    ["team_panel_container"],
    [
      candidate("team_panel_css", "css", ".team"),
      candidate("team_panel_xpath", "xpath", "//div[contains(concat(' ', normalize-space(@class), ' '), ' team ') and .//*[normalize-space(.)='团队管理']]"),
    ],
  ));

  const title = panel.querySelector(".head .title");
  if (title) {
    items.push(makeItem(
      title,
      "team_panel_title",
      normalizeText(title.innerText || title.textContent || "团队管理"),
      ["team_panel_title"],
      [
        candidate("team_panel_title_css", "css", ".team .head .title"),
        candidate("team_panel_title_xpath", "xpath", "//div[contains(concat(' ', normalize-space(@class), ' '), ' team ')]//div[contains(concat(' ', normalize-space(@class), ' '), ' title ') and normalize-space(.)='团队管理']"),
      ],
    ));
  }

  const addButton = panel.querySelector(".head .add");
  if (addButton) {
    items.push(makeItem(
      addButton,
      "team_panel_action",
      normalizeText(addButton.innerText || addButton.textContent || "新增团队"),
      ["team_panel_action"],
      [
        candidate("team_panel_add_css", "css", ".team .head .add"),
        candidate("team_panel_add_xpath", "xpath", "//div[contains(concat(' ', normalize-space(@class), ' '), ' team ')]//div[contains(concat(' ', normalize-space(@class), ' '), ' add ') and normalize-space(.)='新增团队']"),
      ],
    ));
  }

  const listRoot = panel.querySelector(".items");
  const visibleItems = Array.from(panel.querySelectorAll(".items .item")).filter(visible);
  if (listRoot) {
    const sampleValues = visibleItems
      .map((node) => normalizeText(node.querySelector(".name")?.innerText || node.textContent || ""))
      .filter(Boolean)
      .slice(0, 20);
    items.push(makeItem(
      listRoot,
      "team_panel_collection",
      "团队列表",
      ["team_panel_collection"],
      [
        candidate("team_panel_items_css", "css", ".team .items .item"),
        candidate("team_panel_items_xpath", "xpath", ".//div[contains(concat(' ', normalize-space(@class), ' '), ' items ')]//div[contains(concat(' ', normalize-space(@class), ' '), ' item ')]"),
      ],
      { sample_values: sampleValues },
    ));
  }

  const firstItem = visibleItems[0];
  if (firstItem) {
    const nameNode = firstItem.querySelector(".name .overflow-ellipsis") || firstItem.querySelector(".name");
    if (nameNode) {
      items.push(makeItem(
        nameNode,
        "team_panel_item_name",
        "团队名称",
        ["team_panel_item_name"],
        [
          candidate("team_panel_item_name_css", "css", ".team .items .item .name .overflow-ellipsis"),
          candidate("team_panel_item_name_xpath", "xpath", ".//div[contains(concat(' ', normalize-space(@class), ' '), ' name ')]//*[contains(concat(' ', normalize-space(@class), ' '), ' overflow-ellipsis ')]"),
        ],
      ));
    }

    const expandNode = firstItem.querySelector(".expand-icon-box");
    if (expandNode) {
      items.push(makeItem(
        expandNode,
        "team_panel_expand_toggle",
        "团队展开按钮",
        ["team_panel_expand_toggle"],
        [
          candidate("team_panel_expand_css", "css", ".team .items .item .expand-icon-box"),
          candidate("team_panel_expand_xpath", "xpath", ".//div[contains(concat(' ', normalize-space(@class), ' '), ' expand-icon-box ')]"),
        ],
      ));
    }

    const menuNode = firstItem.querySelector(":scope > .add-icon");
    if (menuNode) {
      items.push(makeItem(
        menuNode,
        "team_panel_item_menu",
        "团队行操作入口",
        ["team_panel_item_menu"],
        [
          candidate("team_panel_item_menu_css", "css", ".team .items .item > .add-icon"),
          candidate("team_panel_item_menu_xpath", "xpath", ".//*[contains(concat(' ', normalize-space(@class), ' '), ' add-icon ')]"),
        ],
      ));
    }
  }

  return items;
}
"""


MODAL_EXTRAS_JS = r"""
(scopeSelector) => {
  const root = scopeSelector ? document.querySelector(scopeSelector) : null;
  if (!root) {
    return [];
  }

  const normalizeText = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const items = [];

  const titleNode = root.querySelector(".el-dialog__title, .ant-modal-title, .modal-title");
  if (titleNode) {
    const title = normalizeText(titleNode.innerText || titleNode.textContent || "");
    if (title) {
      items.push({
        tag_name: "span",
        text: title,
        accessible_name: title,
        visible: true,
        enabled: true,
        interactable: false,
        interactable_reasons: [],
        role: "",
        business: true,
        business_type: "modal_title",
        business_name: title,
        business_reasons: ["modal_title"],
        attributes: Object.fromEntries(Array.from(titleNode.attributes).map((attr) => [attr.name, attr.value])),
        bbox: (() => {
          const rect = titleNode.getBoundingClientRect();
          return {
            x: Number(rect.x.toFixed(2)),
            y: Number(rect.y.toFixed(2)),
            width: Number(rect.width.toFixed(2)),
            height: Number(rect.height.toFixed(2)),
          };
        })(),
        locator_candidates: [],
        preferred_locators: { primary: null, css: null, xpath: null, playwright: null },
      });
    }
  }

  const buttons = root.querySelectorAll("button, [role='button']");
  for (const button of buttons) {
    const style = getComputedStyle(button);
    const rect = button.getBoundingClientRect();
    if (style.display === "none" || style.visibility === "hidden" || rect.width === 0 || rect.height === 0) {
      continue;
    }

    let name = normalizeText(button.innerText || button.textContent || button.getAttribute("aria-label") || "");
    const className = normalizeText(button.getAttribute("class") || "");
    if (!name && className.includes("close")) {
      name = "关闭";
    }
    if (!name) {
      continue;
    }

    const xpath = `//button[normalize-space(.)='${name}']`;
    items.push({
      tag_name: "button",
      text: name,
      accessible_name: name,
      visible: true,
      enabled: !(button.disabled),
      interactable: true,
      interactable_reasons: ["interactive_tag", "interactive_role"],
      role: "button",
      business: true,
      business_type: "action_button",
      business_name: name,
      business_reasons: ["modal_button"],
      attributes: Object.fromEntries(Array.from(button.attributes).map((attr) => [attr.name, attr.value])),
      bbox: {
        x: Number(rect.x.toFixed(2)),
        y: Number(rect.y.toFixed(2)),
        width: Number(rect.width.toFixed(2)),
        height: Number(rect.height.toFixed(2)),
      },
      locator_candidates: [
        {
          strategy: "text_xpath",
          selector_type: "xpath",
          value: xpath,
          unique_in_frame: true,
          source: "text",
          priority: 92,
        },
        {
          strategy: "text_playwright",
          selector_type: "playwright",
          value: `page.getByText(${JSON.stringify(name)}, { exact: true })`,
          unique_in_frame: null,
          source: "text",
          priority: 91,
        },
      ],
      preferred_locators: {
        primary: {
          strategy: "text_xpath",
          selector_type: "xpath",
          value: xpath,
          unique_in_frame: true,
          source: "text",
          priority: 92,
        },
        css: null,
        xpath: {
          strategy: "text_xpath",
          selector_type: "xpath",
          value: xpath,
          unique_in_frame: true,
          source: "text",
          priority: 92,
        },
        playwright: {
          strategy: "text_playwright",
          selector_type: "playwright",
          value: `page.getByText(${JSON.stringify(name)}, { exact: true })`,
          unique_in_frame: null,
          source: "text",
          priority: 91,
        },
      },
    });
  }

  return items;
}
"""


MODAL_CAPTURE_JS = r"""
(options) => {
  const keywords = options.keywords || [];
  const normalizeText = (value) => String(value || "").replace(/\s+/g, " ").trim();

  const buttons = Array.from(document.querySelectorAll("button, [role='button']"));
  const matchButton = buttons.find((node) => {
    const text = normalizeText(node.innerText || node.textContent || node.getAttribute("aria-label") || "");
    return text && keywords.some((keyword) => text.includes(keyword));
  });

  if (!matchButton) {
    return {
      clicked: false,
      reason: "button_not_found",
      button_text: null,
      scope_selector: null,
    };
  }

  const buttonText = normalizeText(matchButton.innerText || matchButton.textContent || matchButton.getAttribute("aria-label") || "");
  matchButton.click();

  const dialogs = Array.from(document.querySelectorAll(".el-dialog, [role='dialog'], .ant-modal, .modal, .dialog"));
  let targetDialog = null;
  for (const dialog of dialogs) {
    const style = getComputedStyle(dialog);
    const rect = dialog.getBoundingClientRect();
    if (style.display === "none" || style.visibility === "hidden" || rect.width === 0 || rect.height === 0) {
      continue;
    }
    targetDialog = dialog;
    break;
  }

  if (!targetDialog) {
    return {
      clicked: true,
      reason: "dialog_not_found",
      button_text: buttonText,
      scope_selector: null,
    };
  }

  if (!targetDialog.hasAttribute("data-capture-modal-root")) {
    targetDialog.setAttribute("data-capture-modal-root", "true");
  }

  const titleNode = targetDialog.querySelector(".el-dialog__title, .ant-modal-title, .modal-title, [class*='title']");
  const title = normalizeText(titleNode ? (titleNode.innerText || titleNode.textContent) : "");

  return {
    clicked: true,
    reason: "ok",
    button_text: buttonText,
    modal_title: title,
    scope_selector: "[data-capture-modal-root='true']",
  };
}
"""


@dataclass
class ResolvedAuth:
    mode: str
    key: str
    scheme: str | None
    token_present: bool


BUSINESS_TYPE_TO_ELEMENT_TYPE = {
    "text_input": "input",
    "textarea": "input",
    "number_input": "input",
    "select": "input",
    "cascader": "input",
    "checkbox": "input",
    "radio": "input",
    "action_button": "button",
    "custom_action": "button",
    "table_action": "button",
    "link_action": "link",
    "table_column": "any",
    "modal_title": "any",
    "team_panel_container": "container",
    "team_panel_title": "any",
    "team_panel_action": "button",
    "team_panel_collection": "collection",
    "team_panel_item_name": "any",
    "team_panel_expand_toggle": "button",
    "team_panel_item_menu": "button",
}


COMMON_KEYWORD_REPLACEMENTS = {
    "帐号": "账号",
    "工号": "工号",
    "姓名": "姓名",
    "团队/分组": "团队 分组",
    "关闭此对话框": "关闭",
}

PHRASE_NAME_MAP = {
    "输入团队/组织名称": "team_organization_name",
    "团队/组织名称": "team_organization_name",
    "姓名": "name",
    "完整帐号": "full_account",
    "完整账号": "full_account",
    "完整工号": "full_employee_id",
    "团队/分组": "team_group",
    "团队": "team",
    "分组": "group",
    "选择角色": "role",
    "角色": "role",
    "状态": "status",
    "搜索": "search",
    "重置": "reset",
    "新增用户": "add_user",
    "批量导入": "batch_import",
    "导出": "export",
    "编辑": "edit",
    "设置角色": "set_role",
    "关闭": "close",
    "关闭此对话框": "close",
    "确定": "confirm",
    "取消": "cancel",
    "账号": "account",
    "工号": "employee_id",
    "手机": "mobile",
    "手机号": "mobile",
    "团队 新增团队": "team",
    "新增团队": "add_team",
    "一级分类": "primary_category",
    "二级分类": "secondary_category",
    "关联标签组": "tag_group",
    "添加": "add",
    "团队管理": "team_manage",
    "团队管理区": "team_panel",
    "团队列表": "team_list",
    "团队展开按钮": "team_expand",
    "团队行操作入口": "team_item_menu",
    "分组 新增分组": "group",
    "新增分组": "add_group",
    "创建时间": "created_time",
    "操作": "operation",
    "新增用户弹窗": "add_user_modal",
}


BUSINESS_TYPE_TO_KIND = {
    "text_input": "field",
    "textarea": "field",
    "number_input": "field",
    "select": "field",
    "cascader": "field",
    "checkbox": "field",
    "radio": "field",
    "action_button": "action",
    "custom_action": "action",
    "table_action": "row_action",
    "table_column": "table_column",
    "link_action": "link",
    "modal_title": "title",
    "team_panel_container": "container",
    "team_panel_title": "title",
    "team_panel_action": "action",
    "team_panel_collection": "collection",
    "team_panel_item_name": "item_name",
    "team_panel_expand_toggle": "toggle",
    "team_panel_item_menu": "action",
}


BUSINESS_TYPE_TO_GROUP = {
    "text_input": "filters",
    "textarea": "filters",
    "number_input": "filters",
    "select": "filters",
    "cascader": "filters",
    "checkbox": "filters",
    "radio": "filters",
    "action_button": "actions",
    "custom_action": "actions",
    "table_action": "table_actions",
    "table_column": "table",
    "link_action": "actions",
    "modal_title": "modal",
}


def snake_case(text: str) -> str:
    normalized = normalize_label(text)
    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", normalized)
    normalized = normalized.strip("_").lower()
    normalized = re.sub(r"_+", "_", normalized)
    return normalized or "element"


def normalize_label(text: str) -> str:
    value = (text or "").strip()
    for source, target in COMMON_KEYWORD_REPLACEMENTS.items():
        value = value.replace(source, target)
    return value


def remove_generic_prefix(text: str) -> str:
    value = text.strip()
    for prefix in ("输入", "请选择", "选择", "点击", "请输入"):
        if value.startswith(prefix) and len(value) > len(prefix):
            return value[len(prefix):].strip()
    return value


def is_probably_dynamic_id(value: str) -> bool:
    return bool(re.match(r"^el-id-\d+-\d+$", value or ""))


def is_generic_class(value: str) -> bool:
    if not value:
        return True
    class_names = [item for item in str(value).split() if item]
    if not class_names:
        return True
    generic_prefixes = ("el-",)
    generic_names = {
        "is-link",
        "is-active",
        "is-disabled",
        "is-focus",
    }
    meaningful = []
    for class_name in class_names:
        if class_name in generic_names:
            continue
        if class_name.startswith(generic_prefixes):
            continue
        meaningful.append(class_name)
    return len(meaningful) == 0


def infer_element_name(item: dict[str, Any], used_names: dict[str, int]) -> str:
    business_name = item.get("business_name") or item.get("accessible_name") or item.get("text") or ""
    base_label = remove_generic_prefix(normalize_label(business_name))
    base = PHRASE_NAME_MAP.get(base_label) or PHRASE_NAME_MAP.get(business_name) or snake_case(base_label)
    business_type = item.get("business_type") or ""
    business_scope = item.get("business_scope") or ""
    scope_label = normalize_label(business_scope)
    scope_base = PHRASE_NAME_MAP.get(scope_label) or PHRASE_NAME_MAP.get(business_scope) or snake_case(scope_label)

    suffix_map = {
        "text_input": "input",
        "textarea": "input",
        "number_input": "input",
        "select": "select",
        "cascader": "cascader",
        "checkbox": "checkbox",
        "radio": "radio",
        "action_button": "button",
        "custom_action": "button",
        "table_action": "button",
        "table_column": "column",
        "link_action": "link",
        "team_panel_container": "panel",
        "team_panel_title": "title",
        "team_panel_action": "button",
        "team_panel_collection": "collection",
        "team_panel_item_name": "item_name",
        "team_panel_expand_toggle": "button",
        "team_panel_item_menu": "button",
    }
    suffix = suffix_map.get(business_type, "element")
    candidate = f"{base}_{suffix}" if not base.endswith(f"_{suffix}") else base

    if scope_base and scope_base != "element":
        generic_bases = {"add", "element", "input", "button"}
        if base in generic_bases or candidate in used_names:
            candidate = f"{scope_base}_{candidate}"

    count = used_names.get(candidate, 0)
    used_names[candidate] = count + 1
    if count == 0:
        return candidate
    return f"{candidate}_{count + 1}"


def strategy_sort_key(strategy: dict[str, Any]) -> tuple[int, str]:
    type_order = {
        "test_id": 1,
        "id": 2,
        "role": 3,
        "label": 4,
        "placeholder": 5,
        "text": 6,
        "name": 7,
        "css": 8,
        "xpath": 9,
        "class": 10,
    }
    return (type_order.get(strategy["type"], 99), strategy["path"])


def build_locator_strategies(item: dict[str, Any]) -> list[dict[str, str]]:
    attrs = item.get("attributes", {}) or {}
    tag_name = item.get("tag_name", "")
    business_type = item.get("business_type") or ""
    business_name = item.get("business_name") or item.get("accessible_name") or item.get("text") or ""
    candidates = item.get("locator_candidates", []) or []
    field_like_types = {
        "text_input",
        "textarea",
        "number_input",
        "select",
        "cascader",
        "checkbox",
        "radio",
    }
    allow_multi_target = business_type in {"table_column", "table_action"}
    role = str(item.get("role") or "").strip()
    accessible_name = str(item.get("accessible_name") or "").strip()

    mapped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_strategy(strategy_type: str, path: str) -> None:
        key = (strategy_type, str(path))
        if key not in seen:
            seen.add(key)
            mapped.append({"type": strategy_type, "path": str(path)})

    def is_candidate_unique(candidate: dict[str, Any]) -> bool:
        if allow_multi_target:
            return True
        return candidate.get("unique_in_frame") is True

    test_id = attrs.get("data-testid") or attrs.get("data-test") or attrs.get("data-qa")
    if test_id:
        add_strategy("test_id", str(test_id))

    stable_id = None
    if attrs.get("id") and not is_probably_dynamic_id(str(attrs["id"])):
        stable_id = str(attrs["id"])
    if stable_id:
        add_strategy("id", stable_id)

    if attrs.get("name"):
        name_candidate = next(
            (
                candidate
                for candidate in candidates
                if candidate.get("strategy") in {"name_css", "name_xpath"} and is_candidate_unique(candidate)
            ),
            None,
        )
        if name_candidate or allow_multi_target:
            add_strategy("name", str(attrs["name"]))

    if role and accessible_name:
        role_candidate = next(
            (
                candidate
                for candidate in candidates
                if candidate.get("strategy") == "role_name"
            ),
            None,
        )
        if role_candidate:
            add_strategy("role", role_candidate.get("value") or "")
        else:
            add_strategy("role", f"getByRole({role}, {accessible_name})")

    if accessible_name and business_type in {"text_input", "textarea", "number_input", "select", "cascader", "checkbox", "radio"}:
        label_candidate = next(
            (
                candidate
                for candidate in candidates
                if candidate.get("strategy") in {"role_name", "text_playwright"}
            ),
            None,
        )
        if label_candidate:
            add_strategy("label", accessible_name)

    if attrs.get("placeholder"):
        placeholder_candidate = next(
            (
                candidate
                for candidate in candidates
                if candidate.get("strategy") in {"placeholder_css", "placeholder_xpath"} and is_candidate_unique(candidate)
            ),
            None,
        )
        if placeholder_candidate or allow_multi_target:
            add_strategy("placeholder", str(attrs["placeholder"]))

    if business_name:
        text_candidate = next(
            (
                candidate
                for candidate in candidates
                if candidate.get("strategy") in {"text_xpath", "text_playwright"} and is_candidate_unique(candidate)
            ),
            None,
        )
        if text_candidate or allow_multi_target:
            add_strategy("text", str(business_name))

    if business_name and business_type in {"action_button", "table_action"}:
        button_xpath = f"//button[normalize-space(.)='{str(business_name)}']"
        add_strategy("xpath", button_xpath)

    if business_name and business_type == "custom_action":
        add_strategy("text", str(business_name))

    if business_name and business_type == "select":
        add_strategy("text", str(business_name))
        select_xpath = f"//div[contains(@class,'el-select')][.//*[normalize-space(text())='{str(business_name)}']]"
        add_strategy("xpath", select_xpath)

    if business_name and business_type == "cascader":
        cascader_xpath = (
            f"//div[contains(@class,'el-cascader')][.//*[@placeholder='{str(business_name)}'] "
            f"or .//*[normalize-space(text())='{str(business_name)}']]"
        )
        cascader_candidate = next(
            (
                candidate
                for candidate in candidates
                if candidate.get("value") == cascader_xpath and is_candidate_unique(candidate)
            ),
            None,
        )
        if cascader_candidate:
            add_strategy("xpath", cascader_xpath)

    if business_name and business_type == "table_column":
        header_xpath = f"//th[.//*[normalize-space(text())='{str(business_name)}'] or normalize-space(.)='{str(business_name)}']"
        add_strategy("text", str(business_name))
        add_strategy("xpath", header_xpath)

    if business_type.startswith("team_panel_"):
        for candidate in candidates:
            selector_type = candidate.get("selector_type")
            value = candidate.get("value")
            if selector_type not in {"css", "xpath"} or not value:
                continue
            if selector_type == "css" and not is_candidate_unique(candidate):
                continue
            if selector_type == "xpath" and not is_candidate_unique(candidate):
                continue
            add_strategy(selector_type, str(value))

    xpath_value = None
    css_value = None
    class_name = attrs.get("class")

    for candidate in candidates:
        strategy = candidate.get("strategy")
        selector_type = candidate.get("selector_type")
        value = candidate.get("value")
        if not value:
            continue

        if selector_type == "xpath":
            if strategy in {"id_xpath", "name_xpath", "placeholder_xpath", "text_xpath", "data_testid_xpath"}:
                continue
            if not is_candidate_unique(candidate):
                continue
            if not xpath_value:
                xpath_value = value
        elif selector_type == "css":
            if strategy in {"id_css", "name_css", "placeholder_css", "data_testid_css"}:
                continue
            if not is_candidate_unique(candidate):
                continue
            if strategy == "class_single_css" and class_name and not is_generic_class(str(class_name)):
                class_value = str(class_name).split()[0]
                add_strategy("class", class_value)
                continue
            if strategy == "class_combo_css" and is_generic_class(str(class_name or "")):
                continue
            if not css_value:
                css_value = value

    if css_value and business_type not in {"action_button", "table_action", "table_column"} and business_type not in field_like_types:
        add_strategy("css", css_value)

    if xpath_value and business_type not in {"action_button", "table_action", "select", "cascader", "table_column"} and business_type not in field_like_types:
        add_strategy("xpath", xpath_value)

    mapped.sort(key=strategy_sort_key)
    return mapped


def build_semantic_config(item: dict[str, Any]) -> dict[str, Any] | None:
    business_name = item.get("business_name") or item.get("accessible_name") or item.get("text") or ""
    keywords: list[str] = []

    raw_values = [
        business_name,
        remove_generic_prefix(business_name),
        normalize_label(business_name),
    ]
    for value in raw_values:
        value = (value or "").strip()
        if value and value not in keywords:
            keywords.append(value)

    if not keywords:
        return None

    return {
        "keywords": keywords,
        "element_type": BUSINESS_TYPE_TO_ELEMENT_TYPE.get(item.get("business_type"), "any"),
    }


def export_kind_for_item(item: dict[str, Any]) -> str:
    return BUSINESS_TYPE_TO_KIND.get(item.get("business_type"), "element")


def export_group_for_item(item: dict[str, Any]) -> str:
    return BUSINESS_TYPE_TO_GROUP.get(item.get("business_type"), "main")


def column_key_for_business_name(business_name: str) -> str:
    return PHRASE_NAME_MAP.get(normalize_label(business_name)) or snake_case(remove_generic_prefix(normalize_label(business_name)))


def unique_column_key(
    business_name: str,
    column_class: str,
    used_names: dict[str, int],
) -> str:
    preferred = column_key_for_business_name(business_name)
    if preferred == "element" and column_class:
        preferred = snake_case(column_class)
    count = used_names.get(preferred, 0)
    used_names[preferred] = count + 1
    if count == 0:
        return preferred
    return f"{preferred}_{count + 1}"


def table_column_class(item: dict[str, Any]) -> str:
    class_name = item.get("attributes", {}).get("class", "")
    for token in str(class_name).split():
        if token.startswith("el-table_") and "_column_" in token:
            return token
    return ""


def modal_key_from_title(title: str) -> str:
    business_key = column_key_for_business_name(title)
    if business_key.endswith("_modal"):
        return business_key
    return f"{business_key}_modal"


def is_modal_item(item: dict[str, Any]) -> bool:
    reasons = item.get("business_reasons") or []
    if any(str(reason).startswith("modal_") for reason in reasons):
        return True
    if item.get("business_type") == "modal_title":
        return True
    attrs = item.get("attributes", {}) or {}
    class_name = str(attrs.get("class", ""))
    return "el-dialog" in class_name or item.get("frame", {}).get("modal_scope") is True


def is_table_action_item(item: dict[str, Any]) -> bool:
    business_type = item.get("business_type") or ""
    if business_type == "table_action":
        return True
    reasons = item.get("business_reasons") or []
    return "table_action" in reasons


def is_field_item(item: dict[str, Any]) -> bool:
    return (item.get("business_type") or "") in {
        "text_input",
        "textarea",
        "number_input",
        "select",
        "cascader",
        "checkbox",
        "radio",
    }


def is_action_item(item: dict[str, Any]) -> bool:
    return (item.get("business_type") or "") in {"action_button", "custom_action", "link_action"}


def dedupe_for_uiproject_export(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    type_priority = {
        "cascader": 50,
        "select": 45,
        "action_button": 40,
        "custom_action": 39,
        "table_action": 35,
        "table_column": 34,
        "team_panel_container": 33,
        "team_panel_title": 32,
        "team_panel_action": 32,
        "team_panel_collection": 32,
        "team_panel_item_name": 31,
        "team_panel_expand_toggle": 31,
        "team_panel_item_menu": 31,
        "text_input": 30,
        "textarea": 30,
        "number_input": 30,
        "checkbox": 25,
        "radio": 25,
    }

    for item in elements:
        name = normalize_label((item.get("business_name") or item.get("accessible_name") or item.get("text") or "").strip())
        if not name:
            continue
        business_type = item.get("business_type") or "any"
        business_scope = normalize_label((item.get("business_scope") or "").strip())
        scope = "modal" if is_modal_item(item) else "page"
        scope_key = f"{scope}::{business_scope}" if business_scope else scope
        if business_type == "table_column":
            dedupe_key = f"table_column::{name}"
        elif business_type.startswith("team_panel_"):
            dedupe_key = f"team_panel::{business_type}::{name}"
        elif business_type == "table_action":
            dedupe_key = f"table_action::{name}"
        elif business_type in {"action_button", "custom_action"}:
            dedupe_key = f"{scope_key}::action::{name}"
        elif business_type in {"text_input", "textarea", "number_input", "select", "cascader", "checkbox", "radio"}:
            dedupe_key = f"{scope_key}::field::{name}"
        else:
            dedupe_key = f"{scope_key}::{business_type}::{name}"

        current = chosen.get(dedupe_key)
        if not current:
            chosen[dedupe_key] = item
            continue

        current_score = type_priority.get(current.get("business_type"), 0)
        item_score = type_priority.get(item.get("business_type"), 0)
        if item_score > current_score:
            chosen[dedupe_key] = item

    return list(chosen.values())


def export_locator_yaml_v2(
    *,
    elements: list[dict[str, Any]],
    output_path: Path,
    page_name: str,
    page_url: str,
    modal_capture: dict[str, Any] | None = None,
) -> None:
    elements = dedupe_for_uiproject_export(elements)
    page_slug = output_path.stem
    filter_names: dict[str, int] = {}
    team_search_names: dict[str, int] = {}
    team_action_names: dict[str, int] = {}
    toolbar_names: dict[str, int] = {}
    row_action_names: dict[str, int] = {}
    table_column_names: dict[str, int] = {}
    modal_field_names: dict[str, int] = {}
    modal_action_names: dict[str, int] = {}

    def element_payload(item: dict[str, Any], kind: str | None = None) -> dict[str, Any] | None:
        strategies = build_locator_strategies(item)
        if not strategies:
            return None
        payload: dict[str, Any] = {
            "description": item.get("business_name") or item.get("accessible_name") or item.get("text") or "",
            "kind": kind or export_kind_for_item(item),
            "required": False,
            "strategies": strategies,
        }
        semantic = build_semantic_config(item)
        if semantic:
            payload["semantic"] = semantic
        return payload

    def add_named(
        target: dict[str, Any],
        item: dict[str, Any],
        *,
        kind: str | None = None,
        used_names: dict[str, int],
    ) -> str | None:
        name = infer_element_name(item, used_names)
        payload = element_payload(item, kind=kind)
        if not payload:
            return None
        target[name] = payload
        return name

    def add_table_column(target: dict[str, Any], item: dict[str, Any]) -> None:
        business_name = item.get("business_name") or ""
        column_class = table_column_class(item)
        if not column_class:
            return
        column_key = unique_column_key(business_name, column_class, table_column_names)

        header_strategies = build_locator_strategies(item)
        cell_strategies = [
            {"type": "css", "path": f".{column_class} .cell"},
            {"type": "xpath", "path": f".//td[contains(@class, '{column_class}')]//div[@class='cell']"},
        ]
        payload: dict[str, Any] = {
            "description": f"{business_name}单元格",
            "kind": "table_column",
            "required": False,
            "column_key": column_key,
            "header": business_name,
            "header_strategies": header_strategies,
            "cell_strategies": cell_strategies,
        }
        semantic = build_semantic_config(item)
        if semantic:
            payload["semantic"] = semantic
        target[column_key] = payload

    table_column_items = [item for item in elements if item.get("business_type") == "table_column"]
    modal_items = [item for item in elements if is_modal_item(item)]
    main_items = [
        item
        for item in elements
        if item.get("business_type") != "table_column" and not is_modal_item(item)
    ]

    filters: dict[str, Any] = {}
    team_panel: dict[str, Any] = {}
    team_panel_actions: dict[str, Any] = {}
    team_panel_search: dict[str, Any] = {}
    team_panel_items: dict[str, Any] = {}
    toolbar_actions: dict[str, Any] = {}
    row_actions: dict[str, Any] = {}
    table_columns: dict[str, Any] = {}
    modals: dict[str, Any] = {}

    for item in main_items:
        business_type = item.get("business_type") or ""
        business_name = normalize_label(item.get("business_name") or "")
        if business_type.startswith("team_panel_"):
            payload = element_payload(item, kind=export_kind_for_item(item))
            if not payload:
                continue
            if business_type == "team_panel_container":
                team_panel["container"] = payload
            elif business_type == "team_panel_title":
                team_panel["title"] = payload
            elif business_type == "team_panel_action":
                team_panel_actions[infer_element_name(item, team_action_names)] = payload
            elif business_type == "team_panel_collection":
                team_panel_items["collection"] = payload
                if item.get("sample_values"):
                    team_panel_items["sample_values"] = item["sample_values"]
            elif business_type == "team_panel_item_name":
                team_panel_items["item_name"] = payload
            elif business_type == "team_panel_expand_toggle":
                team_panel_items["expand_toggle"] = payload
            elif business_type == "team_panel_item_menu":
                team_panel_items["item_menu"] = payload
        elif is_field_item(item) and business_name == "输入团队/组织名称":
            add_named(team_panel_search, item, kind="field", used_names=team_search_names)
        elif is_field_item(item):
            add_named(filters, item, kind="field", used_names=filter_names)
        elif is_table_action_item(item):
            add_named(row_actions, item, kind="row_action", used_names=row_action_names)
        elif is_action_item(item):
            add_named(toolbar_actions, item, kind="action", used_names=toolbar_names)

    for item in table_column_items:
        add_table_column(table_columns, item)

    if modal_items:
        title_item = next((item for item in modal_items if item.get("business_type") == "modal_title"), None)
        modal_title = (
            (title_item or {}).get("business_name")
            or (modal_capture or {}).get("modal_title")
            or "modal"
        )
        modal_key = modal_key_from_title(modal_title)
        modal_fields: dict[str, Any] = {}
        modal_actions: dict[str, Any] = {}
        modal_title_payload: dict[str, Any] | None = None

        for item in modal_items:
            business_type = item.get("business_type") or ""
            if business_type == "modal_title":
                modal_title_payload = {
                    "description": item.get("business_name") or modal_title,
                    "kind": "title",
                    "required": True,
                    "strategies": [
                        {
                            "type": "xpath",
                            "path": f"//*[contains(@class, 'el-dialog__title') and normalize-space(.)='{item.get('business_name') or modal_title}']",
                        }
                    ],
                }
                continue
            if is_field_item(item):
                add_named(modal_fields, item, kind="field", used_names=modal_field_names)
            elif is_action_item(item):
                add_named(modal_actions, item, kind="action", used_names=modal_action_names)

        opened_by = None
        button_text = (modal_capture or {}).get("button_text")
        if button_text:
            opened_by = f"{column_key_for_business_name(button_text)}_button"

        modal_payload: dict[str, Any] = {
            "description": modal_title,
            "kind": "modal",
            "opened_by": opened_by,
            "container": {
                "description": f"{modal_title}弹窗容器",
                "kind": "container",
                "required": True,
                "strategies": [
                    {
                        "type": "xpath",
                        "path": f"//div[contains(@class, 'el-dialog') and .//*[normalize-space(.)='{modal_title}']]",
                    }
                ],
            },
        }
        if modal_title_payload:
            modal_payload["title"] = modal_title_payload
        modal_payload["fields"] = modal_fields
        modal_payload["actions"] = modal_actions
        modals[modal_key] = modal_payload

    regions: dict[str, Any] = {}

    team_panel_region = {
        "description": "团队管理区",
        **team_panel,
        "actions": team_panel_actions,
        "search": team_panel_search,
        "items": team_panel_items,
    }
    if (
        team_panel
        or team_panel_actions
        or team_panel_search
        or team_panel_items
    ):
        regions["team_panel"] = team_panel_region

    if filters:
        regions["filters"] = {
            "description": "筛选区",
            "fields": filters,
        }

    if toolbar_actions:
        regions["toolbar"] = {
            "description": "工具栏",
            "actions": toolbar_actions,
        }

    if table_columns or row_actions:
        regions["table"] = {
            "description": "数据表格",
            "collection": {
                "key": "user_rows",
                "description": "表格行数据",
                "kind": "collection",
                "required": False,
                "strategies": [{"type": "css", "path": ".el-table__row"}],
            },
            "columns": table_columns,
            "row_actions": row_actions,
        }

    if modals:
        regions["modals"] = modals

    payload: dict[str, Any] = {
        "schema_version": 2,
        "page": {
            "key": page_slug,
            "name": page_name,
            "url": page_url,
        },
        "regions": regions,
    }

    yaml_text = dump_locator_yaml(payload)
    output_path.write_text("# 页面元素定位配置\n# 由 capture-web-elements 自动生成\n\n" + yaml_text, encoding="utf-8")

    exported_count = (
        len(filters)
        + len(toolbar_actions)
        + len(row_actions)
        + len(table_columns)
        + len(team_panel_actions)
        + len(team_panel_search)
        + len([key for key in ("container", "title") if key in team_panel])
        + len([key for key in ("collection", "item_name", "expand_toggle", "item_menu") if key in team_panel_items])
    )
    if table_columns:
        exported_count += 1
    for modal in modals.values():
        exported_count += 1
        exported_count += 1 if modal.get("title") else 0
        exported_count += len(modal.get("fields", {}))
        exported_count += len(modal.get("actions", {}))

    summary_payload = {
        "page_slug": page_slug,
        "element_count": exported_count,
        "output_path": str(output_path),
    }
    print(json.dumps(summary_payload, ensure_ascii=False))


def compact_strategy_lists(yaml_text: str) -> str:
    data = yaml.safe_load(yaml_text)

    def quote(value: str) -> str:
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def render_strategy_list(strategies: list[dict[str, Any]]) -> str:
        rendered = []
        for strategy in strategies:
            pairs = []
            for key, value in strategy.items():
                pairs.append(f"{key}: {quote(value)}")
            rendered.append("{" + ", ".join(pairs) + "}")
        return "[" + ", ".join(rendered) + "]"

    strategy_paths: list[tuple[tuple[str, ...], list[dict[str, Any]]]] = []

    def walk(node: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"strategies", "cell_strategies", "header_strategies"} and isinstance(value, list):
                    if all(isinstance(item, dict) for item in value):
                        strategy_paths.append((path + (str(key),), value))
                else:
                    walk(value, path + (str(key),))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path + (str(index),))

    def get_indent_for_path(lines: list[str], path: tuple[str, ...]) -> tuple[int, int] | None:
        stack: list[tuple[int, str]] = []
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("- "):
                continue
            if ":" not in stripped:
                continue
            indent = len(line) - len(line.lstrip(" "))
            key = stripped.split(":", 1)[0].strip("'\"")
            while stack and stack[-1][0] >= indent:
                stack.pop()
            current_path = tuple(item[1] for item in stack) + (key,)
            if current_path == path:
                return index, indent
            stack.append((indent, key))
        return None

    lines = yaml_text.splitlines()
    for path, strategies in sorted(strategy_paths, key=lambda item: len(item[0]), reverse=True):
        found = get_indent_for_path(lines, path)
        if not found:
            continue
        start_index, indent = found
        end_index = start_index + 1
        while end_index < len(lines):
            next_line = lines[end_index]
            stripped = next_line.strip()
            if stripped:
                next_indent = len(next_line) - len(next_line.lstrip(" "))
                if next_indent <= indent:
                    break
            end_index += 1
        replacement = " " * indent + f"{path[-1]}: {render_strategy_list(strategies)}"
        lines[start_index:end_index] = [replacement]

    return "\n".join(lines) + "\n"


class FlowList(list):
    pass


class FlowDict(dict):
    pass


class LocatorYamlDumper(yaml.SafeDumper):
    pass


def _represent_flow_list(dumper: yaml.Dumper, data: FlowList) -> yaml.Node:
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)


def _represent_flow_dict(dumper: yaml.Dumper, data: FlowDict) -> yaml.Node:
    return dumper.represent_mapping("tag:yaml.org,2002:map", data, flow_style=True)


LocatorYamlDumper.add_representer(FlowList, _represent_flow_list)
LocatorYamlDumper.add_representer(FlowDict, _represent_flow_dict)


def dump_locator_yaml(payload: dict[str, Any]) -> str:
    def convert(node: Any, parent_key: str | None = None) -> Any:
        if parent_key in {"strategies", "cell_strategies", "header_strategies"} and isinstance(node, list):
            return FlowList(
                FlowDict({str(key): value for key, value in item.items()})
                if isinstance(item, dict)
                else item
                for item in node
            )
        if isinstance(node, dict):
            return {key: convert(value, str(key)) for key, value in node.items()}
        if isinstance(node, list):
            return [convert(value, parent_key) for value in node]
        return node

    return yaml.dump(
        convert(payload),
        Dumper=LocatorYamlDumper,
        allow_unicode=True,
        sort_keys=False,
        width=1000,
        default_flow_style=False,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture DOM elements and locator candidates from an authenticated page.",
    )
    parser.add_argument("--url", required=True, help="Target page URL.")
    parser.add_argument(
        "--auth-mode",
        default="none",
        choices=["none", "header", "cookie", "local-storage", "session-storage", "query"],
        help="How to inject the token into the page session.",
    )
    parser.add_argument(
        "--auth-key",
        default="Authorization",
        help="Header name, cookie name, storage key, or query parameter name.",
    )
    parser.add_argument(
        "--auth-scheme",
        default="Bearer",
        help="Header auth scheme used with header mode.",
    )
    parser.add_argument("--token", help="Token value. Prefer --token-env to avoid shell history.")
    parser.add_argument("--token-env", help="Environment variable name that holds the token.")
    parser.add_argument(
        "--wait-until",
        default="load",
        choices=["domcontentloaded", "load", "networkidle"],
        help="Navigation lifecycle to wait for before capture.",
    )
    parser.add_argument("--wait-selector", help="Optional selector that indicates the page is ready.")
    parser.add_argument(
        "--settle-ms",
        type=int,
        default=1500,
        help="Extra delay after readiness to allow client-side rendering to settle.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=30000,
        help="Timeout applied to navigation and waits.",
    )
    parser.add_argument(
        "--capture-mode",
        default="business",
        choices=["business", "interactive", "all"],
        help="Capture business controls, all interactive elements, or all visible DOM elements.",
    )
    parser.add_argument("--scope-selector", help="Optional selector used to limit the capture scope.")
    parser.add_argument(
        "--include-dom-path",
        action="store_true",
        help="Include ancestor-chain dom_path in the output payload for debugging.",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden elements instead of filtering them out.",
    )
    parser.add_argument(
        "--auto-scroll",
        action="store_true",
        help="Scroll the page before capture to trigger lazy-loaded content.",
    )
    parser.add_argument(
        "--save-screenshot",
        action="store_true",
        help="Save a full-page screenshot to the output directory.",
    )
    parser.add_argument(
        "--browser",
        default="chromium",
        choices=["chromium", "firefox", "webkit"],
        help="Browser engine to use.",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Launch a visible browser window for debugging.",
    )
    parser.add_argument("--user-agent", help="Optional user agent override.")
    parser.add_argument(
        "--cookie-domain",
        help="Cookie domain override for cookie auth mode. Defaults to the URL origin.",
    )
    parser.add_argument(
        "--cookie-path",
        default="/",
        help="Cookie path for cookie auth mode.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for output artifacts. Defaults to ./runs/<timestamp>.",
    )
    parser.add_argument(
        "--max-elements",
        type=int,
        default=0,
        help="Maximum number of elements to store. 0 means unlimited.",
    )
    parser.add_argument(
        "--export-locator-yaml",
        help="Export captured elements to the schema_version=2 layered locator YAML file.",
    )
    parser.add_argument(
        "--export-uiproject-yaml",
        help="Deprecated alias for --export-locator-yaml. Exports schema_version=2 locator YAML.",
    )
    parser.add_argument(
        "--export-page-name",
        help="Human-readable page name for exported locator YAML.",
    )
    parser.add_argument(
        "--export-page-url",
        help="Page url/path for exported locator YAML. Defaults to the final page URL path.",
    )
    parser.add_argument(
        "--click-keywords",
        nargs="+",
        help="Click the first visible button whose text contains any of these keywords before capture.",
    )
    parser.add_argument(
        "--capture-modal",
        action="store_true",
        help="After clicking a keyword-matched button, wait for and capture the opened modal/dialog only.",
    )
    parser.add_argument(
        "--expand-safe-dynamic",
        action="store_true",
        help="Discover safe dynamic triggers on the page, expand them one by one, and capture per-state artifacts.",
    )
    parser.add_argument(
        "--max-dynamic-triggers",
        type=int,
        default=12,
        help="Maximum number of safe dynamic triggers to expand when --expand-safe-dynamic is enabled.",
    )
    return parser.parse_args()


def resolve_output_dir(raw_output_dir: str | None) -> Path:
    if raw_output_dir:
        output_dir = Path(raw_output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = Path.cwd() / "runs" / timestamp

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir.resolve()


def resolve_token(args: argparse.Namespace) -> str | None:
    if args.token:
        return args.token

    if args.token_env:
        return os.environ.get(args.token_env)

    return None


def validate_auth(args: argparse.Namespace, token: str | None) -> ResolvedAuth:
    needs_token = args.auth_mode != "none"
    if needs_token and not token:
        raise SystemExit(
            f"auth-mode={args.auth_mode} requires a token. Supply --token or --token-env.",
        )

    return ResolvedAuth(
        mode=args.auth_mode,
        key=args.auth_key,
        scheme=args.auth_scheme if args.auth_mode == "header" else None,
        token_present=bool(token),
    )


def build_target_url(url: str, args: argparse.Namespace, token: str | None) -> str:
    if args.auth_mode != "query" or not token:
        return url

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[args.auth_key] = token
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def base_origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def apply_auth_to_context(context: Any, url: str, args: argparse.Namespace, token: str | None) -> None:
    if args.auth_mode == "cookie" and token:
        secure = urlparse(url).scheme == "https"
        cookie: dict[str, Any] = {
            "name": args.auth_key,
            "value": token,
            "path": args.cookie_path,
            "secure": secure,
        }

        if args.cookie_domain:
            cookie["domain"] = args.cookie_domain
        else:
            cookie["url"] = base_origin(url)

        context.add_cookies([cookie])

    if args.auth_mode in {"local-storage", "session-storage"} and token:
        storage_name = "localStorage" if args.auth_mode == "local-storage" else "sessionStorage"
        init_script = (
            f"window.{storage_name}.setItem({json.dumps(args.auth_key)}, {json.dumps(token)});"
        )
        context.add_init_script(init_script)


def build_context_options(args: argparse.Namespace, token: str | None) -> dict[str, Any]:
    options: dict[str, Any] = {}

    if args.user_agent:
        options["user_agent"] = args.user_agent

    if args.auth_mode == "header" and token:
        header_value = f"{args.auth_scheme} {token}".strip()
        options["extra_http_headers"] = {
            args.auth_key: header_value,
        }

    return options


def wait_for_page(page: Any, args: argparse.Namespace) -> None:
    page.wait_for_load_state(args.wait_until, timeout=args.timeout_ms)

    if args.wait_selector:
        page.locator(args.wait_selector).first.wait_for(
            state="visible",
            timeout=args.timeout_ms,
        )

    if args.settle_ms > 0:
        page.wait_for_timeout(args.settle_ms)


def auto_scroll(page: Any) -> None:
    page.evaluate(
        """
        async () => {
          await new Promise((resolve) => {
            const step = 600;
            const delay = 120;
            let previousHeight = -1;

            const timer = setInterval(() => {
              const doc = document.documentElement;
              const height = Math.max(doc.scrollHeight, document.body ? document.body.scrollHeight : 0);
              window.scrollBy(0, step);
              if (height === previousHeight && window.innerHeight + window.scrollY >= height) {
                clearInterval(timer);
                window.scrollTo(0, 0);
                setTimeout(resolve, 250);
                return;
              }
              previousHeight = height;
            }, delay);
          });
        }
        """,
    )


def clear_modal_markers(page: Any) -> None:
    page.evaluate(
        """
        () => {
          document.querySelectorAll('[data-capture-modal-root="true"]').forEach((node) => {
            node.removeAttribute('data-capture-modal-root');
          });
        }
        """
    )


def click_keyword_button(page: Any, keywords: list[str]) -> str | None:
    locator = page.locator(
        "button, [role='button'], .add, [class*='add'], [class*='action'], [class*='tool']"
    )
    count = locator.count()
    for index in range(count):
        button = locator.nth(index)
        try:
            if not button.is_visible():
                continue
        except PlaywrightError:
            continue

        try:
            shell_like = button.evaluate(
                """
                (node) => {
                  const shell = node.closest(
                    'nav, aside, header, [role="menu"], [role="menuitem"], .el-menu, .el-sub-menu, .el-menu-item, .menu-item'
                  );
                  return Boolean(shell);
                }
                """
            )
            if shell_like:
                continue
        except PlaywrightError:
            pass

        text = ""
        try:
            text = (button.inner_text() or "").strip()
        except PlaywrightError:
            text = ""
        if not text:
            try:
                text = (button.get_attribute("aria-label") or "").strip()
            except PlaywrightError:
                text = ""
        if not text:
            try:
                text = (button.get_attribute("title") or "").strip()
            except PlaywrightError:
                text = ""

        if text and any(keyword in text for keyword in keywords):
            button.click()
            return text

    return None


def wait_and_mark_visible_modal(page: Any, timeout_ms: int = 5000) -> dict[str, Any]:
    selectors = [
        ".el-dialog",
        ".el-message-box",
        "[role='dialog']",
        ".ant-modal",
        ".modal",
        ".dialog",
    ]
    deadline = time.time() + (timeout_ms / 1000)

    while time.time() < deadline:
        for selector in selectors:
            locator = page.locator(selector)
            try:
                count = locator.count()
            except PlaywrightError:
                continue

            for index in range(count):
                candidate = locator.nth(index)
                try:
                    if not candidate.is_visible():
                        continue
                except PlaywrightError:
                    continue

                candidate.evaluate(
                    """(node) => {
                        node.setAttribute('data-capture-modal-root', 'true');
                    }"""
                )

                modal_title = ""
                title_locator = candidate.locator(
                    ".el-dialog__title, .ant-modal-title, .modal-title, [class*='title']"
                ).first
                try:
                    if title_locator.count() > 0:
                        modal_title = (title_locator.inner_text() or "").strip()
                except PlaywrightError:
                    modal_title = ""

                return {
                    "clicked": True,
                    "reason": "ok",
                    "modal_title": modal_title,
                    "scope_selector": "[data-capture-modal-root='true']",
                }

        page.wait_for_timeout(200)

    return {
        "clicked": True,
        "reason": "dialog_not_found",
        "modal_title": "",
        "scope_selector": None,
    }


def trigger_modal_capture(page: Any, args: argparse.Namespace) -> dict[str, Any] | None:
    if not args.click_keywords:
        return None

    clear_modal_markers(page)
    button_text = click_keyword_button(page, args.click_keywords)
    if not button_text:
        return {
            "clicked": False,
            "reason": "button_not_found",
            "button_text": None,
            "scope_selector": None,
        }

    if not args.capture_modal:
        return {
            "clicked": True,
            "reason": "button_clicked",
            "button_text": button_text,
            "scope_selector": None,
        }

    payload = wait_and_mark_visible_modal(page, timeout_ms=max(args.timeout_ms, 5000))
    payload["button_text"] = button_text
    return payload


SAFE_DYNAMIC_KEYWORDS = (
    "新增",
    "添加",
    "编辑",
    "设置",
    "更多",
    "展开",
)


def slugify_text(value: str) -> str:
    value = normalize_label(value)
    value = re.sub(r"[^0-9a-zA-Z一-鿿]+", "_", value)
    value = value.strip("_").lower()
    value = re.sub(r"_+", "_", value)
    return value or "state"


def candidate_click_score(candidate: dict[str, Any]) -> int:
    strategy = str(candidate.get("strategy") or "")
    selector_type = str(candidate.get("selector_type") or "")
    unique = candidate.get("unique_in_frame") is True
    score = 0
    if unique:
        score += 100
    if strategy in {"id_css", "css_path", "href_css", "team_panel_add_css", "team_panel_items_css"}:
        score += 50
    elif strategy in {"id_xpath", "xpath_absolute", "href_xpath", "team_panel_add_xpath"}:
        score += 45
    elif strategy in {"role_name", "text_playwright"}:
        score += 35
    elif strategy in {"text_xpath", "class_combo_css", "class_xpath"}:
        score += 25

    if selector_type == "css":
        score += 10
    elif selector_type == "playwright":
        score += 8
    elif selector_type == "xpath":
        score += 6

    return score


def choose_click_candidate(item: dict[str, Any]) -> dict[str, Any] | None:
    candidates = item.get("locator_candidates", []) or []
    if not candidates:
        return None

    sorted_candidates = sorted(candidates, key=candidate_click_score, reverse=True)
    for candidate in sorted_candidates:
        selector_type = str(candidate.get("selector_type") or "")
        value = str(candidate.get("value") or "")
        if not value:
            continue
        if selector_type in {"css", "xpath", "playwright"}:
            return candidate
    return None


def build_locator_from_candidate(page: Any, candidate: dict[str, Any]) -> Any:
    selector_type = str(candidate.get("selector_type") or "")
    value = str(candidate.get("value") or "")
    if selector_type == "css":
        return page.locator(value)
    if selector_type == "xpath":
        return page.locator(f"xpath={value}")
    if selector_type == "playwright":
        role_match = re.fullmatch(r'page\.getByRole\("([^"]+)", \{ name: "([^"]*)" \}\)', value)
        if role_match:
            role_name, access_name = role_match.groups()
            kwargs = {"name": access_name} if access_name else {}
            return page.get_by_role(role_name, **kwargs)
        text_match = re.fullmatch(r'page\.getByText\("([^"]+)", \{ exact: true \}\)', value)
        if text_match:
            return page.get_by_text(text_match.group(1), exact=True)
    raise ValueError(f"Unsupported click candidate: {candidate}")


def is_safe_dynamic_trigger(item: dict[str, Any]) -> bool:
    business_type = str(item.get("business_type") or "")
    business_name = str(item.get("business_name") or item.get("accessible_name") or item.get("text") or "").strip()
    class_name = str((item.get("attributes") or {}).get("class") or "")
    scope = str(item.get("business_scope") or "")

    if not business_name and "add" not in class_name.lower():
        return False

    if business_type not in {
        "action_button",
        "custom_action",
        "table_action",
        "team_panel_action",
        "team_panel_expand_toggle",
        "team_panel_item_menu",
    }:
        return False

    shell_scope = normalize_label(scope)
    if shell_scope in {"系统管理", "内容管理", "后台管理"}:
        return False

    if any(keyword in business_name for keyword in SAFE_DYNAMIC_KEYWORDS):
        return True

    return "add" in class_name.lower()


def business_item_score(item: dict[str, Any]) -> int:
    attrs = item.get("attributes") or {}
    class_name = str(attrs.get("class") or "").lower()
    preferred = item.get("preferred_locators") or {}
    primary = preferred.get("primary") or {}
    business_name = str(item.get("business_name") or item.get("accessible_name") or item.get("text") or "").strip()
    tag_name = str(item.get("tag_name") or "").lower()

    score = 0
    if tag_name == "button":
        score += 40
    if tag_name == "input":
        score += 35
    if tag_name == "textarea":
        score += 34
    if tag_name == "select":
        score += 33
    if business_name:
        score += 15
    if isinstance(primary, dict) and primary.get("unique_in_frame") is True:
        score += 10
    if preferred.get("playwright"):
        score += 8
    if attrs.get("placeholder"):
        score += 4
    if "el-select__input" in class_name:
        score -= 12
    if "el-cascader__search-input" in class_name:
        score -= 8
    return score


def dedupe_dynamic_triggers(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    for item in elements:
        if not is_safe_dynamic_trigger(item):
            continue
        key = "||".join(
            [
                str(item.get("business_type") or ""),
                normalize_label(str(item.get("business_scope") or "")),
                normalize_label(str(item.get("business_name") or item.get("accessible_name") or item.get("text") or "")),
            ]
        )
        current = chosen.get(key)
        if current is None or business_item_score(item) > business_item_score(current):
            chosen[key] = item
    return list(chosen.values())


def open_target_page(
    page: Any,
    *,
    target_url: str,
    args: argparse.Namespace,
) -> None:
    page.goto(target_url, wait_until=args.wait_until, timeout=args.timeout_ms)
    wait_for_page(page, args)
    if args.auto_scroll:
        auto_scroll(page)
        if args.settle_ms > 0:
            page.wait_for_timeout(args.settle_ms)


def capture_state_elements(
    page: Any,
    *,
    args: argparse.Namespace,
    scope_selector: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    original_scope = args.scope_selector
    args.scope_selector = scope_selector
    frame_results: list[dict[str, Any]] = []
    skipped_frames: list[dict[str, Any]] = []
    elements: list[dict[str, Any]] = []
    for frame_index, frame in enumerate(page.frames):
        try:
            result = capture_frame(frame, frame_index, args)
        except PlaywrightError as exc:
            skipped_frames.append(
                {
                    "frame_index": frame_index,
                    "frame_name": frame.name or "",
                    "frame_url": frame.url,
                    "reason": str(exc),
                }
            )
            continue
        if result.get("error"):
            skipped_frames.append(
                {
                    "frame_index": frame_index,
                    "frame_name": frame.name or "",
                    "frame_url": frame.url,
                    "reason": result["error"],
                }
            )
            continue
        frame_results.append(result)
        elements.extend(result.get("elements", []))

    if args.capture_mode == "business":
        for frame_index, frame in enumerate(page.frames):
            try:
                elements.extend(collect_table_headers(frame, frame_index))
            except PlaywrightError:
                continue
            try:
                elements.extend(collect_team_panel(frame, frame_index))
            except PlaywrightError:
                continue
            if scope_selector:
                try:
                    extras = collect_modal_extras(frame, frame_index, scope_selector)
                    for element in extras:
                        element.setdefault("frame", {})["modal_scope"] = True
                    elements.extend(extras)
                except PlaywrightError:
                    continue

    args.scope_selector = original_scope
    return frame_results, skipped_frames, elements


def capture_dynamic_states(
    *,
    context: Any,
    args: argparse.Namespace,
    target_url: str,
    output_dir: Path,
    base_elements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not args.expand_safe_dynamic or args.scope_selector:
        return []

    triggers = dedupe_dynamic_triggers(base_elements)[: max(args.max_dynamic_triggers, 0) or None]
    if not triggers:
        return []

    dynamic_root = output_dir / "dynamic_states"
    dynamic_root.mkdir(parents=True, exist_ok=True)
    states: list[dict[str, Any]] = []

    for index, trigger in enumerate(triggers):
        candidate = choose_click_candidate(trigger)
        if not candidate:
            states.append(
                {
                    "index": index,
                    "trigger_name": trigger.get("business_name"),
                    "trigger_scope": trigger.get("business_scope"),
                    "reason": "no_click_candidate",
                    "state_type": "skipped",
                }
            )
            continue

        page = context.new_page()
        try:
            open_target_page(page, target_url=target_url, args=args)
            locator = build_locator_from_candidate(page, candidate)
            if locator.count() < 1 or not locator.first.is_visible():
                states.append(
                    {
                        "index": index,
                        "trigger_name": trigger.get("business_name"),
                        "trigger_scope": trigger.get("business_scope"),
                        "reason": "trigger_not_visible",
                        "state_type": "skipped",
                    }
                )
                page.close()
                continue

            before_url = page.url
            clear_modal_markers(page)
            locator.first.click()
            page.wait_for_timeout(max(args.settle_ms, 1200))
            dynamic_modal_timeout_ms = max(1000, min(args.timeout_ms, 5000))
            modal_capture = wait_and_mark_visible_modal(page, timeout_ms=dynamic_modal_timeout_ms)
            modal_capture["button_text"] = trigger.get("business_name")

            state_scope = modal_capture.get("scope_selector")
            state_type = "modal" if modal_capture.get("reason") == "ok" and state_scope else "page"
            state_name_seed = (
                modal_capture.get("modal_title")
                or f"{trigger.get('business_scope') or ''}_{trigger.get('business_name') or ''}"
                or f"state_{index}"
            )
            state_slug = slugify_text(state_name_seed)
            state_dir = dynamic_root / f"{index:02d}-{state_slug}"
            state_dir.mkdir(parents=True, exist_ok=True)

            frame_results, skipped_frames, state_elements = capture_state_elements(
                page,
                args=args,
                scope_selector=state_scope,
            )
            screenshot_path = state_dir / "page.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            final_url = page.url
            title = page.title()

            state_args = argparse.Namespace(**vars(args))
            state_args.output_dir = str(state_dir)
            state_args.scope_selector = state_scope
            summary = build_summary(
                args=state_args,
                auth=ResolvedAuth(args.auth_mode, args.auth_key, args.auth_scheme, True),
                output_dir=state_dir,
                target_url=target_url,
                final_url=final_url,
                title=title,
                frame_results=frame_results,
                skipped_frames=skipped_frames,
                screenshot_path=screenshot_path,
                modal_capture=modal_capture if state_type == "modal" else None,
            )
            summary["state_type"] = state_type
            summary["trigger"] = {
                "business_name": trigger.get("business_name"),
                "business_scope": trigger.get("business_scope"),
                "candidate": candidate,
                "navigated": final_url != before_url,
            }
            state_args.export_locator_yaml = str(state_dir / f"{state_slug}.yaml")
            state_args.export_uiproject_yaml = None
            state_args.export_page_name = f"{trigger.get('business_scope') or ''}-{trigger.get('business_name') or ''}".strip("-") or state_slug
            state_args.export_page_url = urlparse(final_url).path or "/"
            exported_yaml = export_yaml_if_needed(
                state_args,
                state_elements,
                final_url,
                modal_capture=modal_capture if state_type == "modal" else None,
            )
            if exported_yaml:
                summary["artifacts"]["locator_yaml"] = exported_yaml
            write_json(state_dir / "elements.json", state_elements)
            write_ndjson(state_dir / "elements.ndjson", state_elements)
            write_json(state_dir / "summary.json", summary)

            states.append(
                {
                    "index": index,
                    "state_name": state_slug,
                    "state_type": state_type,
                    "trigger_name": trigger.get("business_name"),
                    "trigger_scope": trigger.get("business_scope"),
                    "final_url": final_url,
                    "summary_json": str(state_dir / "summary.json"),
                    "elements_json": str(state_dir / "elements.json"),
                    "locator_yaml": exported_yaml,
                    "screenshot": str(screenshot_path),
                }
            )
        finally:
            try:
                page.close()
            except Exception:
                pass

    return states


def capture_frame(frame: Any, frame_index: int, args: argparse.Namespace) -> dict[str, Any]:
    snapshot = frame.evaluate(
        DOM_SNAPSHOT_JS,
        {
            "captureMode": args.capture_mode,
            "includeDomPath": args.include_dom_path,
            "includeHidden": args.include_hidden,
            "scopeSelector": args.scope_selector,
            "maxElements": args.max_elements,
        },
    )

    elements = snapshot.get("elements", [])
    for element_index, element in enumerate(elements):
        element["element_id"] = f"f{frame_index}-e{element_index}"
        element["frame"] = {
            "index": frame_index,
            "name": frame.name or "",
            "url": frame.url,
            "is_main_frame": frame == frame.page.main_frame,
        }

    snapshot["elements"] = elements
    snapshot["frame"] = {
        "index": frame_index,
        "name": frame.name or "",
        "url": frame.url,
        "is_main_frame": frame == frame.page.main_frame,
    }
    return snapshot


def collect_table_headers(frame: Any, frame_index: int) -> list[dict[str, Any]]:
    headers = frame.evaluate(TABLE_HEADERS_JS, ".el-table")
    for header_index, header in enumerate(headers):
        header["element_id"] = f"f{frame_index}-th{header_index}"
        header["frame"] = {
            "index": frame_index,
            "name": frame.name or "",
            "url": frame.url,
            "is_main_frame": frame == frame.page.main_frame,
        }
    return headers


def collect_team_panel(frame: Any, frame_index: int) -> list[dict[str, Any]]:
    items = frame.evaluate(TEAM_PANEL_JS)
    for item_index, item in enumerate(items):
        item["element_id"] = f"f{frame_index}-tp{item_index}"
        item["frame"] = {
            "index": frame_index,
            "name": frame.name or "",
            "url": frame.url,
            "is_main_frame": frame == frame.page.main_frame,
        }
    return items


def collect_modal_extras(frame: Any, frame_index: int, scope_selector: str) -> list[dict[str, Any]]:
    items = frame.evaluate(MODAL_EXTRAS_JS, scope_selector)
    for item_index, item in enumerate(items):
        item["element_id"] = f"f{frame_index}-mx{item_index}"
        item["frame"] = {
            "index": frame_index,
            "name": frame.name or "",
            "url": frame.url,
            "is_main_frame": frame == frame.page.main_frame,
        }
    return items


def build_summary(
    args: argparse.Namespace,
    auth: ResolvedAuth,
    output_dir: Path,
    target_url: str,
    final_url: str,
    title: str,
    frame_results: list[dict[str, Any]],
    skipped_frames: list[dict[str, Any]],
    screenshot_path: Path | None,
    modal_capture: dict[str, Any] | None = None,
    dynamic_states: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    total_dom_elements = sum(result.get("total_dom_elements", 0) for result in frame_results)
    total_captured = sum(result.get("returned_count", 0) for result in frame_results)
    truncated_frames = [
        result["frame"]["index"]
        for result in frame_results
        if result.get("truncated")
    ]

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "url": args.url,
            "target_url": target_url,
            "auth_mode": auth.mode,
            "auth_key": auth.key,
            "auth_scheme": auth.scheme,
            "token_present": auth.token_present,
            "wait_until": args.wait_until,
            "wait_selector": args.wait_selector,
            "settle_ms": args.settle_ms,
            "capture_mode": args.capture_mode,
            "scope_selector": args.scope_selector,
            "include_dom_path": args.include_dom_path,
            "include_hidden": args.include_hidden,
            "auto_scroll": args.auto_scroll,
            "max_elements": args.max_elements,
            "browser": args.browser,
        },
        "page": {
            "title": title,
            "final_url": final_url,
        },
        "counts": {
            "frame_count": len(frame_results),
            "skipped_frame_count": len(skipped_frames),
            "total_dom_elements": total_dom_elements,
            "captured_elements": total_captured,
            "truncated_frames": truncated_frames,
        },
        "artifacts": {
            "output_dir": str(output_dir),
            "summary_json": str(output_dir / "summary.json"),
            "elements_json": str(output_dir / "elements.json"),
            "elements_ndjson": str(output_dir / "elements.ndjson"),
            "screenshot": str(screenshot_path) if screenshot_path else None,
            "dynamic_states_json": str(output_dir / "dynamic_states.json") if dynamic_states else None,
        },
        "skipped_frames": skipped_frames,
        "modal_capture": modal_capture,
        "dynamic_states": dynamic_states or [],
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_ndjson(path: Path, elements: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for element in elements:
            handle.write(json.dumps(element, ensure_ascii=False))
            handle.write("\n")


def export_yaml_if_needed(
    args: argparse.Namespace,
    elements: list[dict[str, Any]],
    final_url: str,
    modal_capture: dict[str, Any] | None = None,
) -> str | None:
    export_path = args.export_locator_yaml or args.export_uiproject_yaml
    if not export_path:
        return None

    output_path = Path(export_path)
    if not output_path.is_absolute():
        output_path = (Path.cwd() / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    parsed_final = urlparse(final_url)
    default_page_name = args.export_page_name or parsed_final.path.strip("/").replace("/", "_") or "generated_page"
    export_page_url = args.export_page_url or parsed_final.path or "/"

    export_locator_yaml_v2(
        elements=elements,
        output_path=output_path,
        page_name=default_page_name,
        page_url=export_page_url,
        modal_capture=modal_capture,
    )
    return str(output_path)


def main() -> int:
    args = parse_args()
    output_dir = resolve_output_dir(args.output_dir)
    token = resolve_token(args)
    auth = validate_auth(args, token)
    target_url = build_target_url(args.url, args, token)

    browser_start = time.perf_counter()
    with sync_playwright() as playwright:
        browser_launcher = getattr(playwright, args.browser)
        browser = browser_launcher.launch(headless=not args.headful)
        context = browser.new_context(**build_context_options(args, token))
        apply_auth_to_context(context, target_url, args, token)
        page = context.new_page()

        try:
            page.goto(target_url, wait_until=args.wait_until, timeout=args.timeout_ms)
            wait_for_page(page, args)
            if args.auto_scroll:
                auto_scroll(page)
                if args.settle_ms > 0:
                    page.wait_for_timeout(args.settle_ms)
        except PlaywrightTimeoutError as exc:
            browser.close()
            raise SystemExit(f"Timed out while loading the page: {exc}") from exc
        except PlaywrightError as exc:
            browser.close()
            raise SystemExit(f"Browser failed while preparing the page: {exc}") from exc

        screenshot_path: Path | None = None

        frame_results: list[dict[str, Any]] = []
        skipped_frames: list[dict[str, Any]] = []
        original_scope_selector = args.scope_selector
        for frame_index, frame in enumerate(page.frames):
            try:
                result = capture_frame(frame, frame_index, args)
            except PlaywrightError as exc:
                skipped_frames.append(
                    {
                        "frame_index": frame_index,
                        "frame_name": frame.name or "",
                        "frame_url": frame.url,
                        "reason": str(exc),
                    }
                )
                continue

            if result.get("error"):
                skipped_frames.append(
                    {
                        "frame_index": frame_index,
                        "frame_name": frame.name or "",
                        "frame_url": frame.url,
                        "reason": result["error"],
                    }
                )
                continue

            frame_results.append(result)

        elements: list[dict[str, Any]] = []
        for result in frame_results:
            elements.extend(result.get("elements", []))

        if args.capture_mode == "business":
            for frame_index, frame in enumerate(page.frames):
                try:
                    elements.extend(collect_table_headers(frame, frame_index))
                except PlaywrightError:
                    continue
                try:
                    elements.extend(collect_team_panel(frame, frame_index))
                except PlaywrightError:
                    continue

        modal_capture: dict[str, Any] | None = None
        if args.click_keywords:
            modal_capture = trigger_modal_capture(page, args)
            if args.capture_modal and modal_capture and modal_capture.get("scope_selector"):
                args.scope_selector = modal_capture["scope_selector"]
                if args.settle_ms > 0:
                    page.wait_for_timeout(args.settle_ms)
                for frame_index, frame in enumerate(page.frames):
                    try:
                        modal_result = capture_frame(frame, frame_index, args)
                    except PlaywrightError:
                        continue
                    if modal_result.get("error"):
                        continue
                    for element in modal_result.get("elements", []):
                        element.setdefault("frame", {})["modal_scope"] = True
                        elements.append(element)
                    try:
                        for element in collect_modal_extras(frame, frame_index, args.scope_selector):
                            element.setdefault("frame", {})["modal_scope"] = True
                            elements.append(element)
                    except PlaywrightError:
                        continue
            args.scope_selector = original_scope_selector

        dynamic_states: list[dict[str, Any]] = capture_dynamic_states(
            context=context,
            args=args,
            target_url=target_url,
            output_dir=output_dir,
            base_elements=elements,
        )

        if args.save_screenshot:
            screenshot_path = output_dir / "page.png"
            page.screenshot(path=str(screenshot_path), full_page=True)

        final_url = page.url
        title = page.title()

        summary = build_summary(
            args=args,
            auth=auth,
            output_dir=output_dir,
            target_url=target_url,
            final_url=final_url,
            title=title,
            frame_results=frame_results,
            skipped_frames=skipped_frames,
            screenshot_path=screenshot_path,
            modal_capture=modal_capture,
            dynamic_states=dynamic_states,
        )
        summary["runtime_seconds"] = round(time.perf_counter() - browser_start, 3)
        exported_yaml = export_yaml_if_needed(args, elements, final_url, modal_capture=modal_capture)
        if exported_yaml:
            summary["artifacts"]["locator_yaml"] = exported_yaml

        write_json(output_dir / "elements.json", elements)
        write_ndjson(output_dir / "elements.ndjson", elements)
        if dynamic_states:
            write_json(output_dir / "dynamic_states.json", dynamic_states)
        write_json(output_dir / "summary.json", summary)

        browser.close()

    print(
        json.dumps(
            {
                "title": summary["page"]["title"],
                "final_url": summary["page"]["final_url"],
                "captured_elements": summary["counts"]["captured_elements"],
                "frame_count": summary["counts"]["frame_count"],
                "output_dir": summary["artifacts"]["output_dir"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
