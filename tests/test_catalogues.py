from pathlib import Path

from babel.messages.pofile import read_po

TRANSLATIONS = Path(__file__).parent.parent / "oarepo_pgd" / "translations"


def test_the_czech_catalogue_translates_every_server_message():
    with open(TRANSLATIONS / "messages.pot", encoding="utf-8") as stream:
        template = read_po(stream)
    with open(TRANSLATIONS / "cs" / "LC_MESSAGES" / "messages.po", encoding="utf-8") as stream:
        czech = read_po(stream, locale="cs")
    expected = {message.id for message in template if message.id}
    translated = {
        message.id for message in czech
        if message.id and all(message.string if isinstance(message.string, tuple) else [message.string])
    }
    assert expected == translated
    assert czech.num_plurals == 3
