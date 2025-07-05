import hashlib
import itertools
import re
from functools import lru_cache

from django.template.loader import render_to_string
from django.urls import reverse

from wagtail import hooks
from pathlib import Path

icon_comment_pattern = re.compile(r"<!--.*?-->", re.DOTALL)


@lru_cache(maxsize=None)
def get_icons():
    icon_hooks = hooks.get_hooks("register_icons")
    all_icons = sorted(itertools.chain.from_iterable(hook([]) for hook in icon_hooks))
    combined_icon_markup = ""
    for icon in all_icons:
        symbol = (
            render_to_string(icon)
            .replace('xmlns="http://www.w3.org/2000/svg"', "")
            .replace("svg", "symbol")
        )
        symbol = icon_comment_pattern.sub("", symbol)
        combined_icon_markup += symbol

    return render_to_string(
        "wagtailadmin/shared/icons.html", {"icons": combined_icon_markup}
    )


icon_comment_pattern = re.compile(r"<!--.*?-->", re.DOTALL)

DEFAULT_ICONS = [
    '<svg xmlns="http://www.w3.org/2000/svg"><path d="M-default"/></svg>',
]

def get_all_icons():
    icons = DEFAULT_ICONS.copy()
    for hook in hooks.get_hooks("register_icons"):
        icons += hook([])  # ← ignora o conteúdo atual, apenas acumula
    return icons


def get_icon_sprite():
    icons = get_all_icons()
    combined = ""

    for item in icons:
        # Verifica se é um caminho de arquivo SVG
        if isinstance(item, (str, Path)) and str(item).endswith(".svg") and Path(item).exists():
            svg = Path(item).read_text(encoding="utf-8")
        else:
            svg = str(item)

        # Limpeza e conversão para <symbol>
        svg = svg.replace('xmlns="http://www.w3.org/2000/svg"', "")
        svg = svg.replace("<svg", "<symbol").replace("</svg>", "</symbol>")
        svg = icon_comment_pattern.sub("", svg)

        combined += svg

    return f'<svg xmlns="http://www.w3.org/2000/svg" style="display: none">{combined}</svg>'



@lru_cache(maxsize=None)
def get_icon_sprite_hash():
    return hashlib.sha1(get_icons().encode()).hexdigest()[:8]


def get_icon_sprite_url():
    return reverse("wagtailadmin_sprite") + f"?h={get_icon_sprite_hash()}"
