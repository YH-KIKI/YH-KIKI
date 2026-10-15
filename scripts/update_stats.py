"""Refresh public GitHub cards. Keep the previous cards if any request fails."""
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from html import escape
import math
import os
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
OWNER = os.environ.get('PROFILE_OWNER', 'YH-KIKI')
CARDS = ('profile-details', 'most-commit-language')


def language_breakdown(data):
    """Read shares from the existing donut so both cards use the same basis."""
    root = ET.fromstring(data)
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    labels = [node.text for node in root.findall('.//svg:text', ns)][1:]
    arcs = [node for node in root.findall('.//svg:g', ns) if node.get('class') == 'arc']
    if not labels or len(labels) != len(arcs):
        raise ValueError('Language labels and chart segments do not match')
    values = []
    number = r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'
    for label, arc in zip(labels, arcs):
        path = arc.find('svg:path', ns)
        commands = re.findall(r'[MALZ]|' + number, path.get('d'))
        if commands[0] != 'M':
            raise ValueError('Unexpected donut path')
        x, y = float(commands[1]), float(commands[2])
        angle = math.atan2(y, x)
        total = 0.0
        i = 3
        while i < len(commands) and commands[i] == 'A':
            args = [float(n) for n in commands[i + 1:i + 8]]
            end_angle = math.atan2(args[6], args[5])
            sweep = args[4]
            delta = ((end_angle - angle) if sweep else (angle - end_angle)) % math.tau
            total += delta
            angle = end_angle
            i += 8
        if total <= 0:
            raise ValueError('Empty language segment')
        color = re.search(r'fill:\s*(#[0-9a-fA-F]{3,8})', path.get('style', ''))
        if color is None:
            raise ValueError('Language segment color missing')
        values.append({'name': label, 'angle': total, 'color': color.group(1)})
    angle_sum = sum(item['angle'] for item in values)
    if not math.isclose(angle_sum, math.tau, abs_tol=1e-7):
        raise ValueError('Language donut does not cover a full circle')
    # Round to tenths with a 100.0% total, including close fractional ties.
    tenths = [item['angle'] / angle_sum * 1000 for item in values]
    rounded = [math.floor(value + 1e-9) for value in tenths]
    remainder = 1000 - sum(rounded)
    order = sorted(range(len(values)), key=lambda j: (-(tenths[j] - rounded[j]), j))
    for j in order[:remainder]:
        rounded[j] += 1
    for item, value in zip(values, rounded):
        item['percent'] = value / 10
    return values


def percentage_card(languages):
    if len(languages) > 5:
        raise ValueError('Percentage card supports at most five displayed languages')
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="340" height="200" viewBox="0 0 340 200" role="img" aria-labelledby="title desc">',
        '<title id="title">Language percentages by commit</title>',
        '<desc id="desc">Shares among the languages displayed in the adjacent commit-based donut chart.</desc>',
        '<rect x="1" y="1" width="338" height="198" rx="5" fill="#FCFAFF" stroke="#E4D6F5"/>',
        '<g font-family="Segoe UI, Arial, sans-serif">',
        '<text x="26" y="39" font-size="22" fill="#24292F">Language Percentages</text>',
        '<text x="27" y="55" font-size="10" fill="#6B7280">By commit · displayed languages</text>',
    ]
    for i, item in enumerate(languages):
        y = 77 + i * 25.5
        name = escape(item['name'])
        color = item['color']
        percentage = item['percent']
        parts += [
            f'<circle cx="31" cy="{y - 4}" r="3.5" fill="{color}"/>',
            f'<text x="42" y="{y}" font-size="12" fill="#57606A">{name}</text>',
            f'<text x="312" y="{y}" font-size="13" font-weight="600" text-anchor="end" fill="#24292F">{percentage:.1f}%</text>',
            f'<rect x="27" y="{y + 6}" width="285" height="3" rx="1.5" fill="#EDE7F4"/>',
            f'<rect x="27" y="{y + 6}" width="{285 * percentage / 100:.3f}" height="3" rx="1.5" fill="{color}"/>',
        ]
    parts.append('</g></svg>')
    return ''.join(parts).encode('utf-8')


def main():
    options = {
        'username': OWNER, 'theme': 'default', 'title_color': '24292F',
        'text_color': '57606A', 'bg_color': 'FCFAFF', 'border_color': 'E4D6F5',
        'icon_color': '7C3AED', 'chart_color': 'A279D6',
    }
    fetched = {}
    for card in CARDS:
        url = f'https://github-profile-summary-cards.vercel.app/api/cards/{card}?{urlencode(options)}'
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=45) as response:
            data = response.read()
        svg = ET.fromstring(data)
        if svg.tag.rsplit('}', 1)[-1] != 'svg':
            raise ValueError(f'{card}: expected SVG')
        text = ''.join(svg.itertext())
        if card == 'profile-details' and OWNER.lower() not in text.lower():
            raise ValueError(f'{card}: account name missing')
        if any(error in text.lower() for error in ('api rate limit', 'something went wrong', 'user not found')):
            raise ValueError(f'{card}: service returned an error')
        fetched[card] = data

    fetched['language-percentages'] = percentage_card(language_breakdown(fetched['most-commit-language']))

    directory = ROOT / 'assets' / 'stats'
    directory.mkdir(parents=True, exist_ok=True)
    # Fetch both source cards and derive matching percentages before replacing files.
    for card, data in fetched.items():
        target = directory / f'{card}.svg'
        temporary = target.with_suffix('.svg.tmp')
        temporary.write_bytes(data)
        temporary.replace(target)
        print(f'Updated {card}')


if __name__ == '__main__':
    main()
