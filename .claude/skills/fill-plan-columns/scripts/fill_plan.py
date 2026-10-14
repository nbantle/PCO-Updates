#!/usr/bin/env python3
"""Fill the production columns (Cue #, Audio, On Stage, Switcher, Timer) on the next two
Rochester Campus weekend plans in Planning Center Services, using Nate's rules, and match
each real song's length to the same song in that Sunday's _CENTRAL plan.

Usage:
  PCO_APP_ID=... PCO_SECRET=... python3 fill_plan.py [--calendar FILE] [--apply]
  PCO_APP_ID=... PCO_SECRET=... python3 fill_plan.py --plan PLAN_ID [--speaker FIRSTNAME] [--apply]

--calendar is the "Preaching Calendar // Northridge Church" sheet exported as .xlsx (or the
Drive tool's saved JSON wrapper around it); the speaker for each Sunday is column I of the
"Preaching Calendar" tab. Without it, speakers come from the Service Planning page
(nbantle.github.io/service-planning), which is generated from that same column.

Without --apply it only prints what it would change (dry run).
Never touches the Leader column, song Timers, or plans beyond the next two weekends.
"""
import os, re, sys, json, base64, datetime, urllib.request, urllib.error

ST = '34139'  # Rochester Campus
CENTRAL_ST = '1755399'  # _CENTRAL: the source of truth for song lengths
BASE = 'https://api.planningcenteronline.com/services/v2'
CAT = {'Cue #': '2321386', 'Audio': '6016093', 'On Stage': '2322068',
       'Switcher': '77156', 'Timer': '808264'}

AUTH = 'Basic ' + base64.b64encode(
    f"{os.environ['PCO_APP_ID']}:{os.environ['PCO_SECRET']}".encode()).decode()


def req(path, method='GET', body=None):
    url = path if path.startswith('http') else BASE + path
    r = urllib.request.Request(url, method=method,
                               data=json.dumps(body).encode() if body else None,
                               headers={'Authorization': AUTH, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r) as f:
            t = f.read()
            return json.loads(t) if t else {}
    except urllib.error.HTTPError as e:
        sys.exit(f'PCO {method} {url} -> {e.code}: {e.read().decode()[:500]}')


def short_name(full):
    """'Alex Kingston' -> 'Alex K.'  (matches the existing On Stage format)."""
    full = re.sub(r'\s*\(.*?\)\s*', ' ', full).split()
    return f'{full[0]} {full[-1][0]}.' if len(full) > 1 else full[0]


def name_keys(full):
    """All (first, last-initial) pairs a roster name can be written as, incl. nicknames."""
    nick = re.findall(r'\((.*?)\)', full)
    parts = re.sub(r'\s*\(.*?\)\s*', ' ', full).split()
    if not parts:
        return set()
    firsts = {parts[0].lower()} | {n.lower() for n in nick}
    return {(f, parts[-1][0].lower()) for f in firsts}


def onstage_key(s):
    p = s.replace('.', ' ').split()
    return (p[0].lower(), p[1][0].lower()) if len(p) >= 2 else (p[0].lower() if p else '', '')


def find_vocal(vocal, who):
    """Match an On Stage name ('Sam P.') to (vocal number, last initial); allows
    shortened first names (Sam -> Samantha) when exactly one singer fits."""
    first, li = onstage_key(who)
    if (first, li) in vocal:
        return vocal[(first, li)], li
    hits = {(n, l) for (f, l), n in vocal.items()
            if (l == li or not li) and (f.startswith(first) or first.startswith(f))}
    if not hits and li:
        # Nicknames that aren't prefixes ('Liz' for Elizabeth): same first letter + last initial
        hits = {(n, l) for (f, l), n in vocal.items() if l == li and f[:1] == first[:1]}
    return hits.pop() if len(hits) == 1 else (None, None)


def upcoming_plans(n=2):
    """The next `n` weekend plans (one plan = Thursday + Sunday), within two weeks."""
    today = datetime.date.today()
    plans = req(f'/service_types/{ST}/plans?filter=future&order=sort_date&per_page=5')['data']
    out = [p for p in plans
           if (datetime.date.fromisoformat(p['attributes']['sort_date'][:10]) - today).days <= 14][:n]
    if not out:
        sys.exit(f'No Rochester plan in the next two weeks (next: {plans[0]["attributes"]["dates"] if plans else "none"})')
    return out


def plan_sunday(plan):
    sd = datetime.date.fromisoformat(plan['attributes']['sort_date'][:10])
    return sd + datetime.timedelta(days=(6 - sd.weekday()) % 7)


def calendar_speakers(path):
    """{date: speaker first name} from column I of the Preaching Calendar tab."""
    import zipfile, io
    from xml.etree import ElementTree as ET
    raw = open(path, 'rb').read()
    if raw[:2] != b'PK':  # Drive tool's saved JSON: {"content": "<base64 xlsx>", ...}
        raw = base64.b64decode(json.loads(raw)['content'])
    z = zipfile.ZipFile(io.BytesIO(raw))
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    ss = [''.join(t.text or '' for t in si.iter('{%s}t' % ns['m']))
          for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', ns)]
    rid = [x for x in ET.fromstring(z.read('xl/workbook.xml')).find('m:sheets', ns)
           if x.get('name') == 'Preaching Calendar'][0].get(R)
    tgt = [r for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')) if r.get('Id') == rid][0].get('Target')
    tgt = tgt.lstrip('/') if tgt.lstrip('/').startswith('xl/') else 'xl/' + tgt
    out = {}
    for row in ET.fromstring(z.read(tgt)).iter('{%s}row' % ns['m']):
        cells = {}
        for c in row.findall('m:c', ns):
            v = c.find('m:v', ns)
            if v is None:
                continue
            cells[re.match(r'[A-Z]+', c.get('r')).group()] = ss[int(v.text)] if c.get('t') == 's' else v.text
        for col in ('B', 'G'):
            try:
                d = datetime.date(1899, 12, 30) + datetime.timedelta(days=float(cells.get(col)))
            except (TypeError, ValueError):
                continue
            if (cells.get('I') or '').strip():
                out[d] = cells['I'].strip()
            break
    return out


VIDEO_WORDS = ('video', 'promo', 'title package', 'story')


def classify(title, item_type):
    t = title.lower()
    if 'pre-service' in t or 'preservice' in t: return 'pre'
    if 'countdown' in t: return 'countdown'
    if 'end of service' in t: return 'end'
    if 'host moment' in t: return 'host'
    if 'closing comments' in t: return 'closing'
    if 'transition comments' in t: return 'transition'
    if t.strip() == 'message' or t.startswith('message'): return 'message'
    if 'baptism' in t: return 'baptism'
    if any(w in t for w in VIDEO_WORDS): return 'video'
    if item_type == 'song': return 'song'  # real songs + Spiritual Direction / Flow
    return 'other'


def mmss(seconds):
    """Item length in seconds -> timer text ('25:00', '6:01')."""
    m, s = divmod(int(seconds or 0), 60)
    return f'{m}:{s:02d}'


SPEAKING = ('host', 'transition', 'message', 'closing')

# Recurring placeholders that Planning Center stores as songs; never length-matched.
NOT_REAL_SONGS = ('spiritual direction', 'flow', 'offering')


def is_real_song(a, kind):
    return (a['item_type'] == 'song' and kind == 'song'
            and not a['title'].strip().lower().startswith(NOT_REAL_SONGS))


def central_lengths(sunday):
    """{song id or lowercased title: length} for the real songs in Central's plan for `sunday`,
    or None when Central has no plan that day."""
    plans = req(f'/service_types/{CENTRAL_ST}/plans?filter=future&order=sort_date&per_page=10')['data']
    plan = next((p for p in plans if p['attributes']['sort_date'][:10] == sunday.isoformat()), None)
    if not plan:
        return None
    out = {}
    for it in req(f"/service_types/{CENTRAL_ST}/plans/{plan['id']}/items?per_page=100")['data']:
        a = it['attributes']
        if not is_real_song(a, classify(a['title'], a['item_type'])):
            continue
        sid = ((it['relationships'].get('song') or {}).get('data') or {}).get('id')
        if sid:
            out[sid] = a['length']
        out[a['title'].strip().lower()] = a['length']
    return out


def past_speaker(first):
    """Find 'First L.' for a calendar first name from Message On Stage in past plans."""
    first = first.split()[0].lower()
    for p in req(f'/service_types/{ST}/plans?filter=past&order=-sort_date&per_page=40')['data']:
        d = req(f"/service_types/{ST}/plans/{p['id']}/items?include=item_notes&per_page=100")
        notes = {n['id']: n['attributes'] for n in d.get('included', []) if n['type'] == 'ItemNote'}
        for it in d['data']:
            if classify(it['attributes']['title'], it['attributes']['item_type']) != 'message':
                continue
            for r in it['relationships']['item_notes']['data']:
                n = notes[r['id']]
                v = (n['content'] or '').strip()
                if n['category_name'] == 'On Stage' and v.lower().startswith(first) and '.' in v:
                    return v
    return None


def page_speaker(sunday):
    """Speaker for `sunday` from the Service Planning page's 'Upcoming Communicators'
    (column I of the Preaching Calendar). Returns (first_name or None, note)."""
    import html
    try:
        with urllib.request.urlopen('https://nbantle.github.io/service-planning/', timeout=30) as f:
            raw = f.read().decode()
    except Exception as e:
        return None, f'could not load the Service Planning page ({e})'
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', raw, flags=re.S)
    t = html.unescape(re.sub(r'<[^>]+>', '|', t)).replace('\xa0', ' ')
    t = re.sub(r'\s*\|[\s|]*', '|', t)
    sec = t[t.find('Upcoming Communicators'):]
    want = sunday.strftime('%b ') + str(sunday.day)
    m = re.search(r'\|([^|]+)\|·[^|]*\|Sun, ' + re.escape(want) + r'\|', sec)
    note = ''
    u = re.search(r'updated (\w{3} \d{1,2}, \d{4})', sec)
    if u:
        age = (datetime.date.today() - datetime.datetime.strptime(u.group(1), '%b %d, %Y').date()).days
        if age > 9:
            note = f'Service Planning page is {age} days stale'
    return (m.group(1).strip() if m else None), note


def main():
    apply = '--apply' in sys.argv
    arg = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
    if arg('--plan'):
        plans = [req(f"/service_types/{ST}/plans/{arg('--plan')}")['data']]
    else:
        plans = upcoming_plans(2)
    cal = calendar_speakers(arg('--calendar')) if arg('--calendar') else None
    for plan in plans:
        sunday = plan_sunday(plan)
        if arg('--speaker'):
            name, why = arg('--speaker'), ''
        elif cal is not None:
            name = cal.get(sunday)
            why = '' if name else f'no speaker for {sunday} on the Preaching Calendar'
        else:
            name, why = page_speaker(sunday)
            if name:
                why = ''
            elif not why:
                why = f'no speaker for {sunday} on the Service Planning page'
        fill(plan, name, why, apply)
        print()


def fill(plan, cal, cal_problem, apply):
    pid = plan['id']
    P = f'/service_types/{ST}/plans/{pid}'
    print(f"Plan: {plan['attributes']['dates']} (id {pid})  {'APPLY' if apply else 'DRY RUN'}")

    # Roster: vocal numbers, host and speaker (Speaking team)
    vocal, host, speaker, speaker_flag = {}, None, None, None
    data = req(P + '/team_members?per_page=100&include=team')
    teams = {t['id']: t['attributes']['name'].strip().lower()
             for t in data.get('included', []) if t['type'] == 'Team'}
    for m in data['data']:
        a = m['attributes']
        if a['status'] == 'D':
            continue
        pos = (a['team_position_name'] or '').strip()
        team = teams.get(((m['relationships'].get('team') or {}).get('data') or {}).get('id'), '')
        mv = re.match(r'Vocal\s*(\d+)', pos, re.I)
        if mv:
            for k in name_keys(a['name']):
                vocal[k] = mv.group(1)
        elif team == 'speaking' and pos.lower() == 'host':
            host = short_name(a['name'])
        elif team == 'speaking' and pos.lower() == 'message':
            speaker = short_name(a['name'])

    # The Preaching Calendar is the source of truth for the speaker. The Speaking roster
    # is sometimes stale, so it's only used to supply the last initial when first names agree.
    if not cal:
        speaker_flag = f'Message: {cal_problem}'
        speaker = None
    else:
        if speaker and speaker.split()[0].lower() == cal.split()[0].lower():
            pass
        else:
            speaker = past_speaker(cal) or None
            if not speaker:
                speaker_flag = f'Message: calendar says "{cal}" but I can\'t find a last name — On Stage left as is'

    d = req(P + '/items?include=item_notes&per_page=100')
    notes = {n['id']: n for n in d.get('included', []) if n['type'] == 'ItemNote'}

    # Song lengths: every real song (not the recurring placeholders) takes Central's length.
    central = central_lengths(plan_sunday(plan))
    length_changes, flags = [], []
    if central is None:
        flags.append(f'Song lengths: no Central plan for {plan_sunday(plan)} — lengths left as is')
    for it in d['data']:
        a = it['attributes']
        if central is None or not is_real_song(a, classify(a['title'], a['item_type'])):
            continue
        sid = ((it['relationships'].get('song') or {}).get('data') or {}).get('id')
        target = central.get(sid, central.get(a['title'].strip().lower()))
        if target is None:
            flags.append(f'{a["title"]}: not in Central\'s plan — length left as is')
        elif target != a['length']:
            length_changes.append((it['id'], a['title'].strip(), a['length'], target))
            a['length'] = target  # keep speaking-moment timers etc. consistent below

    changes, cue = [], 0
    for it in sorted(d['data'], key=lambda i: i['attributes']['sequence']):
        a = it['attributes']
        if a['item_type'] == 'header':
            continue
        title = a['title'].strip()
        cur = {}
        for r in it['relationships']['item_notes']['data']:
            n = notes[r['id']]['attributes']
            cur[n['category_name']] = (r['id'], (n['content'] or '').strip())
        val = lambda c: cur.get(c, (None, ''))[1]
        kind = classify(title, a['item_type'])
        want = {}

        cue += 1
        want['Cue #'] = '1' if kind == 'end' else str(cue)

        if kind == 'pre':
            want.update({'Audio': 'Spotify', 'Switcher': 'Mac'})
        elif kind == 'countdown':
            want.update({'Audio': 'Mac', 'Switcher': 'Mac'})
        elif kind == 'end':
            want.update({'Switcher': 'Mac'})
        elif kind == 'host':
            want['Audio'] = 'W8/Band'
            if host: want['On Stage'] = host
            else: flags.append(f'{title}: no Host on the Speaking team')
        elif kind == 'closing':
            want['Audio'] = 'W8/Keys'
            if host: want['On Stage'] = host
        elif kind in ('message', 'transition'):
            # Transition Comments are given by whoever preaches the message.
            want['Audio'] = 'W7'
            if speaker: want['On Stage'] = speaker
            else: flags.append(f'{title}: ' + (speaker_flag or 'no speaker found').removeprefix('Message: '))
        elif kind == 'baptism':
            want['Audio'] = 'W9'
        elif kind == 'video':
            want.update({'Audio': 'Mac', 'Switcher': 'Mac'})
        elif kind == 'song':
            who = val('On Stage')
            if not who:
                flags.append(f'{title}: On Stage is blank — can\'t pick a mic')
            else:
                # Shared leads ('Jordan/Sam', 'Jordan R. & Sam P.') -> one mic each,
                # written like the existing multi-person cells: 'W1/W5/Band', 'Jordan R. / Sam P.'
                people = [p.strip() for p in re.split(r'\s*(?:/|&|,|\band\b)\s*', who) if p.strip()]
                found = [(p, *find_vocal(vocal, p)) for p in people]
                missing = [p for p, n, _ in found if not n]
                if missing:
                    flags.append(f'{title}: "{", ".join(missing)}" isn\'t on a Vocal position this week')
                else:
                    want['Audio'] = '/'.join(f'W{n}' for _, n, _ in found) + '/Band'
                    # On Stage is always 'First L.' — keep the first name as written
                    want['On Stage'] = ' / '.join(
                        f"{p.replace('.', ' ').split()[0]} {li.upper()}." for p, _, li in found)
        else:
            if not val('Audio'):
                flags.append(f'{title}: Audio is blank — what should it be?')

        # Speaking moments: the timer always matches the item's length.
        if kind in SPEAKING:
            want['Timer'] = mmss(a['length'])
        # Switcher is only ever 'Mac' or blank. Videos and pre/countdown/end get Mac;
        # anything else ('Stream', etc.) is cleared, but an existing Mac is left alone.
        if 'Switcher' not in want and val('Switcher') and val('Switcher').lower() != 'mac':
            want['Switcher'] = ''

        # A Host Moment with several people on it ('Host A. / Guest B.') is a deliberate
        # one-off; flag it instead of collapsing it back to the template.
        if kind in ('host', 'closing') and '/' in val('On Stage'):
            flags.append(f'{title}: special lineup "{val("On Stage")}" / "{val("Audio")}" — left as is')
            want.pop('On Stage', None); want.pop('Audio', None)

        for cat, v in want.items():
            if val(cat) != v:
                changes.append((it['id'], title, cat, cur.get(cat, (None, ''))[0], val(cat), v))

    for iid, title, old, new in length_changes:
        print(f'  {title:32} {"Length":9} {mmss(old):>12} -> {mmss(new)}  (Central)')
        if apply:
            req(f'{P}/items/{iid}', 'PATCH', {'data': {'type': 'Item', 'attributes': {'length': new}}})
    for iid, title, cat, nid, old, new in changes:
        print(f'  {title:32} {cat:9} {old or "(blank)":>12} -> {new or "(blank)"}')
        if apply:
            base = f'{P}/items/{iid}/item_notes'
            if nid and not new:
                req(f'{base}/{nid}', 'DELETE')
            elif nid:
                req(f'{base}/{nid}', 'PATCH', {'data': {'type': 'ItemNote', 'attributes': {'content': new}}})
            else:
                req(base, 'POST', {'data': {'type': 'ItemNote', 'attributes': {
                    'content': new, 'item_note_category_id': CAT[cat]}}})
    if not changes and not length_changes:
        print('  No changes needed.')
    print('Flags:' if flags else 'Flags: none')
    for f in flags:
        print('  - ' + f)


if __name__ == '__main__':
    main()
