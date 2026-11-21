"""Build a GitHub profile from public account data and a local configuration."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
from io import BytesIO
import json
import os
from pathlib import Path
import re
import tempfile
import textwrap
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
THEMES = {
    "dark": {
        "background": "#0d1117", "surface": "#161b22", "border": "#30363d",
        "text": "#e6edf3", "muted": "#9da7b3", "key": "#ffa657",
        "value": "#a5d6ff", "art": "#8bd5ca", "accent": "#3fb950",
    },
    "light": {
        "background": "#ffffff", "surface": "#f6f8fa", "border": "#d0d7de",
        "text": "#1f2328", "muted": "#59636e", "key": "#953800",
        "value": "#0550ae", "art": "#176b63", "accent": "#116329",
    },
}


def download(url, token=""):
    headers = {"User-Agent": "github-terminal-profile", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                return response.read()
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f"GitHub request failed with HTTP {error.code}") from None
        except (URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError("GitHub could not be reached after three attempts") from None
        time.sleep(2 ** attempt)


def public_snapshot(username):
    token = os.environ.get("GITHUB_TOKEN", "")
    user = json.loads(download(f"https://api.github.com/users/{username}", token))
    repositories = []
    page = 1
    while True:
        batch = json.loads(download(
            f"https://api.github.com/users/{username}/repos?type=owner&per_page=100&page={page}",
            token,
        ))
        repositories.extend(repo for repo in batch if not repo.get("private", True))
        if len(batch) < 100:
            break
        page += 1
    owned = [repo for repo in repositories if not repo["fork"]]
    language_counts = Counter(repo["language"] for repo in owned if repo.get("language"))
    return {
        "username": user["login"],
        "created_at": user["created_at"],
        "avatar_url": user["avatar_url"],
        "public_repos": len(repositories),
        "original_repos": len(owned),
        "stars": sum(repo["stargazers_count"] for repo in owned),
        "forks": sum(repo["forks_count"] for repo in owned),
        "followers": user["followers"],
        "languages": [name for name, _ in language_counts.most_common(4)],
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def ascii_portrait(image_bytes):
    with Image.open(BytesIO(image_bytes)) as source:
        square = ImageOps.fit(source.convert("RGB"), (460, 460), Image.Resampling.LANCZOS)
        portrait = square.resize((46, 27), Image.Resampling.LANCZOS)
    grey = ImageOps.autocontrast(ImageOps.grayscale(portrait))
    background = portrait.getpixel((0, 0))
    ramp = "@%#*+=-:. "
    lines = []
    for y in range(portrait.height):
        characters = []
        for x in range(portrait.width):
            pixel = portrait.getpixel((x, y))
            distance = sum((channel - bg) ** 2 for channel, bg in zip(pixel, background)) ** 0.5
            character = ramp[grey.getpixel((x, y)) * (len(ramp) - 1) // 255]
            characters.append(" " if distance < 58 else character)
        lines.append("".join(characters))
    return lines


def svg_profile(config, snapshot, portrait, theme_name, compact):
    palette = THEMES[theme_name]
    width = 360 if compact else 1000
    elements = []

    def text(x, y, value, color="text", size=15, extra=""):
        elements.append(
            f'<text x="{x}" y="{y}" fill="{palette[color]}" font-size="{size}" {extra}>'
            f'{escape(str(value))}</text>'
        )

    def section(y, title):
        text(content_x, y, title, "muted", 12, 'letter-spacing="1.6"')
        line_start = content_x + len(title) * 8 + 16
        elements.append(f'<path d="M {line_start} {y - 4} H {width - 28}" stroke="{palette["border"]}"/>')
        return y + 28

    def field(y, label, value):
        value_x = content_x + (98 if compact else 126)
        text(content_x, y, label, "key", 14 if compact else 15)
        lines = textwrap.wrap(str(value), width=23 if compact else 55, break_long_words=True) or [""]
        for index, line in enumerate(lines):
            text(value_x, y + index * 21, line, "value", 14 if compact else 15)
        return y + 25 + (len(lines) - 1) * 21

    for index, color in enumerate(("key", "muted", "accent")):
        elements.append(f'<circle cx="{26 + index * 17}" cy="27" r="4" fill="{palette[color]}"/>')
    text(88, 32, f'~/{config["username"]}/README.md', "muted", 12)
    elements.append(f'<path d="M 0 54 H {width}" stroke="{palette["border"]}"/>')

    art_size = 9.1 if compact else 10.7
    art_line_height = 10 if compact else 13.2
    art_x = 54 if compact else 26
    art_y = 86 if compact else 142
    elements.append(f'<g aria-label="ASCII portrait" font-size="{art_size}" fill="{palette["art"]}" xml:space="preserve" style="white-space:pre">')
    for index, line in enumerate(portrait):
        elements.append(f'<text x="{art_x}" y="{art_y + index * art_line_height:.1f}" style="white-space:pre">{escape(line)}</text>')
    elements.append("</g>")

    content_x = 22 if compact else 356
    title_y = 396 if compact else 101
    text(content_x, title_y, f'{config["username"]}@github', "text", 23)
    tagline_lines = textwrap.wrap(config["tagline"], width=36 if compact else 62)
    for index, line in enumerate(tagline_lines):
        text(content_x, title_y + 26 + index * 19, line, "muted", 13)
    y = section(title_y + 66 + (len(tagline_lines) - 1) * 19, "PROFILE")
    for label, value in config["fields"]:
        y = field(y, label, value)
    created_at = datetime.fromisoformat(snapshot["created_at"].replace("Z", "+00:00"))
    updated_at = datetime.fromisoformat(snapshot["updated_at"].replace("Z", "+00:00"))
    days = max(0, (updated_at - created_at).days)
    y = field(y, "Uptime", f'{days:,} days on GitHub')
    y = section(y + 16, "TOOLBOX")
    y = field(y, "Languages", " / ".join(snapshot["languages"]) or "Exploring")
    y = section(y + 16, "PUBLIC GITHUB STATS")
    for label, value in (
        ("Repos", snapshot["public_repos"]),
        ("Originals", snapshot["original_repos"]),
        ("Stars", snapshot["stars"]),
        ("Followers", snapshot["followers"]),
    ):
        y = field(y, label, f"{value:,}")
    height = y + 69
    if not compact:
        text(28, height - 95, "$ explore --build --share", "art", 12)
        text(28, height - 71, "curiosity / experiments / notes", "muted", 11)
    footer_y = height - 45
    elements.append(f'<path d="M 22 {footer_y} H {width - 22}" stroke="{palette["border"]}"/>')
    stamp = updated_at.strftime("%Y-%m-%d %H:%M UTC")
    text(22, height - 21, f"synced {stamp}", "muted", 10.5 if compact else 11)
    if not compact:
        text(width - 206, height - 21, "public data / daily refresh", "muted", 11)
    title = escape(f'{config["username"]} — terminal profile')
    description = escape(
        f'{config["intro"]} Public repositories {snapshot["public_repos"]}, '
        f'original repositories {snapshot["original_repos"]}, stars {snapshot["stars"]}, '
        f'followers {snapshot["followers"]}. Last synchronized {stamp}.'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">\n'
        f'<title id="title">{title}</title><desc id="description">{description}</desc>\n'
        f'<rect width="{width}" height="{height}" rx="14" fill="{palette["background"]}"/>\n'
        f'<path d="M 14 0 H {width - 14} Q {width} 0 {width} 14 V 54 H 0 V 14 Q 0 0 14 0" '
        f'fill="{palette["surface"]}"/>\n'
        '<g font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" '
        'font-weight="400">\n' + "\n".join(elements) + '\n</g>\n</svg>\n'
    )


def readme(config):
    username = config["username"]
    lines = [
        f'<!-- Generated from profile.json by scripts/update_profile.py. -->',
        '<picture>',
        '  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="assets/profile-compact-dark.svg">',
        '  <source media="(max-width: 600px)" srcset="assets/profile-compact-light.svg">',
        '  <source media="(prefers-color-scheme: dark)" srcset="assets/profile-dark.svg">',
        f'  <img alt="{escape(username)} 的终端风格个人主页，展示兴趣、公开仓库语言与 GitHub 统计" src="assets/profile-light.svg" width="1000">',
        '</picture>',
        '',
        config["intro"],
        '',
        f'[探索我的项目]({config["homepage"]}) · [所有公开仓库](https://github.com/{username}?tab=repositories)',
        '',
    ]
    for project in config["projects"]:
        lines.append(f'- [{project["name"]}]({project["url"]}) — {project["description"]}')
    lines.extend([
        '',
        '<sub>统计按日更新。Repos 为公开仓库数，Originals 为其中非 fork 仓库数，Stars 为这些非 fork 仓库获得的星标。Languages 按公开非 fork 仓库的主语言出现次数排序。</sub>',
        '',
        '<!-- Visual concept inspired by https://github.com/Andrew6rant/Andrew6rant. Implementation and artwork generated for this account. -->',
        '',
    ])
    return "\n".join(lines)


def atomic_write(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(contents)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Render using the saved public snapshot and avatar")
    args = parser.parse_args()
    config = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    username = config["username"]
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", username):
        raise ValueError("profile.json contains an invalid GitHub username")
    if args.offline:
        snapshot = json.loads((ASSETS / "public-data.json").read_text(encoding="utf-8"))
        image_bytes = (ASSETS / "avatar.png").read_bytes()
    else:
        snapshot = public_snapshot(username)
        image_bytes = download(snapshot["avatar_url"])
    if snapshot["username"].lower() != username.lower():
        raise ValueError("Saved account data does not match profile.json")
    portrait = ascii_portrait(image_bytes)
    outputs = {ROOT / "README.md": readme(config).encode("utf-8")}
    for theme in THEMES:
        for compact in (False, True):
            name = f'profile-{"compact-" if compact else ""}{theme}.svg'
            outputs[ASSETS / name] = svg_profile(config, snapshot, portrait, theme, compact).encode("utf-8")
    outputs[ASSETS / "avatar.png"] = image_bytes
    outputs[ASSETS / "public-data.json"] = (json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    for path, contents in outputs.items():
        atomic_write(path, contents)
    print(f'Updated {username}: {snapshot["public_repos"]} public repositories, {snapshot["followers"]} followers')


if __name__ == "__main__":
    main()
