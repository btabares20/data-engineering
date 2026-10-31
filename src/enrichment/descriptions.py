from html.parser import HTMLParser
import re


class DescriptionParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if not self.hidden and tag in ("p", "div", "li", "br", "h1", "h2", "h3", "h4", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden and tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "tr"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def description_text(value):
    if not isinstance(value, str) or not value.strip():
        return None
    parser = DescriptionParser()
    parser.feed(value)
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line) or None


def trademe_description(data):
    for key in ("DescriptionBody", "Body", "Description"):
        text = description_text(data.get(key))
        if text:
            return text, "full"
    text = description_text(data.get("ShortDescription"))
    return text, "summary" if text else "missing"
