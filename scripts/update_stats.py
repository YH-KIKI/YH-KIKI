"""Refresh public GitHub cards. Keep the previous cards if any request fails."""
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import os
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
OWNER = os.environ.get('PROFILE_OWNER', 'YH-KIKI')
CARDS = ('profile-details', 'stats', 'most-commit-language')


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

    directory = ROOT / 'assets' / 'stats'
    directory.mkdir(parents=True, exist_ok=True)
    # Only start replacing cards after all three responses pass validation.
    for card, data in fetched.items():
        target = directory / f'{card}.svg'
        temporary = target.with_suffix('.svg.tmp')
        temporary.write_bytes(data)
        temporary.replace(target)
        print(f'Updated {card}')


if __name__ == '__main__':
    main()
