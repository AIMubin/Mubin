"""Q0.1b: bounded, byte-exact, *unverified-mirror* Tanzil-format reader.

Never rewrites, exports, or claims publisher-authentic scripture. An external
GitHub mirror is NOT an independently authenticated Tanzil download.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import re
import stat
from types import MappingProxyType
from typing import Any, Mapping

from engines.quran.q01.engine import (
    SnapshotError, _fold_arabic_marks, _safe_text, _VERSE_COUNTS,
)

MAX_RAW_BYTES = 4 * 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024
_REPO = 'acfatah/tanzil'
_COMMIT = '052b515f3a24dfacbe4cafc3b89f0681a447f462'
_BLOB = 'f2f03c415ea50f8493d2058ec67a90257333abe3'
_URL = f'https://raw.githubusercontent.com/{_REPO}/{_COMMIT}/data/quran-uthmani.txt'
_FIELDS = frozenset(('contract','source_kind','source_id','source_url','source_commit','source_git_blob_sha1',
                     'raw_sha256','raw_byte_count','coverage','reading','rights_status','authority_status'))
_COMPACT_REF = re.compile(r'([1-9][0-9]{0,2}):([1-9][0-9]{0,2})')
_ROW = re.compile(r'([1-9][0-9]{0,2})\|([1-9][0-9]{0,2})\|(.+)')
_SHA256 = re.compile('[a-f0-9]{64}')

class RawSourceError(SnapshotError):
    """Untrusted snapshot or its source identity failed closed."""


def read_regular_file(path: str | Path, limit: int) -> bytes:
    """Read bounded, non-symlink leaf through one file descriptor (Linux CI)."""
    if not isinstance(path, (str, Path)) or type(limit) is not int or limit <= 0:
        raise RawSourceError('unsafe_path_or_limit')
    name = os.fspath(path)
    if not name or '\x00' in name:
        raise RawSourceError('unsafe_path_or_limit')
    flags = os.O_RDONLY | getattr(os,'O_NONBLOCK',0) | getattr(os,'O_CLOEXEC',0) | getattr(os,'O_NOFOLLOW',0)
    try:
        fd = os.open(name, flags)
        try:
            meta = os.fstat(fd)
            if not stat.S_ISREG(meta.st_mode) or meta.st_size <= 0 or meta.st_size > limit:
                raise RawSourceError('unsafe_source_file')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                data = stream.read(limit + 1)
            if len(data) != meta.st_size or len(data) > limit:
                raise RawSourceError('source_size_changed_or_exceeded')
            tail_meta = os.fstat(fd)
            if (tail_meta.st_dev,tail_meta.st_ino,tail_meta.st_size)!=(meta.st_dev,meta.st_ino,meta.st_size):
                raise RawSourceError('source_changed_during_read')
            return data
        finally:
            os.close(fd)
    except (OSError,OverflowError) as exc:
        raise RawSourceError('unreadable_or_unsafe_source') from exc


def _decode_manifest(blob: bytes) -> dict[str,Any]:
    if type(blob) is not bytes or not 1 <= len(blob) <= MAX_MANIFEST_BYTES or blob.startswith(b'\xef\xbb\xbf'):
        raise RawSourceError('manifest_size_or_bom')
    try:
        def pairs(values):
            out = {}
            for key,val in values:
                if key in out:raise RawSourceError('duplicate_manifest_key')
                out[key]=val
            return out
        def nonfinite(_):raise RawSourceError('nonfinite_manifest_number')
        obj=json.loads(blob.decode('utf-8','strict'),object_pairs_hook=pairs,parse_constant=nonfinite)
    except (ValueError,UnicodeError,RecursionError,OverflowError) as exc:
        raise RawSourceError('invalid_manifest_json') from exc
    if type(obj) is not dict or set(obj)!=_FIELDS or any(type(k) is not str for k in obj):
        raise RawSourceError('manifest_shape_mismatch')
    if obj['contract']!='mubin-quran-q01b-verbatim-source-v1':
        raise RawSourceError('unexpected_manifest_contract')
    kind=obj['source_kind']
    if type(kind) is not str or kind not in ('synthetic_fixture','unverified_github_mirror'):
        raise RawSourceError('unsupported_source_kind')
    if obj['coverage'] not in ('partial','complete_hafs_kufan') or obj['reading']!='hafs_an_asim_kufan':
        raise RawSourceError('unsupported_reading_or_coverage')
    if obj['rights_status']!='requires_use_review' or obj['authority_status']!='not_authenticated':
        raise RawSourceError('forbidden_rights_or_authority_promotion')
    if type(obj['raw_sha256']) is not str or not _SHA256.fullmatch(obj['raw_sha256']):
        raise RawSourceError('invalid_sha256')
    if type(obj['raw_byte_count']) is not int or not 1 <= obj['raw_byte_count'] <= MAX_RAW_BYTES:
        raise RawSourceError('invalid_raw_byte_count')
    if kind=='synthetic_fixture':
        if (obj['coverage']!='partial' or obj['source_id']!='synthetic:q01b'
                or obj['source_url'] is not None or obj['source_commit'] is not None
                or obj['source_git_blob_sha1'] is not None):
            raise RawSourceError('invalid_synthetic_source_identity')
    else:
        if (obj['coverage']!='complete_hafs_kufan' or obj['source_id']!='mirror:acfatah-tanzil-uthmani-v1.1'
            or obj['source_url']!=_URL or obj['source_commit']!=_COMMIT
            or obj['source_git_blob_sha1']!=_BLOB):
            raise RawSourceError('untrusted_mirror_identity')
    return obj


def _source_text_lines(raw: bytes, kind: str) -> tuple[tuple[int,int,str], ...]:
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_RAW_BYTES or raw.startswith(b'\xef\xbb\xbf'):
        raise RawSourceError('raw_file_size_or_bom')
    try: text=raw.decode('utf-8','strict')
    except UnicodeError as exc:raise RawSourceError('raw_not_utf8') from exc
    if '\r' in text or not text.endswith('\n'):
        raise RawSourceError('line_endings_not_exact_lf')
    lines=text.split('\n')
    if lines[-1]!='':raise RawSourceError('missing_final_newline')
    records=[]
    footer=[]
    in_footer=False
    blanks=0
    for line in lines[:-1]:
        if not in_footer and _ROW.fullmatch(line):
            m=_ROW.fullmatch(line)
            s,a=int(m[1]),int(m[2]);val=m[3]
            if (not 1<=s<=114 or not 1<=a<=_VERSE_COUNTS[s-1] or
                    not _safe_text(val,maxchars=4000,arabic=True)):
                raise RawSourceError('unsafe_record_coordinate_or_text')
            records.append((s,a,val))
            if len(records)>6236:raise RawSourceError('too_many_verses')
        elif line=='':
            in_footer=True
            blanks+=1
            if blanks>3:raise RawSourceError('unexpected_blank_line')
            footer.append(line)
        elif line.startswith('#') and kind=='unverified_github_mirror' and len(records)==6236:
            in_footer=True
            footer.append(line)
        else:
            raise RawSourceError('unsafe_or_misplaced_nonverse_line')
    if not records:raise RawSourceError('empty_verse_data')
    if kind=='unverified_github_mirror':
        tail='\n'.join(footer)
        for token in ('Tanzil Quran Text (Uthmani, Version 1.1)',
                      'License: Creative Commons Attribution 3.0',
                      'CHANGING IT IS NOT ALLOWED.', 'tanzil.net'):
            if token not in tail:raise RawSourceError('missing_original_source_notice')
        if len(records)!=6236:raise RawSourceError('mirror_incomplete')
    elif footer:
        raise RawSourceError('unexpected_synthetic_footer')
    previous=(0,0)
    counts=[0]*114
    for s,a,_ in records:
        if (s,a)<=previous:raise RawSourceError('out_of_order_or_duplicate_verse')
        counts[s-1]+=1
        previous=(s,a)
    if kind=='unverified_github_mirror' and tuple(counts)!=_VERSE_COUNTS:
        raise RawSourceError('incorrect_complete_hafs_topology')
    return tuple(records)


@dataclass(frozen=True)
class SourceIndex:
    manifest:Mapping[str,Any]
    verses:tuple[tuple[int,int,str],...]
    raw_sha256:str

    def report(self)->dict[str,Any]:
        return {'valid_metadata':True,'source_id':self.manifest['source_id'],
                'coverage':self.manifest['coverage'],'verse_count':len(self.verses),
                'chapter_count':len({s for s,_,_ in self.verses}),
                'raw_sha256':self.raw_sha256,
                'source_kind':self.manifest['source_kind'],
                'source_authenticated':False,'official_tanzil_bytes_independently_verified':False,
                'rights_verified':False,'eligible_for_religious_ruling':False,
                'source_byte_preservation':True}

    def get(self, ref: str)->dict[str,Any]:
        m=_COMPACT_REF.fullmatch(ref) if type(ref) is str else None
        if not m:raise RawSourceError('invalid_reference')
        s,a=int(m[1]),int(m[2])
        if not 1<=s<=114 or not 1<=a<=_VERSE_COUNTS[s-1]:
            raise RawSourceError('reference_out_of_range')
        for x,y,t in self.verses:
            if x==s and y==a:return self._hit(x,y,t)
        return {'found':False,'reference':ref}

    def _hit(self,s:int,a:int,t:str)->dict[str,Any]:
        return {'found':True,'reference':f'{s}:{a}','text':t,'source_id':self.manifest['source_id'],
                'raw_sha256':self.raw_sha256,'source_authenticated':False}

    def find(self,query:str,*,fold_marks:bool=False,limit:int=20)->list[dict[str,Any]]:
        if not _safe_text(query,maxchars=256) or not query.strip():
            raise RawSourceError('invalid_search_query')
        if type(fold_marks) is not bool or type(limit) is not int or not 1<=limit<=100:
            raise RawSourceError('invalid_search_options')
        q=_fold_arabic_marks(query) if fold_marks else query
        if not q.strip():raise RawSourceError('empty_query_after_mark_removal')
        out=[]
        for s,a,text in self.verses:
            match_text=_fold_arabic_marks(text) if fold_marks else text
            if q in match_text:out.append(self._hit(s,a,text))
            if len(out)>=limit:break
        return out


def load_raw(manifest_blob:bytes,raw:bytes)->SourceIndex:
    obj=_decode_manifest(manifest_blob)
    if type(raw) is not bytes or len(raw)!=obj['raw_byte_count'] or sha256(raw).hexdigest()!=obj['raw_sha256']:
        raise RawSourceError('raw_byte_digest_or_length_mismatch')
    if obj['source_kind']=='unverified_github_mirror':
        blob=sha1(b'blob '+str(len(raw)).encode('ascii')+b'\x00'+raw).hexdigest()
        if blob!=obj['source_git_blob_sha1']:
            raise RawSourceError('pinned_git_blob_mismatch')
    verses=_source_text_lines(raw,obj['source_kind'])
    return SourceIndex(MappingProxyType(dict(obj)),verses,obj['raw_sha256'])


def assess_raw(manifest_blob:bytes,raw:bytes)->dict[str,Any]:
    try:return {**load_raw(manifest_blob,raw).report(),'errors':[]}
    except (ValueError,TypeError,UnicodeError,RecursionError,OverflowError) as exc:
        return {'valid_metadata':False,'source_authenticated':False,'rights_verified':False,
                'eligible_for_religious_ruling':False,'errors':[str(exc)[:120]]}
