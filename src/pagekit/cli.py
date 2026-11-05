"""pagekit command line. Every command works with the server down."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .fonts import FontError, add_font
from .icons import search_icons
from .library import ComponentError, add_component, find_component, list_components
from .pages import (
    DEFAULT_PORT,
    CheckResult,
    PHONE_WIDTH_PX,
    Page,
    PageError,
    build_page,
    check_page,
    iter_pages,
    list_saved,
    load_page,
    new_page,
    pack_page,
    pages_root,
    prune_if_due,
    prune_pages,
    save_page,
    send_page,
    server_running,
    set_public_url,
)
from .pdf import render_pdf
from .update import UpdateError, check, installed_version, resolve_follow, update, update_settings_file
from .profiles import (
    EXTRA_PROFILES_SUBDIR,
    PROFILE_SUBDIR,
    Profile,
    ProfileError,
    init_profile,
    load_profile,
    local_profile_dir,
    personal_dir,
    projects_file,
    register_project,
    repo_profiles,
)


def _profile(args) -> Profile:
    return load_profile(override=getattr(args, "profile", None))


def _print_profile(profile: Profile) -> None:
    print(f"profile: {profile.name}")
    if profile.config.get("when"):
        print(f"when: {profile.config['when']}")
    print(f"folder: {profile.nearest}")
    print("layers: " + " > ".join(str(d) for d in profile.dirs[: len(profile.dirs) - len(profile.overrides)]))
    if profile.overrides:
        print("overrides: " + " > ".join(str(d) for d in profile.overrides))
    _print_other_profiles(profile)
    print("theme tokens: " + ", ".join(profile.tokens()))
    print("components (pagekit component show NAME):")
    for component in list_components(profile):
        print(f"  {component.name}: {component.when}")
    instructions = profile.instructions()
    if instructions:
        print("\n--- profile instructions ---")
        print(instructions)
        print("--- end instructions ---")


def _print_other_profiles(profile: Profile) -> None:
    offered = {name: load_profile(override=str(path), overrides=False) for name, path in repo_profiles().items()}
    # A profile others build on, with no guidance of its own, is a shared base rather than a choice.
    bases = {layer for other in offered.values() for layer in other.dirs[:-1]}
    others = {
        name: other
        for name, other in offered.items()
        if name != profile.name and (other.config.get("when") or other.dirs[-1] not in bases)
    }
    if not others:
        return
    print("other profiles here (choose by when to use each, then add --profile NAME to every command for the page):")
    for name, other in others.items():
        print(f"  {name}: {other.config.get('when') or 'no guidance yet: add when to its profile.toml'}")


def _print_location(page: Page) -> None:
    print(f"file: {page.index}")
    if server_running():
        print(f"url: {page.url()}")
    else:
        print(f"url: {page.url()} (server not running: pagekit serve, or share with pagekit send)")


def _report_check(profile: Profile, page: Page) -> int:
    return _print_check(check_page(profile, page))


def _print_check(result: CheckResult) -> int:
    for error in result.errors:
        print(f"error: {error}")
    for warning in result.warnings:
        print(f"warning: {warning}")
    if result.ok:
        print(f"check: ok (phone width needs a browser: scrollWidth at {PHONE_WIDTH_PX}px)")
        return 0
    print(f"check: {len(result.errors)} error(s)")
    return 1


def cmd_new(args) -> int:
    prune_if_due()
    profile = _profile(args)
    page, created = new_page(profile, args.slug, args.title, args.summary, args.mode)
    print(("created" if created else "exists, updating in place") + f": {page.dir}")
    print(f"write: {page.content}")
    print(f"assets: {page.assets}")
    print(f"then: pagekit build {page.slug}")
    _print_profile(profile)
    return 0


def cmd_build(args) -> int:
    prune_if_due()
    profile = _profile(args)
    page = load_page(profile, args.slug)
    previous = page.index.read_bytes() if page.index.is_file() else None
    build_page(profile, page)
    result = check_page(profile, page)
    if result.hook_failed:
        # A page the profile refuses never becomes the live version.
        if previous is None:
            page.index.unlink()
        else:
            page.index.write_bytes(previous)
        _print_check(result)
        print("not updated: the profile's check refused this build")
        return 1
    _print_location(page)
    return _print_check(result)


def cmd_check(args) -> int:
    profile = _profile(args)
    return _report_check(profile, load_page(profile, args.slug))


def cmd_pack(args) -> int:
    print(pack_page(load_page(_profile(args), args.slug)))
    return 0


def cmd_send(args) -> int:
    profile = _profile(args)
    print(send_page(profile, load_page(profile, args.slug)))
    return 0


def cmd_pdf(args) -> int:
    page = load_page(_profile(args), args.slug)
    target = Path(args.out).expanduser() if args.out else page.dir / f"{page.slug}.pdf"
    print(render_pdf(page, target))
    return 0


def cmd_save(args) -> int:
    profile = _profile(args)
    page = load_page(profile, args.slug)
    result = save_page(profile, page)
    print(f"saved: {result.path}")
    print(f"pinned: {page.dir}")
    if result.instructions:
        print("\n--- required next step ---")
        print(result.instructions)
        print("--- end ---")
    return 0


def cmd_component_list(args) -> int:
    components = list_components(_profile(args))
    if args.json:
        rows = [{"name": c.name, "source": c.source, "when": c.when, "path": str(c.html)} for c in components]
        print(json.dumps(rows, indent=2))
        return 0
    for component in components:
        print(f"{component.name} [{component.source}]: {component.when}")
    return 0


def cmd_component_show(args) -> int:
    component = find_component(_profile(args), args.name)
    print(component.html.read_text(encoding="utf-8").rstrip())
    if component.css:
        print(f"\n/* {component.css} (added to pages automatically) */")
        print(component.css.read_text(encoding="utf-8").rstrip())
    return 0


def cmd_component_add(args) -> int:
    target = add_component(_profile(args), args.name, args.when, Path(args.source).expanduser(), args.update)
    print(f"saved: {target}")
    return 0


def cmd_icons(args) -> int:
    matches = search_icons(" ".join(args.query), _profile(args))
    if not matches:
        print("no matching icons: try a broader word")
        return 1
    print("\n".join(matches))
    print('\nuse in a page: <i data-icon="NAME"></i>')
    return 0


def cmd_ls(args) -> int:
    entries = [p.to_json() for p in iter_pages()] + list_saved()
    if args.json:
        print(json.dumps(entries, indent=2))
        return 0
    if not entries:
        print(f"no pages under {pages_root()}")
    for entry in entries:
        if entry["expires"]:
            state = "expires " + datetime.fromtimestamp(entry["expires"]).strftime("%m/%d/%Y")
        else:
            state = "kept"
        print(f"{entry['profile']}/{entry['slug']}  {state}  {entry['title']}  {entry['path']}")
    return 0


def cmd_prune(args) -> int:
    for path in prune_pages(args.older_than_days, args.dry_run):
        print(("would remove " if args.dry_run else "removed ") + str(path))
    return 0


def cmd_profile(args) -> int:
    profile = _profile(args)
    _print_profile(profile)
    weights = profile.brand_weights()
    if weights:
        print("\nbrand data on every page:")
        for name, size in weights:
            print(f"  {name}: {size / 1024:.0f} KB")
        print(f"  total: {sum(size for _, size in weights) / 1024:.0f} KB")
    for warning in profile.brand_warnings():
        print(f"warning: {warning}")
    return 0


def cmd_font_add(args) -> int:
    profile = _profile(args)
    target = add_font(profile, Path(args.file), args.family, args.weight, args.italic)
    print(f"added {args.family} {args.weight} to {target}")
    print(f'then set --pk-font: "{args.family}", sans-serif; in {profile.nearest / "theme.css"}')
    return 0


def _default_profile_name() -> str:
    return re.sub(r"[^a-z0-9]+", "-", Path.cwd().name.lower()).strip("-")


def cmd_init(args) -> int:
    name = args.name or ("personal" if args.personal else _default_profile_name())
    if args.personal:
        directory = personal_dir()
        extends = "builtin"
    elif args.local:
        directory = local_profile_dir(name)
        extends = args.extends
    elif args.also:
        if not args.name:
            print("error: --also needs --name", file=sys.stderr)
            return 1
        directory = Path.cwd() / EXTRA_PROFILES_SUBDIR / name
        extends = args.extends
    else:
        directory = Path.cwd() / PROFILE_SUBDIR
        extends = args.extends
    for path in init_profile(directory, name, extends, args.brand or "", args.when or ""):
        print(f"wrote {path}")
    if args.local:
        register_project(Path.cwd(), directory)
        print(f"mapped {Path.cwd()} to {directory} in {projects_file()}")
    return 0


def cmd_serve(args) -> int:
    from .server import make_server, start_pruner

    start_pruner()
    server = make_server(args.host, args.port)
    print(f"pagekit on http://{args.host}:{args.port} (pages in {pages_root()})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


_UNIT = """[Unit]
Description=pagekit local page server

[Service]
ExecStart={python} -m pagekit serve --port {port}
Restart=on-failure

[Install]
WantedBy=default.target
"""


def cmd_update(args) -> int:
    try:
        follow, source = resolve_follow(args.follow)
        if follow == "main":
            print("following main" + (f", as set in {update_settings_file()}" if source == "file" else ""))
        if args.check:
            pending = check(follow=follow)
            for commit in pending.commits:
                print(f"  {commit}")
            if pending.commits:
                print(f"{len(pending.commits)} update(s) available ({pending.current} -> {pending.target}): run pagekit update")
            else:
                print(f"pagekit {pending.current} is up to date")
            return 0
        result = update(follow=follow)
    except UpdateError as exc:
        print(f"pagekit: {exc}", file=sys.stderr)
        return 1
    if not result.commits:
        print(f"pagekit {result.after} is up to date")
        return 0
    print(f"updated pagekit {result.before} -> {result.after} with {len(result.commits)} change(s):")
    for commit in result.commits:
        print(f"  {commit}")
    if result.reinstalled:
        print("reinstalled, because its dependencies changed")
    for skill in result.new_skills:
        print(f"new skill, link it for your agent: {skill}")
    if result.server == "restarted":
        print("restarted the server")
    elif result.server:
        print("the server is still running the old version: restart it")
    print("pages already built keep their old look until you run pagekit build SLUG")
    return 0


def cmd_install_service(args) -> int:
    if not shutil.which("systemctl"):
        raise PageError("install-service needs systemd: use pagekit serve, or start it at login (see docs/serving.md)")
    if args.public_url:
        set_public_url(args.public_url)
    unit = Path.home() / ".config" / "systemd" / "user" / "pagekit.service"
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text(_UNIT.format(python=sys.executable, port=args.port), encoding="utf-8")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", "pagekit.service"], check=True)
    subprocess.run(["systemctl", "--user", "restart", "pagekit.service"], check=True)
    print(f"installed {unit}; serving on http://localhost:{args.port}")
    return 0


class _ShowVersion(argparse.Action):
    """--version. It asks git only when it is used, since every other command would pay for the call."""

    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, default=argparse.SUPPRESS, help="show the version and exit")

    def __call__(self, parser, namespace, values, option_string=None):
        print(f"pagekit {installed_version()}")
        parser.exit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pagekit", description=__doc__)
    parser.add_argument("--version", action=_ShowVersion)
    sub = parser.add_subparsers(dest="cmd", required=True)
    profile_help = "personal, builtin, a profile this repo offers, or a directory (default: nearest to the working directory)"

    def page_command(name: str, fn, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("slug")
        p.add_argument("--profile", help=profile_help)
        p.set_defaults(fn=fn)
        return p

    p = page_command("new", cmd_new, "create a page, or reopen it to update in place, and print the house rules")
    p.add_argument("--title")
    p.add_argument("--summary")
    p.add_argument("--mode", choices=("slots", "free"), default="slots")
    page_command("build", cmd_build, "compose index.html and run the checks")
    page_command("check", cmd_check, "run the checks only")
    page_command("pack", cmd_pack, "write one self-contained HTML file and print its path")
    page_command("send", cmd_send, "pack the page and run the profile's send command on it")
    p = page_command("pdf", cmd_pdf, "write a bookmarked, tagged PDF with headless Chromium")
    p.add_argument("--out", help="where to write it (default: beside the page)")
    page_command("save", cmd_save, "keep the page: copy it to the profile's save location and pin the working copy")

    p = sub.add_parser("ls", help="list pages, newest first")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_ls)

    p = sub.add_parser("prune", help="delete unpinned pages past the TTL (default 30 days)")
    p.add_argument("--older-than-days", type=float)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_prune)

    p = sub.add_parser("profile", help="print the resolved profile and its instructions")
    p.add_argument("--profile", help=profile_help)
    p.set_defaults(fn=cmd_profile)

    p = sub.add_parser("init", help="scaffold a profile in .pagekit/profile here, or ~/.pagekit/profile with --personal")
    p.add_argument("--name", help="default: this folder's name, or personal with --personal")
    p.add_argument("--brand", help="name to show in the header and footer, replacing the pagekit logo (default: keep it)")
    p.add_argument("--extends", default="builtin", help="the profile to build on: builtin, personal, or a path")
    p.add_argument("--when", help="when to use this profile, shown to agents choosing between profiles")
    p.add_argument("--also", action="store_true", help="another profile for this repo, in .pagekit/profiles/NAME")
    p.add_argument("--personal", action="store_true")
    p.add_argument("--local", action="store_true", help="private profile for this folder: kept under ~/.pagekit, nothing added to the project")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("component", help="list, show, or save reusable components")
    component = p.add_subparsers(dest="component_cmd", required=True)
    q = component.add_parser("list", help="core, profile, and library components with when to use each")
    q.add_argument("--json", action="store_true")
    q.add_argument("--profile", help=profile_help)
    q.set_defaults(fn=cmd_component_list)
    q = component.add_parser("show", help="print a component's markup and styles")
    q.add_argument("name")
    q.add_argument("--profile", help=profile_help)
    q.set_defaults(fn=cmd_component_show)
    q = component.add_parser("add", help="save a new component to the library")
    q.add_argument("name")
    q.add_argument("--when", required=True, help="one line on when to use it")
    q.add_argument("--from", dest="source", required=True, help="folder with component.html and optional component.css")
    q.add_argument("--update", action="store_true", help="replace the library's copy, for every page on its next build")
    q.add_argument("--profile", help=profile_help)
    q.set_defaults(fn=cmd_component_add)

    p = sub.add_parser("font", help="embed a font in the profile")
    font = p.add_subparsers(dest="font_cmd", required=True)
    q = font.add_parser("add", help="add one static font file, one weight at a time, to the profile's fonts.css")
    q.add_argument("file")
    q.add_argument("--family", required=True, help='the name to use in CSS, such as "Acme Sans"')
    q.add_argument("--weight", type=int, default=400)
    q.add_argument("--italic", action="store_true")
    q.add_argument("--profile", help=profile_help)
    q.set_defaults(fn=cmd_font_add)

    p = sub.add_parser("icons", help="search the Lucide icons by name or tag")
    p.add_argument("query", nargs="+")
    p.add_argument("--profile", help=profile_help)
    p.set_defaults(fn=cmd_icons)

    p = sub.add_parser("update", help="update pagekit to the newest release, and restart the server if needed")
    p.add_argument("--check", action="store_true", help="list what an update would bring in, and change nothing")
    follow = p.add_mutually_exclusive_group()
    follow.add_argument("--main", dest="follow", action="store_const", const="main",
                        help="follow the main branch, whatever ~/.pagekit/update.toml says")
    follow.add_argument("--releases", dest="follow", action="store_const", const="releases",
                        help="follow the newest release, whatever ~/.pagekit/update.toml says")
    p.set_defaults(fn=cmd_update)

    p = sub.add_parser("serve", help="run the optional page index")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.set_defaults(fn=cmd_serve)

    p = sub.add_parser("install-service", help="install and start a systemd user service")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--public-url", help="also accept this private https address, such as a tailscale serve name")
    p.set_defaults(fn=cmd_install_service)
    return parser


def main(argv: list[str] | None = None) -> int:
    # A Windows console defaults to a legacy code page, which cannot print every character in a page's rules.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except (PageError, ProfileError, ComponentError, FontError) as exc:
        print(f"pagekit: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
