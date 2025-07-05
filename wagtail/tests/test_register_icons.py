import pytest
from wagtail import hooks
from wagtail.admin.icons import get_icon_sprite

def test_register_icons_hook_called(monkeypatch):
    executed = {'called': False}

    def fake_hook(icons):
        executed['called'] = True
        return icons

    monkeypatch.setattr(hooks, 'get_hooks', lambda name: [fake_hook] if name == 'register_icons' else [])
    
    _ = get_icon_sprite()

    assert executed['called'], "Hook register_icons não foi executado!"

def test_custom_icon_included_in_sprite(monkeypatch, tmp_path):
    # Cria um ícone SVG falso
    icon_file = tmp_path / "custom_icon.svg"
    icon_file.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M1"/></svg>')

    # Hook que retorna o caminho do ícone
    def fake_hook(_):
        return [str(icon_file)]

    # Monkeypatch para substituir os hooks
    monkeypatch.setattr(hooks, "get_hooks", lambda name: [fake_hook] if name == "register_icons" else [])

    # Executa a função que deveria construir o sprite
    sprite = get_icon_sprite()

    # Verifica se o conteúdo do <path d="M1"/> está presente no sprite final
    assert '<path d="M1"' in sprite, "Ícone personalizado não foi incluído no sprite!"


def test_default_icons_are_included_without_hooks(monkeypatch):
    # Simula que nenhum hook foi registrado
    monkeypatch.setattr(hooks, "get_hooks", lambda name: [] if name == "register_icons" else [])

    sprite = get_icon_sprite()

    # Esperamos que pelo menos um <symbol> esteja presente (de ícones padrão)
    assert "<symbol" in sprite, "Ícones padrão não foram incluídos no sprite!"


def test_multiple_hooks_include_all_icons(monkeypatch, tmp_path):
    # Cria dois arquivos SVG simulados
    icon1 = tmp_path / "icon1.svg"
    icon2 = tmp_path / "icon2.svg"
    icon1.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M1"/></svg>')
    icon2.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M2"/></svg>')

    # Dois hooks que retornam os caminhos SVG um após o outro
    def hook_one(existing_icons):
        return existing_icons + [str(icon1)]

    def hook_two(existing_icons):
        return existing_icons + [str(icon2)]

    # Monkeypatch para simular múltiplos hooks
    monkeypatch.setattr(hooks, "get_hooks", lambda name: [hook_one, hook_two] if name == "register_icons" else [])

    from wagtail.admin.icons import get_icon_sprite
    sprite = get_icon_sprite()

    # Verifica se ambos os ícones foram incluídos no resultado
    assert '<path d="M1"' in sprite, "Ícone 1 não incluído no sprite!"
    assert '<path d="M2"' in sprite, "Ícone 2 não incluído no sprite!"
