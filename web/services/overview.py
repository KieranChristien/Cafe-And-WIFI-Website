import nh3

OVERVIEW_CLEANER = nh3.Cleaner(
    tags={
        "p",
        "br",
        "h2",
        "h3",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "s",
        "ul",
        "ol",
        "li",
        "blockquote",
        "a",
    },
    attributes={
        "a": {"href", "title"},
    },
    clean_content_tags={
        "script",
        "style",
        "iframe",
        "object",
        "embed",
    },
    url_schemes={
        "http",
        "https",
        "mailto",
    },
    link_rel="noopener noreferrer",
)


def sanitize_overview(html: str | None) -> str:
    return OVERVIEW_CLEANER.clean(html or "")
