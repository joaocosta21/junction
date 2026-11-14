"""The assumptions document is Markdown from the repository. It is rendered as data: everything is escaped."""

from __future__ import annotations

from tta.ui.markdown import render


def test_headings_paragraphs_and_emphasis() -> None:
    html = render("# Title\n\nFirst line\nsame paragraph.\n\n## Part *one*\n\nA **bold** word and `code`.\n")

    assert "<h1>Title</h1>" in html
    assert "<p>First line same paragraph.</p>" in html
    assert "<h2>Part <em>one</em></h2>" in html
    assert "<p>A <strong>bold</strong> word and <code>code</code>.</p>" in html


def test_lists_keep_their_kind_and_wrapped_items() -> None:
    html = render("- one\n- two\n  still two\n* three\n\n1. first\n2. second\n")

    assert "<ul><li>one</li><li>two still two</li><li>three</li></ul>" in html
    assert "<ol><li>first</li><li>second</li></ol>" in html


def test_a_pipe_table_becomes_a_table() -> None:
    html = render("| Setting | Value |\n|---|---|\n| `max_order_net_eur` | 750 |\n| a \\| b | **c** |\n")

    assert "<table><thead><tr><th>Setting</th><th>Value</th></tr></thead>" in html
    assert "<tr><td><code>max_order_net_eur</code></td><td>750</td></tr>" in html
    assert "<td>a | b</td><td><strong>c</strong></td>" in html


def test_a_fenced_block_is_kept_as_written() -> None:
    html = render("```\nPOST /v1/orders\n  **not bold** <b>\n```\nafter\n")

    assert "<pre><code>POST /v1/orders\n  **not bold** &lt;b&gt;</code></pre>" in html
    assert "<p>after</p>" in html


def test_quotes_and_rules() -> None:
    html = render("> quoted **text**\n> second line\n\n---\n")

    assert "<blockquote><p>quoted <strong>text</strong> second line</p></blockquote>" in html
    assert "<hr>" in html


def test_markup_in_the_document_is_escaped_everywhere() -> None:
    hostile = '<script>alert("x")</script>'
    html = render(
        f"# {hostile}\n\n{hostile}\n\n- {hostile}\n\n| {hostile} |\n|---|\n| {hostile} |\n\n"
        f"`{hostile}`\n\n> {hostile}\n\n[{hostile}](https://example.org)\n"
    )

    assert "<script" not in html
    assert html.count("&lt;script&gt;") == 8


def test_only_a_web_link_becomes_a_link() -> None:
    html = render(
        "[the spec](https://www.rfc-editor.org/rfc/rfc9457) and [bad](javascript:alert(1)) and [file](../README.md) "
        'and [quote](https://example.org/"onmouseover="x)\n'
    )

    assert '<a href="https://www.rfc-editor.org/rfc/rfc9457" rel="noopener noreferrer">the spec</a>' in html
    assert "javascript:" not in html and "bad" in html
    assert '<a href="../README.md"' not in html and "file" in html
    assert 'onmouseover="x' not in html


def test_an_empty_document_renders_as_nothing() -> None:
    assert render("") == ""
    assert render("\n\n   \n") == ""
