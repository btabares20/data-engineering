from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
import re


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
TOKEN = re.compile(r"^(?:[a-zA-Z][\w-]*|\*)?(?:[.#][\w-]+|\[[\w-]+(?:=(?:\"[^\"]*\"|'[^']*'|[\w-]+))?\])*$")


@dataclass
class Element:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    parent: object = None

    def descendants(self):
        for child in self.children:
            if isinstance(child, Element):
                yield child
                yield from child.descendants()

    def text(self):
        if self.tag in ("script", "style"):
            return ""
        return " ".join(child.text() if isinstance(child, Element) else child for child in self.children).strip()

    def html(self):
        attrs = "".join(f' {name}="{escape(value, quote=True)}"' for name, value in self.attrs.items())
        inner = "".join(child.html() if isinstance(child, Element) else escape(child) for child in self.children)
        return f"<{self.tag}{attrs}>{inner}</{self.tag}>"


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Element("document")
        self.current = self.root
        self.count = 0
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.count += 1
        if self.count > 20000:
            raise ValueError("Page contains too many elements")
        depth = 0
        ancestor = self.current
        while ancestor is not None:
            depth += 1
            ancestor = ancestor.parent
        if depth > 100:
            raise ValueError("HTML nesting is too deep")
        node = Element(tag, {key: value or "" for key, value in attrs}, parent=self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def selector_steps(selector):
    if selector == "$":
        return []
    if not isinstance(selector, str) or not selector.strip() or len(selector) > 300:
        raise ValueError("A bounded CSS selector is required")
    tokens = re.findall(r"(?:[^\s>\[\"']|\[[^\]]*\])+|>", selector)
    compact = re.sub(r"\s+", "", selector)
    if re.sub(r"\s+", "", "".join(tokens)) != compact:
        raise ValueError("Unsupported CSS selector syntax")
    steps, direct = [], False
    for token in tokens:
        if token == ">":
            if not steps or direct:
                raise ValueError("Invalid child selector")
            direct = True
            continue
        if not TOKEN.fullmatch(token):
            raise ValueError("Use tags, classes, IDs, attributes, descendants, or child selectors")
        steps.append((token, direct))
        direct = False
    if direct or not steps or len(steps) > 10:
        raise ValueError("Invalid selector")
    return steps


def matches(node, token):
    tag = re.match(r"^[\w*-]+", token)
    if tag and tag.group() != "*" and node.tag != tag.group().lower():
        return False
    for kind, value in re.findall(r"([.#])([\w-]+)", re.sub(r"\[[^\]]*\]", "", token)):
        if kind == "#" and node.attrs.get("id") != value:
            return False
        if kind == "." and value not in node.attrs.get("class", "").split():
            return False
    for name, value in re.findall(r"\[([\w-]+)(?:=([^\]]+))?\]", token):
        if name not in node.attrs:
            return False
        if value and node.attrs[name] != value.strip("\"'"):
            return False
    return True


def select(root, selector):
    steps = selector_steps(selector)
    nodes = [root]
    for token, direct in steps:
        found, seen = [], set()
        for node in nodes:
            candidates = (child for child in node.children if isinstance(child, Element)) if direct else node.descendants()
            for candidate in candidates:
                if id(candidate) not in seen and matches(candidate, token):
                    found.append(candidate)
                    seen.add(id(candidate))
        nodes = found
    return nodes
