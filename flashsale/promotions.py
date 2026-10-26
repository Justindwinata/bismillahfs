"""Classify explicitly published offer evidence; never infer a promo SKU from a banner."""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from .core import ZONE

def normalized(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip().casefold()

def matching_offers(snapshot, choices, target, ceiling):
    from .shopee import product_url
    target=datetime.fromisoformat(target) if isinstance(target,str) else target
    if not isinstance(target,datetime) or target.tzinfo is None:
        return []
    wanted=sorted(normalized(x) for x in choices)
    matches=[]
    for offer in snapshot.get('published',[]):
        if not isinstance(offer,dict): continue
        try:
            if offer.get('parent_url'):
                if not isinstance(offer['parent_url'],str): continue
                if product_url(offer['parent_url'])!=product_url(snapshot['url']): continue
            elif normalized(offer.get('parent_name'))!=normalized(snapshot.get('title')): continue
            labels=sorted(normalized(x) for x in offer.get('labels',[]) if normalized(x))
            if labels!=wanted: continue
            if not re.search(r'flash\s*sale',offer.get('name','')+' '+offer.get('description',''),re.I): continue
            if offer.get('currency')!='IDR': continue
            amount=Decimal(str(offer.get('price')))
            if not amount.is_finite() or not Decimal(0)<amount<=Decimal(str(ceiling)): continue
            start=datetime.fromisoformat(str(offer.get('valid_from','')).replace('Z','+00:00'))
            if start.tzinfo is None: continue
            if start.astimezone(ZONE)!=target.astimezone(ZONE): continue
            if str(offer.get('availability','')).rstrip('/').split('/')[-1]!='InStock': continue
            if not offer.get('sku'): continue
            matches.append({'sku':offer['sku'],'price':str(amount),'starts_at':start.astimezone(ZONE).isoformat()})
        except (ValueError,TypeError,InvalidOperation,KeyError):
            continue
    return matches


def scan_summary(rows):
    """Describe observed evidence without promoting a listing banner to a SKU offer."""
    available = sum(bool(row.get('available')) for row in rows)
    announcements = sorted({line for row in rows for line in row.get('evidence', [])
                            if re.search(r'mulai(?:\s+pada)?\s+\d{1,2}[:.]\d{2}', line, re.I)})
    return {'available_combinations': available,
            'unavailable_combinations': len(rows) - available,
            'announcements': announcements,
            'reason': ('Jadwal promo terdeteksi pada listing, tetapi belum ada penawaran publik yang '
                       'mengikat harga promo ke satu varian dan paket.' if announcements else
                       'Belum ditemukan penawaran publik yang mengikat jadwal, harga promo, varian, dan paket.')}


def schedule_conflicts(announcements, target):
    """Compare explicit Indonesian teaser dates with the requested WIB schedule."""
    try:
        moment = datetime.fromisoformat(target).astimezone(ZONE)
    except (ValueError, TypeError):
        return []
    months = {'jan':1,'feb':2,'mar':3,'apr':4,'mei':5,'jun':6,
              'jul':7,'agu':8,'sep':9,'okt':10,'nov':11,'des':12}
    conflicts = []
    for line in announcements:
        match = re.search(r'mulai(?:\s+pada)?\s+(\d{1,2})[:.](\d{2}),?\s+(\d{1,2})\s+([A-Za-z]+)', line, re.I)
        if not match:
            continue
        hour, minute, day = map(int, match.group(1,2,3))
        month = months.get(match.group(4).lower()[:3])
        if month and (moment.month,moment.day,moment.hour,moment.minute)!=(month,day,hour,minute):
            conflicts.append(line)
    return sorted(set(conflicts))


def catalog_summary(catalog):
    """Report model identity separately from campaign membership and pricing."""
    models=catalog.get('models',[])
    preview=catalog.get('preview') or {}
    promotion=str(preview.get('promotion_id') or '')
    linked=[m for m in models if promotion and str(m.get('promotion_id') or '')==promotion]
    return {'model_count':len(models),'campaign_id':promotion,
            'linked_model_ids':[m['model_id'] for m in linked]}
