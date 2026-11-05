from __future__ import annotations

import base64
import os
import re
import stat
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pagekit.pages import (
    Page,
    PageError,
    build_page,
    check_page,
    load_page,
    new_page,
    pack_page,
    pages_root,
    prune_if_due,
    prune_pages,
    save_page,
)
from pagekit.profiles import Profile, init_profile, load_profile

NAMED_FORM = '<input name="a.text"><textarea name="a.notes"></textarea>'


def make(profile: Profile, slug: str = "demo", body: str = "<p>Hello</p>", mode: str = "slots") -> Page:
    page, _ = new_page(profile, slug, "Demo", "One line", mode)
    if mode == "slots":
        page.content.write_text(body, encoding="utf-8")
    build_page(profile, page)
    return page


def age(page: Page, days: float) -> None:
    stamp = datetime.now(timezone.utc) - timedelta(days=days)
    page.meta["updated"] = stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    page.write_meta()


def errors(profile: Profile, page: Page) -> str:
    return "\n".join(check_page(profile, page).errors)


def test_build_composes_a_self_contained_page(home: Path) -> None:
    profile = load_profile()
    page = make(profile)
    document = page.index.read_text()
    assert page.dir == home / "pages" / "default" / "demo"
    assert "<title>Demo</title>" in document and "<p>Hello</p>" in document and "--pk-accent" in document
    assert 'id="pk-export" class="pk-button" hidden' in document and "window.pagekit" in document
    assert 'class="pk-summary">One line' in document
    assert check_page(profile, page).ok


def test_new_is_idempotent_and_keeps_content(home: Path) -> None:
    profile = load_profile()
    page = make(profile, body="<p>Mine</p>")
    again, created = new_page(profile, "demo", None, None, "slots")
    assert not created and again.dir == page.dir
    assert again.content.read_text() == "<p>Mine</p>"
    assert again.meta["title"] == "Demo"


def test_new_needs_a_title_and_a_valid_slug(home: Path) -> None:
    profile = load_profile()
    with pytest.raises(PageError, match="title"):
        new_page(profile, "fresh", None, None, "slots")
    with pytest.raises(PageError, match="slug"):
        new_page(profile, "../escape", "T", None, "slots")


def test_content_placeholders_are_left_as_written(home: Path) -> None:
    profile = load_profile()
    page = make(profile, body="<code>{{footer}}</code>")
    assert "<code>{{footer}}</code>" in page.index.read_text()


def test_answers_key_survives_a_restyle_but_not_a_content_change(home: Path) -> None:
    profile = load_profile()

    def rev(page: Page) -> str:
        return re.search(r'"rev": "(\w+)"', page.index.read_text()).group(1)

    page = make(profile, body="<p>One</p>")
    first = rev(page)
    build_page(profile, page)
    assert rev(page) == first
    page.content.write_text("<p>Two</p>")
    build_page(profile, page)
    assert rev(page) != first


def test_print_layout_repeats_without_relying_on_page_margins(home: Path) -> None:
    profile = load_profile()
    document = make(profile).index.read_text()
    assert "display: table-header-group" in document and "break-inside: avoid" in document
    assert '<div class="pk-print-spacer" aria-hidden="true"><div></div></div>' in document
    assert "counter(pages)" in document


def test_built_page_carries_item_comments_that_do_not_print(home: Path) -> None:
    document = make(load_profile(), body='<span class="pk-id">D-01</span>').index.read_text()
    assert '"comments:"' in document and ".pk-comment" in document
    assert re.search(r"@media print \{.*\.pk-comment,", document, re.DOTALL)


def test_copyright_setting_adds_an_ascii_safe_footer_notice(home: Path) -> None:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    (directory / "profile.toml").write_text(
        'name = "acme"\nextends = "builtin"\nfooter = "Acme internal"\ncopyright = "Acme & Co"\n'
    )
    profile = load_profile(repo)
    page = make(profile)
    assert "<span>Acme internal</span><span>&copy; Acme &amp; Co</span><span>Updated" in page.index.read_text()
    assert check_page(profile, page).ok


def test_no_copyright_setting_means_no_notice(home: Path) -> None:
    assert "&copy;" not in make(load_profile()).index.read_text()


def test_icons_are_stored_once_however_many_times_they_are_used(home: Path) -> None:
    profile = load_profile()
    body = '<p>' + '<i data-icon="database" tone="blue"></i>' * 50 + '<i data-icon="x" aria-label="Close"></i></p>'
    document = make(profile, body=body).index.read_text()
    assert document.count('<symbol id="pk-i-database"') == 1
    assert document.count('<use href="#pk-i-database"/>') == 50
    assert 'class="pk-icon pk-icon-blue" aria-hidden="true"' in document
    assert 'role="img" aria-label="Close"' in document and "<i data-icon" not in document
    assert check_page(profile, make(profile, slug="again", body=body)).ok


def test_unused_icons_cost_nothing(home: Path) -> None:
    document = make(load_profile()).index.read_text()
    assert 'id="pk-i-database"' not in document
    assert 'id="pk-i-download"' in document  # the page's own header button


@pytest.mark.parametrize(
    ("body", "message"),
    [('<i data-icon="not-a-real-icon"></i>', "no icon named"), ('<i data-icon="x" tone="pink"></i>', "unknown icon tone")],
)
def test_unknown_icons_and_tones_fail_the_build(home: Path, body: str, message: str) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "x", "X", None, "slots")
    page.content.write_text(body, encoding="utf-8")
    with pytest.raises(PageError, match=message):
        build_page(profile, page)


def icon_profile(home: Path) -> Profile:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    icons = directory / "icons"
    icons.mkdir()
    (icons / "mark.svg").write_text(
        '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="27 39 131 128"><defs>'
        '<style>.a, .b { fill: url(#grad); } .b { opacity: 0.5; }</style><linearGradient id="grad"/></defs>'
        '<path class="a" d="M0 0"/><path class="b" d="M1 1"/></svg>'
    )
    (icons / "mark-dark.svg").write_text('<svg width="512" height="512"><path id="p" d="M2 2"/><use href="#p"/></svg>')
    (icons / "plain.svg").write_text('<svg viewBox="0 0 8 8"><rect width="8" height="8"/></svg>')
    return load_profile(repo)


def test_profile_icons_are_namespaced_and_pair_with_a_dark_version(home: Path) -> None:
    document = make(icon_profile(home), body='<i data-icon="mark"></i><i data-icon="mark"></i>').index.read_text()
    assert document.count('<symbol id="pk-i-mark" viewBox="27 39 131 128"') == 1
    assert document.count('<symbol id="pk-i-mark-dark" viewBox="0 0 512 512"') == 1
    assert 'id="pk-i-mark-grad"' in document and "url(#pk-i-mark-grad)" in document
    assert 'style="fill: url(#pk-i-mark-grad)"' in document
    assert 'style="fill: url(#pk-i-mark-grad); opacity: 0.5"' in document
    assert 'href="#pk-i-mark-dark-p"' in document
    assert '<svg class="pk-icon pk-icon-paired" aria-hidden="true"><use class="pk-icon-light" href="#pk-i-mark"/>' in document


def test_a_profile_icon_with_no_dark_version_uses_one_drawing(home: Path) -> None:
    document = make(icon_profile(home), body='<i data-icon="plain"></i>').index.read_text()
    assert '<svg class="pk-icon" aria-hidden="true"><use href="#pk-i-plain"/></svg>' in document
    assert 'id="pk-i-mark"' not in document


def test_a_print_image_is_stored_once_and_used_only_for_print(home: Path) -> None:
    profile = icon_profile(home)
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (64).to_bytes(4, "big") + (32).to_bytes(4, "big") + b"rest"
    (profile.nearest / "icons" / "plain-print.png").write_bytes(png)
    document = make(profile, body='<i data-icon="plain"></i>' * 5).index.read_text()
    assert document.count('<symbol id="pk-i-plain-print" viewBox="0 0 64 32"><image href="data:image/png;base64,') == 1
    assert document.count('<use class="pk-icon-print" href="#pk-i-plain-print"/>') == 5
    assert document.count('<use class="pk-icon-light" href="#pk-i-plain"/>') == 5
    assert "plain-print" not in search_icons_names(profile)


def test_a_print_image_must_be_a_png(home: Path) -> None:
    profile = icon_profile(home)
    (profile.nearest / "icons" / "plain-print.png").write_bytes(b"not a png")
    page, _ = new_page(profile, "x", "X", None, "slots")
    page.content.write_text('<i data-icon="plain"></i>')
    with pytest.raises(PageError, match="must be a PNG"):
        build_page(profile, page)


def search_icons_names(profile: Profile) -> list[str]:
    from pagekit.icons import custom_icons

    return list(custom_icons(profile))


def test_a_profile_icon_with_a_script_is_refused(home: Path) -> None:
    profile = icon_profile(home)
    (profile.nearest / "icons" / "bad.svg").write_text('<svg viewBox="0 0 1 1"><script>x()</script></svg>')
    page, _ = new_page(profile, "x", "X", None, "slots")
    page.content.write_text('<i data-icon="bad"></i>')
    with pytest.raises(PageError, match="script"):
        build_page(profile, page)


def test_icon_search_finds_by_name_and_tag(home: Path) -> None:
    from pagekit.icons import search_icons

    assert search_icons("circle-check")[0] == "circle-check"
    assert "triangle-alert" in search_icons("alert")
    assert "file-warning" in search_icons("warning")
    assert search_icons("zzzznothing") == []


def test_profile_fonts_are_embedded_before_the_theme(home: Path) -> None:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    (directory / "fonts.css").write_text('@font-face { font-family: "Acme Sans"; }')
    document = make(load_profile(repo)).index.read_text()
    assert document.index('"Acme Sans"') < document.index("--pk-accent")


def test_header_action_icons_are_embedded_in_the_page_script(home: Path) -> None:
    document = make(load_profile()).index.read_text()
    assert 'data-icon="download"' not in document and 'data-icon="layout-grid"' not in document
    assert "viewport-fit=cover" in document
    assert '<i data-icon' not in document


def test_title_is_escaped(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "x", "<script>alert(1)</script>", None, "slots")
    build_page(profile, page)
    assert "<title>&lt;script&gt;" in page.index.read_text()


def test_free_mode_needs_head_and_footer(home: Path) -> None:
    profile = load_profile()
    page = make(profile, slug="free", mode="free")
    assert check_page(profile, page).ok
    page.content.write_text("<html><body>no slots</body></html>")
    with pytest.raises(PageError, match="head"):
        build_page(profile, page)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("<input>", "no name or id"),
        ("<textarea></textarea>", "no name or id"),
        ("<div contenteditable>x</div>", "no name or id"),
        ('<input name="a"><input name="a">', "share the name"),
        ('<script src="https://evil.example/x.js"></script>', "not in allowed_hosts"),
        ('<img src="//evil.example/x.png">', "not in allowed_hosts"),
        ("<style>@import 'https://evil.example/x.css';</style>", "not in allowed_hosts"),
        ('<img src="assets/gone.png">', "missing asset"),
        ("<p>café</p>", "non-ASCII"),
    ],
)
def test_check_catches(home: Path, body: str, message: str) -> None:
    profile = load_profile()
    assert message in errors(profile, make(profile, body=body))


@pytest.mark.parametrize(
    "body",
    [
        NAMED_FORM,
        '<input type="radio" name="r" value="a"><input type="radio" name="r" value="b">',
        '<input type="checkbox" name="c" value="a"><input type="checkbox" name="c" value="b">',
        '<input type="hidden"><button type="button">x</button><input type="submit">',
        '<div contenteditable="false">x</div>',
        '<script src="https://cdn.jsdelivr.net/npm/x@1.0.0/x.js"></script>',
        '<a href="https://example.com/">external links are fine</a>',
    ],
)
def test_check_allows(home: Path, body: str) -> None:
    profile = load_profile()
    assert errors(profile, make(profile, body=body)) == ""


def test_check_flags_unused_assets_and_stale_builds(home: Path) -> None:
    profile = load_profile()
    page = make(profile)
    (page.assets / "orphan.png").write_bytes(b"x")
    assert "unused asset: assets/orphan.png" in errors(profile, page)
    (page.assets / "orphan.png").unlink()
    future = time.time() + 5
    os.utime(page.content, (future, future))
    assert "stale" in errors(profile, page)


def test_wide_fixed_width_is_a_warning_not_an_error(home: Path) -> None:
    profile = load_profile()
    result = check_page(profile, make(profile, body='<div style="width: 1200px">x</div>'))
    assert result.ok and "1200px" in result.warnings[0]


def test_required_footer_is_enforced(home: Path) -> None:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    (directory / "profile.toml").write_text('name = "acme"\nextends = "builtin"\nfooter = "Acme internal"\n')
    profile = load_profile(repo)
    page = make(profile)
    assert "Acme internal" in page.index.read_text()
    page.index.write_text(page.index.read_text().replace("Acme internal", ""))
    assert "required footer" in errors(profile, page)


def test_logo_is_inlined(home: Path) -> None:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    (directory / "logo.svg").write_text("<svg/>")
    page = make(load_profile(repo))
    encoded = base64.b64encode(b"<svg/>").decode()
    assert f"data:image/svg+xml;base64,{encoded}" in page.index.read_text()


def test_header_swaps_to_the_dark_logo_in_dark_mode(home: Path) -> None:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    (directory / "logo.svg").write_text("<svg id='light'/>")
    (directory / "logo-dark.svg").write_text("<svg id='dark'/>")
    document = make(load_profile(repo)).index.read_text()
    dark = base64.b64encode(b"<svg id='dark'/>").decode()
    light = base64.b64encode(b"<svg id='light'/>").decode()
    assert f'media="screen and (prefers-color-scheme: dark)" srcset="data:image/svg+xml;base64,{dark}"' in document
    assert f'class="pk-logo" src="data:image/svg+xml;base64,{light}"' in document


def test_wordmark_joins_the_icon_and_carries_the_brand_name(home: Path) -> None:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    (directory / "logo.svg").write_text("<svg id='icon'/>")
    (directory / "wordmark.svg").write_text("<svg id='word'/>")
    document = make(load_profile(repo)).index.read_text()
    assert base64.b64encode(b"<svg id='word'/>").decode() in document
    assert re.search(r'class="pk-logo" src="[^"]+" alt=""', document)
    assert re.search(r'class="pk-wordmark" src="[^"]+" alt="Acme"', document)


def _profile_in(home: Path, toml: str) -> tuple[Path, Path]:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    directory.mkdir(parents=True)
    (directory / "profile.toml").write_text(f'name = "acme"\nextends = "builtin"\n{toml}\n')
    return repo, directory


def test_builtin_pages_carry_the_pagekit_brand(home: Path) -> None:
    document = make(load_profile()).index.read_text()
    assert 'class="pk-logo"' in document
    assert re.search(r'class="pk-wordmark" src="[^"]+" alt="pagekit"', document)
    assert 'class="pk-logo-print"' in document
    assert '<link rel="icon" href="data:image/svg+xml' in document
    assert "Made with pagekit" in document


def test_a_read_only_profile_hides_the_copy_button_and_comments(home: Path) -> None:
    repo, _ = _profile_in(home, "interactive = false")
    profile = load_profile(repo)
    page = make(profile, body='<span class="pk-id">D-01</span>')
    document = page.index.read_text()
    assert 'id="pk-export" class="pk-button" hidden>' in document
    assert '"readonly": true' in document
    assert not check_page(profile, page).errors


def test_pages_are_interactive_by_default(home: Path) -> None:
    document = make(load_profile()).index.read_text()
    # export.js shows the button once there is something to copy.
    assert 'id="pk-export"' in document and "refreshExportButton" in document
    assert '"readonly"' not in document


def test_contents_tag_lists_headings_and_nests_them_by_level(home: Path) -> None:
    body = '<pk-contents></pk-contents><h2>First part</h2><h3>Detail &amp; more</h3><h2 id="kept">Second</h2><h4>Too deep</h4>'
    document = make(load_profile(), body=body).index.read_text()
    assert '<h2 id="first-part">First part</h2>' in document and '<h3 id="detail-more">' in document
    assert (
        '<ol><li><a href="#first-part">First part</a><ol><li><a href="#detail-more">Detail &amp; more</a></li></ol>'
        '</li><li><a href="#kept">Second</a></li></ol>'
    ) in document
    assert 'href="#too-deep"' not in document and "pk-contents>" not in document


def test_contents_tag_respects_max_level_and_title(home: Path) -> None:
    body = '<pk-contents max-level="2" title="In this report"></pk-contents><h2>One</h2><h3>Two</h3>'
    document = make(load_profile(), body=body).index.read_text()
    assert '<p class="pk-contents-title">In this report</p>' in document
    assert 'href="#one"' in document and 'href="#two"' not in document


def test_contents_tag_can_drop_its_title_and_skip_a_heading(home: Path) -> None:
    body = '<pk-contents title=""></pk-contents><h2>One</h2><h2 data-pk-no-contents>Hidden</h2>'
    document = make(load_profile(), body=body).index.read_text()
    assert "pk-contents-title\">" not in document
    assert 'href="#one"' in document and 'href="#hidden"' not in document


def test_contents_ids_stay_unique_when_headings_repeat(home: Path) -> None:
    document = make(load_profile(), body='<pk-contents></pk-contents><h2>Same</h2><h2>Same</h2>').index.read_text()
    assert 'id="same"' in document and 'id="same-2"' in document


def test_pages_without_tags_get_no_generated_ids(home: Path) -> None:
    assert "<h2>Plain</h2>" in make(load_profile(), body="<h2>Plain</h2>").index.read_text()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ('<pk-contents max-level="9"></pk-contents><h2>A</h2>', "max-level must be a number"),
        ('<pk-contents depth="2"></pk-contents><h2>A</h2>', "no attribute 'depth'"),
        ("<pk-contents></pk-contents>", "no headings"),
        ("<pk-chart></pk-chart>", "unknown tag <pk-chart>"),
        ("<pk-contents>", "malformed"),
    ],
)
def test_a_mistake_in_a_tag_stops_the_build(home: Path, body: str, message: str) -> None:
    with pytest.raises(PageError, match=message):
        make(load_profile(), body=body)


def test_the_default_brand_stays_under_the_weight_limits(home: Path) -> None:
    assert load_profile().brand_warnings() == []


def test_a_heavy_logo_warns_on_build(home: Path) -> None:
    repo, directory = _profile_in(home, "")
    (directory / "logo.svg").write_text("<svg>" + "x" * 60_000 + "</svg>")
    profile = load_profile(repo)
    warnings = check_page(profile, make(profile)).warnings
    assert any("logo.svg adds 78 KB to every page" in w for w in warnings)


def test_banned_wording_fails_with_the_line_and_reason(home: Path) -> None:
    repo, _ = _profile_in(home, '[[banned]]\npattern = "\\\\bTBD\\\\b"\nwhy = "state what is true now"\n')
    profile = load_profile(repo)
    page = make(profile, body="<p>Fine.</p>\n<p>Date is tbd.</p>")
    errors = check_page(profile, page).errors
    assert len(errors) == 1
    assert errors[0].startswith("banned wording 'tbd' on line ") and "of index.html (state what is true now)" in errors[0]


def test_banned_wording_ignores_markup_and_comments_and_can_match_case(home: Path) -> None:
    repo, _ = _profile_in(home, '[[banned]]\npattern = "secret"\ncase_sensitive = true\n')
    profile = load_profile(repo)
    body = '<!-- secret --><p class="secret" title="secret">SECRET</p>'
    assert not check_page(profile, make(profile, body=body)).errors


def test_banned_wording_reads_generated_text_but_not_the_page_chrome(home: Path) -> None:
    repo, _ = _profile_in(home, 'footer = "Prepared by secret"\n[[banned]]\npattern = "secret"\n')
    profile = load_profile(repo)
    assert not check_page(profile, make(profile, body="<p>Fine.</p>")).errors
    errors = check_page(profile, make(profile, body="<pk-contents></pk-contents><h2>Secret</h2>")).errors
    assert errors and all("banned wording" in e for e in errors)


def test_a_bad_banned_pattern_is_reported(home: Path) -> None:
    repo, _ = _profile_in(home, '[[banned]]\npattern = "("\n')
    profile = load_profile(repo)
    assert any("invalid banned pattern" in e for e in check_page(profile, make(profile)).errors)


def test_builtin_pages_embed_their_font(home: Path) -> None:
    document = make(load_profile()).index.read_text()
    assert 'font-family: "IBM Plex Sans";' in document and "data:font/woff2;base64," in document


def test_builtin_pages_embed_their_code_font(home: Path) -> None:
    document = make(load_profile()).index.read_text()
    assert 'font-family: "IBM Plex Mono";' in document and '--pk-mono: "IBM Plex Mono"' in document


def test_a_profile_with_its_own_text_font_keeps_the_builtin_code_font(home: Path) -> None:
    repo, directory = _profile_in(home, "")
    (directory / "fonts.css").write_text('@font-face { font-family: "Mine"; src: url("data:font/woff2;base64,AAAA"); }')
    document = make(load_profile(repo)).index.read_text()
    assert 'font-family: "IBM Plex Mono";' in document


def test_a_profile_that_sets_a_code_font_does_not_carry_the_builtin_one(home: Path) -> None:
    repo, directory = _profile_in(home, "")
    (directory / "theme.css").write_text(":root { --pk-mono: Courier, monospace; }")
    document = make(load_profile(repo)).index.read_text()
    assert 'font-family: "IBM Plex Mono";' not in document
    assert 'font-family: "IBM Plex Sans";' in document


def test_a_profile_with_its_own_font_does_not_carry_the_builtin_font(home: Path) -> None:
    repo, directory = _profile_in(home, "")
    (directory / "fonts.css").write_text('@font-face { font-family: "Mine"; src: url("data:font/woff2;base64,AAAA"); }')
    document = make(load_profile(repo)).index.read_text()
    assert 'font-family: "Mine"' in document
    assert 'font-family: "IBM Plex Sans";' not in document


def test_a_profile_that_sets_a_system_font_does_not_carry_the_builtin_font(home: Path) -> None:
    repo, directory = _profile_in(home, "")
    (directory / "theme.css").write_text(":root { --pk-font: Georgia, serif; }")
    assert 'font-family: "IBM Plex Sans";' not in make(load_profile(repo)).index.read_text()


def test_a_profile_that_only_changes_colors_keeps_the_builtin_font(home: Path) -> None:
    repo, directory = _profile_in(home, "")
    (directory / "theme.css").write_text(":root { --pk-accent: #123456; }")
    assert 'font-family: "IBM Plex Sans";' in make(load_profile(repo)).index.read_text()


def test_a_profile_with_its_own_brand_inherits_no_pagekit_logo(home: Path) -> None:
    repo, _ = _profile_in(home, 'brand = "Acme"')
    document = make(load_profile(repo)).index.read_text()
    for marker in ('class="pk-logo"', 'class="pk-wordmark"', 'class="pk-logo-print"', 'rel="icon"'):
        assert marker not in document
    assert '<span class="pk-brand">Acme</span>' in document


def test_a_profile_that_only_restyles_keeps_the_pagekit_logo(home: Path) -> None:
    repo, directory = _profile_in(home, "")
    (directory / "theme.css").write_text(":root { --pk-accent: #123456; }")
    document = make(load_profile(repo)).index.read_text()
    assert 'class="pk-wordmark"' in document
    assert "--pk-accent: #123456" in document


def test_a_profile_logo_replaces_the_whole_pagekit_set(home: Path) -> None:
    repo, directory = _profile_in(home, "")
    (directory / "logo.svg").write_text("<svg id='mine'/>")
    document = make(load_profile(repo)).index.read_text()
    mine = base64.b64encode(b"<svg id='mine'/>").decode()
    assert f'class="pk-logo" src="data:image/svg+xml;base64,{mine}"' in document
    assert f'<link rel="icon" href="data:image/svg+xml;base64,{mine}">' in document
    assert 'class="pk-wordmark"' not in document
    assert 'class="pk-logo-print"' not in document


def test_an_empty_brand_shows_no_name_or_logo(home: Path) -> None:
    repo, _ = _profile_in(home, 'brand = ""')
    document = make(load_profile(repo)).index.read_text()
    assert 'class="pk-logo"' not in document
    assert '<span class="pk-brand"></span>' in document


def test_print_logo_is_added_only_when_the_profile_has_one(home: Path) -> None:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    (directory / "logo.svg").write_text("<svg/>")
    profile = load_profile(repo)
    assert 'class="pk-logo-print"' not in make(profile).index.read_text()
    (directory / "logo-print.png").write_bytes(b"png")
    assert 'class="pk-logo-print" src="data:image/png;base64,cG5n"' in make(profile).index.read_text()


def test_pack_inlines_assets(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "shot", "Shot", None, "slots")
    (page.assets / "a b.png").write_bytes(b"png")
    page.content.write_text('<img src="assets/a%20b.png"><div style="background:url(assets/a%20b.png)"></div>')
    build_page(profile, page)
    assert check_page(profile, page).ok  # an encoded name still counts as used
    document = pack_page(page).read_text()
    assert "assets/" not in document.split("</style>")[-1].split("<script>")[0]
    assert document.count("base64,cG5n") == 2


def test_pack_inlines_a_stylesheet_url(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "css", "Css", None, "slots")
    (page.assets / "bg.png").write_bytes(b"png")
    page.content.write_text('<style>.x{background:url("assets/bg.png")}</style>')
    build_page(profile, page)
    assert check_page(profile, page).ok
    assert 'url("data:image/png;base64,cG5n")' in pack_page(page).read_text()


def test_pack_refuses_a_stale_build(home: Path) -> None:
    page = make(load_profile())
    future = time.time() + 5
    os.utime(page.content, (future, future))
    with pytest.raises(PageError, match="stale"):
        pack_page(page)


def test_prune_removes_only_old_unpinned_pages(home: Path) -> None:
    profile = load_profile()
    old, recent, pinned = (make(profile, slug=s) for s in ("old", "recent", "pinned"))
    age(old, 31)
    age(recent, 29)
    age(pinned, 400)
    pinned.meta["pinned"] = True
    pinned.write_meta()

    assert prune_pages(dry_run=True) == [old.dir]
    assert old.dir.exists()
    assert prune_pages() == [old.dir]
    assert not old.dir.exists() and recent.dir.exists() and pinned.dir.exists()


def test_prune_never_touches_folders_it_did_not_create(home: Path) -> None:
    profile = load_profile()
    page = make(profile)
    age(page, 400)
    stray = pages_root() / "default" / "not-a-page"
    stray.mkdir()
    saved = pages_root() / "saved"
    saved.mkdir()
    (saved / "keep.html").write_text("x")
    assert prune_pages() == [page.dir]
    assert stray.exists() and (saved / "keep.html").exists()


@pytest.mark.posix
def test_prune_follows_no_symlinks(home: Path) -> None:
    target = home / "precious"
    target.mkdir()
    (target / "page.toml").write_text('slug = "x"\nprofile = "default"\nupdated = "2000-01-01T00:00:00Z"\n')
    (pages_root() / "default").mkdir(parents=True)
    (pages_root() / "default" / "link").symlink_to(target)
    assert prune_pages() == []
    assert target.exists()


def test_ttl_zero_disables_prune(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAGEKIT_TTL_DAYS", "0")
    page = make(load_profile())
    age(page, 400)
    assert prune_pages() == []


def test_prune_if_due_runs_once_within_the_throttle(home: Path) -> None:
    profile = load_profile()
    first = make(profile, slug="first")
    age(first, 31)
    prune_if_due()
    assert not first.dir.exists()
    second = make(profile, slug="second")
    age(second, 31)
    prune_if_due()
    assert second.dir.exists()


def test_save_defaults_to_the_saved_folder_with_no_next_step(home: Path) -> None:
    profile = load_profile()
    page = make(profile)
    result = save_page(profile, page)
    assert result.path == pages_root() / "saved" / "demo.html"
    assert result.instructions == ""
    assert load_page(profile, "demo").meta["pinned"] is True
    age(page, 400)
    assert prune_pages() == []
    assert result.path.exists()


@pytest.mark.posix
def test_save_follows_the_profile_and_prints_its_next_step(home: Path) -> None:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    target = home / "notes"
    script = home / "where"
    script.write_text(f"#!/bin/sh\necho {target}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    (directory / "profile.toml").write_text(
        f'name = "acme"\nextends = "builtin"\n[save]\nroot_command = "{script}"\nsubdir = "Attachments/Pages"\n'
    )
    (directory / "SAVE.md").write_text("Link {{file}} for {{title}} at {{url}}.")
    profile = load_profile(repo)
    page = make(profile)

    result = save_page(profile, page)

    assert result.path == target / "Attachments" / "Pages" / "demo.html"
    assert result.path.read_text().startswith("<!doctype html>")
    assert result.instructions == "Link demo.html for Demo at http://localhost:8766/p/acme/demo/."


def test_save_refuses_a_failing_page(home: Path) -> None:
    profile = load_profile()
    page = make(profile, body="<input>")
    with pytest.raises(PageError, match="no name"):
        save_page(profile, page)
    assert not load_page(profile, "demo").meta["pinned"]


def test_save_updates_its_own_copy_but_never_another_file(home: Path) -> None:
    profile = load_profile()
    page = make(profile)
    first = save_page(profile, page)
    page.content.write_text("<p>Second</p>")
    build_page(profile, page)
    assert "Second" in save_page(profile, page).path.read_text()

    first.path.write_text("someone else's file")
    with pytest.raises(PageError, match="different page"):
        save_page(profile, page)
    assert first.path.read_text() == "someone else's file"


def test_profile_component_css_reaches_only_the_pages_that_use_it(home: Path) -> None:
    directory = home / ".pagekit" / "profile"
    init_profile(directory, "personal", "builtin", "Me")
    (directory / "components").mkdir()
    (directory / "components" / "notice.html").write_text('<!-- A notice. --><div class="notice">Hi</div>')
    (directory / "components" / "notice.css").write_text(".notice { color: var(--pk-accent); }")
    profile = load_profile()
    used = make(profile, slug="uses", body='<div class="notice">Hi</div>')
    assert ".notice { color" in used.index.read_text()
    assert "notice" not in " ".join(check_page(profile, used).warnings)
    unused = make(profile, slug="plain", body="<p>Hi</p>")
    assert ".notice { color" not in unused.index.read_text()


def test_check_command_can_point_into_its_profile(home: Path) -> None:
    directory = home / "work" / "repo" / ".pagekit" / "profile"
    init_profile(directory, "repo", "builtin", "Acme")
    (directory / "checks").mkdir()
    script = directory / "checks" / "lint.py"
    script.write_text('import sys\nprint("checked " + sys.argv[0])\nsys.exit(1)\n')
    (directory / "profile.toml").write_text(
        'name = "repo"\nextends = "builtin"\n[checks]\ncommand = ["python3", "{profile}/checks/lint.py"]\n'
    )
    profile = load_profile(directory.parent.parent)
    page = make(profile)
    assert f"checked {script.resolve()}" in errors(profile, page)

