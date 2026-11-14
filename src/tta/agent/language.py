"""A sentence in Finnish or Swedish that the fixed rules cannot read is answered as such (REVIEW C2-8).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for" and the main goal, "one
obvious next step". The check of 15 Nov 2026 sent "Tarvitsen 500 litraa laktoositonta maitoa maanantaiksi" and was
asked "Which product is needed on line 1?", which does not say what to do. The fixed rules read English: of Finnish
and Swedish they know unit words, weekdays, some exclusions and the few product words of the type table, not
sentences. So when they cannot read a text that holds at least two words of the short lists below, the answer is
that they read English only for now, with the words that were recognised. The lists are ours and hold common
purchase words only, none of them an English word; no speaker checked them.
- Only a refusal is reworded: what the rules do read of Finnish or Swedish is read as before ("200 l kahvimaito").
- One such word changes nothing: it is a product's name as often as a language ("200 litres of Valio maito").
- A model reads these sentences; this is the fixed rules' answer, not a check on every reader.
"""

from __future__ import annotations

from collections.abc import Sequence

from tta.agent.textcheck import WORD
from tta.agent.unread import NotReadByRules

MIN_WORDS = 2  # fewer words of a list than this do not name a language
WORDS_QUOTED = 3
_WORDS: Sequence[tuple[str, frozenset[str], tuple[str, ...]]] = (  # the language, whole words, starts of words
    ("Finnish", frozenset({
        "haluan", "haluaisin", "haluamme", "tilaan", "tilaamme", "tilaus", "litra", "litraa", "kiloa",
        "kappaletta", "pakkausta", "maito", "maitoa", "kerma", "kermaa", "voita", "juusto", "juustoa", "leipää",
        "jogurttia", "kaurajuoma", "kaurajuomaa", "huomenna", "huomiseksi", "mennessä", "viimeistään", "kiitos",
        "ilman",
    }), ("tarvits", "tarvita", "laktoosit", "gluteenit", "maanantai", "tiistai", "keskiviikko", "torstai",
         "perjantai", "lauantai", "sunnuntai")),
    ("Swedish", frozenset({
        "jag", "behöver", "behövs", "vill", "beställa", "beställer", "beställning", "mjölk", "grädde", "smör",
        "bröd", "havredryck", "senast", "imorgon", "utan", "och",
    }), ("laktosfri", "glutenfri", "måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag")),
)

ANOTHER_LANGUAGE = "it looks like {language} ({words}), and the fixed rules read English only for now"
ASK_IN_ENGLISH = "Can you write it in English? For example: 200 litres of oat drink by Monday."


def _recognised(words: Sequence[str], whole: frozenset[str], starts: tuple[str, ...]) -> list[str]:
    """The words of one language's lists, each once, in the order the text says them."""
    return list(dict.fromkeys(word for word in words if word in whole or word.startswith(starts)))


def in_another_language(text: str) -> NotReadByRules | None:
    """The answer for a text that holds two or more Finnish or Swedish purchase words, or `None`. It names the
    language with the most such words and quotes the first of them."""
    words = WORD.findall(text.casefold())
    found = [(language, _recognised(words, whole, starts)) for language, whole, starts in _WORDS]
    language, recognised = max(found, key=lambda item: len(item[1]))
    if len(recognised) < MIN_WORDS:
        return None
    quoted = ", ".join(f'"{word}"' for word in recognised[:WORDS_QUOTED])
    return NotReadByRules(ANOTHER_LANGUAGE.format(language=language, words=quoted), ASK_IN_ENGLISH)
