"""Q0.1: byte-pinned, source-unverified Quran verse snapshot lookup.

This checks that a supplied local *data snapshot* is internally consistent.
It does NOT certify edition authenticity, attribution, permissions, recitation,
Tafsir, or any religious inference. The included corpus is SYNTHETIC ONLY.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import unicodedata
from types import MappingProxyType
from typing import Any, Mapping

# Hafs/Kufan numbering convention; metadata reference: Tanzil Quran Metadata v1.0.
# This table checks numerical topology, not the actual words of the Qur'an.
_VERSE_COUNTS = (
    7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,
    112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,182,88,75,85,
    54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,24,13,
    14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,50,40,46,42,
    29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,8,8,
    11,11,8,3,9,5,4,7,3,6,3,5,4,5,6
)
assert len(_VERSE_COUNTS)==114 and sum(_VERSE_COUNTS)==6236

MANIFEST_FIELDS = frozenset({'contract','source_id','source_kind','provider_url','reading','script','coverage','rights_status','authority_status','declared_verse_count','raw_sha256'})
CORPUS_FIELDS = frozenset({'contract','verses'})
VERSE_FIELDS = frozenset({'surah','ayah','text'})
_MANIFEST_CONTRACT='mubin-quran-q01-source-manifest-v1'
_CORPUS_CONTRACT='mubin-quran-q01-verse-corpus-v1'
_SHA = re.compile(r'[a-f0-9]{64}')
_ID = re.compile(r'[a-z][a-z0-9:_-]{1,79}')
_REF = re.compile(r'([1-9][0-9]{0,2}):([1-9][0-9]{0,2})')
_BIDI_UNSAFE=set(chr(c) for c in list(range(0x202a,0x202f))+list(range(0x2066,0x206a)))

class SnapshotError(ValueError):
    """Untrusted source or query does not match Q0.1's bounded contract."""


def verse_counts() -> tuple[int,...]:
    return _VERSE_COUNTS


def _safe_text(s: Any, *, maxchars:int=4000, arabic:bool=False)->bool:
    if type(s) is not str or not 1<=len(s)<=maxchars:
        return False
    if any(0xD800<=ord(c)<=0xDFFF or ord(c)<0x20 or c in _BIDI_UNSAFE for c in s):
        return False
    try:s.encode('utf-8','strict')
    except UnicodeError:return False
    if arabic and not any('\u0621'<=c<='\u064a' for c in s):
        return False
    return True


def _strict_object(o:Any,keys:frozenset[str])->None:
    if type(o) is not dict or set(o)!=keys or any(type(k) is not str for k in o):
        raise SnapshotError('unexpected_or_missing_object_fields')


def validate_parsed(manifest:Any,corpus:Any)->None:
    """Reject all programmatic subclasses, spoofed fields, unnumbered rows."""
    _strict_object(manifest,MANIFEST_FIELDS)
    _strict_object(corpus,CORPUS_FIELDS)
    if manifest['contract']!=_MANIFEST_CONTRACT or corpus['contract']!=_CORPUS_CONTRACT:
        raise SnapshotError('incorrect_contract')
    sid=manifest['source_id']
    if type(sid) is not str or _ID.fullmatch(sid) is None:
        raise SnapshotError('bad_source_id')
    kind=manifest['source_kind']
    if type(kind) is not str or kind not in ('synthetic_fixture','external_unverified'):
        raise SnapshotError('bad_source_kind')
    if (kind=='synthetic_fixture' and (not sid.startswith('synthetic:') or manifest['provider_url'] is not None)):
        raise SnapshotError('synthetic_identity_mismatch')
    if kind=='external_unverified':
        url=manifest['provider_url']
        if type(url) is not str or not re.fullmatch(r'https://[A-Za-z0-9.-]+(?:/[A-Za-z0-9._~/?#%=&+-]*)?',url):
            raise SnapshotError('unsafe_provider_url')
        if not sid.startswith('external:'):
            raise SnapshotError('external_identity_mismatch')
    if manifest['reading']!='hafs_an_asim_kufan' or manifest['script'] not in ('uthmani','imlaei'):
        raise SnapshotError('reading_or_script_not_supported')
    if (manifest['coverage'] not in ('partial','complete_hafs_kufan')
        or manifest['rights_status']!='not_reviewed_for_this_use'
        or manifest['authority_status']!='not_authenticated'):
        raise SnapshotError('unauthorized_authenticity_or_rights_promotion')
    digest=manifest['raw_sha256']
    if type(digest) is not str or _SHA.fullmatch(digest) is None:
        raise SnapshotError('bad_raw_sha256')
    rows=corpus['verses']
    if type(rows) is not list or not 1<=len(rows)<=6236:
        raise SnapshotError('verse_count_outside_limits')
    if type(manifest['declared_verse_count']) is not int or manifest['declared_verse_count']!=len(rows):
        raise SnapshotError('declared_verse_count_mismatch')
    previous=(0,0)
    chapter_counts=[0]*114
    for row in rows:
        _strict_object(row,VERSE_FIELDS)
        surah,ayah,text=row['surah'],row['ayah'],row['text']
        if type(surah) is not int or type(ayah) is not int or not 1<=surah<=114 or not 1<=ayah<=_VERSE_COUNTS[surah-1]:
            raise SnapshotError('invalid_verse_coordinates')
        if (surah,ayah)<=previous:
            raise SnapshotError('noncanonical_verse_order_or_duplicate')
        if not _safe_text(text,arabic=True):
            raise SnapshotError('unsafe_or_nonarabic_verse_text')
        previous=surah,ayah
        chapter_counts[surah-1]+=1
    if manifest['coverage']=='complete_hafs_kufan' and tuple(chapter_counts)!=_VERSE_COUNTS:
        raise SnapshotError('incomplete_numbering_for_claimed_full_corpus')


def _parse(data:bytes,*,max_size:int)->Any:
    if type(data) is not bytes or not 1<=len(data)<=max_size or data.startswith(b'\xef\xbb\xbf'):
        raise SnapshotError('unsafe_size_or_bom')
    try:
        text=data.decode('utf-8','strict')
        def pairs_check(pairs):
            ans={}
            for k,v in pairs:
                if k in ans:raise SnapshotError('duplicate_json_key')
                ans[k]=v
            return ans
        def invalid_number(_):raise SnapshotError('nonfinite_json_number')
        return json.loads(text,object_pairs_hook=pairs_check,parse_constant=invalid_number)
    except (UnicodeError,ValueError,RecursionError,OverflowError) as exc:
        raise SnapshotError('unreadable_or_malformed_json') from exc


def _fold_arabic_marks(s:str)->str:
    # Query/index-only transformation; source text/bytes remain untouched.
    # Only optional vocalization/Quranic annotation marks are suppressed.
    # U+0653 MADDAH, U+0654/0655 HAMZA, and U+0670 SUPERSCRIPT ALEF
    # distinguish script forms: never erase them as generic Mn marks.
    def _optional_mark(ch:str)->bool:
        point=ord(ch)
        return (unicodedata.category(ch)=='Mn' and (
            0x0610<=point<=0x061A or
            0x064B<=point<=0x0652 or
            0x06D6<=point<=0x06ED
        ))
    return ''.join(ch for ch in s if not _optional_mark(ch))

@dataclass(frozen=True)
class QuranIndex:
    manifest:Mapping[str,Any]
    verses:tuple[tuple[int,int,str],...]
    raw_sha256:str

    def report(self)->dict[str,Any]:
        chapters=len({s for s,_,_ in self.verses})
        return {
            'valid_metadata':True,'scope':'synthetic_fixture_only' if self.manifest['source_kind']=='synthetic_fixture' else 'external_unverified_snapshot',
            'source_id':self.manifest['source_id'],'reading':self.manifest['reading'],
            'script':self.manifest['script'],'coverage':self.manifest['coverage'],
            'loaded_verse_count':len(self.verses),'loaded_surah_count':chapters,
            'raw_sha256':self.raw_sha256,
            'source_authenticated':False,'rights_verified':False,
            'canonical_corpus_qualified':False,'eligible_for_religious_ruling':False,
        }

    def _hit(self,s:int,a:int,text:str)->dict[str,Any]:
        return {'found':True,'reference':f'{s}:{a}','surah':s,'ayah':a,
                'text':text,'source_id':self.manifest['source_id'],
                'raw_sha256':self.raw_sha256,'source_authenticated':False}

    def get(self,ref:str)->dict[str,Any]:
        if type(ref) is not str or not (match:=_REF.fullmatch(ref)):
            raise SnapshotError('malformed_verse_reference')
        s,a=map(int,match.groups())
        if s>114 or a>_VERSE_COUNTS[s-1]:
            raise SnapshotError('verse_reference_out_of_numbering')
        for x,y,text in self.verses:
            if (x,y)==(s,a):return self._hit(x,y,text)
        return {'found':False,'reference':ref}

    def find(self,query:str,*,match:str='exact',limit:int=20)->list[dict[str,Any]]:
        if not _safe_text(query,maxchars=256) or not query.strip():
            raise SnapshotError('unsafe_search_term')
        if type(match) is not str or match not in ('exact','arabic_marks_insensitive'):
            raise SnapshotError('unknown_search_mode')
        if type(limit) is not int or not 1<=limit<=100:
            raise SnapshotError('search_limit_outside_bounds')
        q=_fold_arabic_marks(query) if match=='arabic_marks_insensitive' else query
        if not q.strip():
            raise SnapshotError('empty_after_search_folding')
        out=[]
        for s,a,txt in self.verses:
            t=_fold_arabic_marks(txt) if match=='arabic_marks_insensitive' else txt
            if q in t:out.append(self._hit(s,a,txt))
            if len(out)>=limit:break
        return out


def load_snapshot(manifest_bytes:bytes,corpus_bytes:bytes)->QuranIndex:
    """Load only an already-authorized local snapshot; checksum is *self-declared*."""
    manifest=_parse(manifest_bytes,max_size=32*1024)
    corpus=_parse(corpus_bytes,max_size=8*1024*1024)
    validate_parsed(manifest,corpus)
    sha=hashlib.sha256(corpus_bytes).hexdigest()
    if sha!=manifest['raw_sha256']:
        raise SnapshotError('raw_source_digest_mismatch')
    return QuranIndex(MappingProxyType(dict(manifest)),tuple((x['surah'],x['ayah'],x['text']) for x in corpus['verses']),sha)


def assess_snapshot(manifest_bytes:bytes,corpus_bytes:bytes)->dict[str,Any]:
    try:return {**load_snapshot(manifest_bytes,corpus_bytes).report(),'errors':[]}
    except (SnapshotError,ValueError,TypeError,UnicodeError,RecursionError,OverflowError) as exc:
        return {'valid_metadata':False,'source_authenticated':False,'rights_verified':False,
                'canonical_corpus_qualified':False,'eligible_for_religious_ruling':False,
                'loaded_verse_count':0,'errors':[str(exc)[:100]]}