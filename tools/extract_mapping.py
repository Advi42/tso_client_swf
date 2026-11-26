#!/usr/bin/env python3
"""Extract FileHashing_Mapping + VERSION_NR from an official TSO client SWF.

usage: extract_mapping.py <client.swf> <out_dir> [--version HEX40]
Writes <out_dir>/mapping.data and <out_dir>/version.txt (no trailing newline).
Mapping = DefineBinaryData tag holding writeUTF name/hash pairs (the format
read by nLib/cFilenameUtil.as). Version = the single bare 40-hex string in the
ABC constant pool, unless --version is given.
"""
import re, struct, sys, zlib, os

def load_swf(data):
    sig = data[:3]
    if sig == b'FWS':
        return data[8:]
    if sig == b'CWS':
        return zlib.decompress(data[8:])
    if sig == b'ZWS':
        import lzma  # header: 4 len + 4 clen + 5 props, then raw lzma
        props = data[12:17]
        lc_lp_pb = props[0]
        lc = lc_lp_pb % 9; r = lc_lp_pb // 9; lp = r % 5; pb = r // 5
        filt = [{'id': lzma.FILTER_LZMA1, 'dict_size': struct.unpack('<I', props[1:5])[0],
                 'lc': lc, 'lp': lp, 'pb': pb}]
        return lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=filt).decompress(data[17:])
    raise SystemExit('not a SWF')

def tags(body):
    nbits = body[0] >> 3
    pos = (5 + 4 * nbits + 7) // 8 + 4  # rect + framerate(2) + framecount(2)
    while pos + 2 <= len(body):
        h = struct.unpack_from('<H', body, pos)[0]; pos += 2
        code, ln = h >> 6, h & 63
        if ln == 63:
            ln = struct.unpack_from('<I', body, pos)[0]; pos += 4
        yield code, body[pos:pos + ln]
        pos += ln
        if code == 0:
            break

def parse_pairs(b):
    out = []; i = 0
    while i < len(b):
        if i + 2 > len(b): return None
        n = struct.unpack_from('>H', b, i)[0]; i += 2
        if i + n > len(b): return None
        out.append(b[i:i + n]); i += n
    return out if out and len(out) % 2 == 0 else None

def main():
    a = sys.argv[1:]
    if len(a) < 2: raise SystemExit(__doc__)
    version = a[a.index('--version') + 1] if '--version' in a else None
    body = load_swf(open(a[0], 'rb').read())
    mapping = None; abc_strings = set()
    for code, d in tags(body):
        if code == 87 and mapping is None:            # DefineBinaryData
            p = d[6:]                                  # id(2) + reserved(4)
            pr = parse_pairs(p)
            if pr and pr[0] == b'achievements_definitions.xml':
                mapping = p
        elif code in (72, 82):                         # DoABC / DoABC2
            abc_strings.update(re.findall(rb'(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f.])', d))
    if mapping is None: raise SystemExit('mapping binary not found in SWF')
    if version is None:
        if len(abc_strings) != 1:
            raise SystemExit('ambiguous VERSION_NR candidates %r; pass --version' % sorted(abc_strings))
        version = abc_strings.pop().decode()
    if not re.fullmatch(r'[0-9a-f]{40}', version): raise SystemExit('bad version')
    os.makedirs(a[1], exist_ok=True)
    open(os.path.join(a[1], 'mapping.data'), 'wb').write(mapping)
    open(os.path.join(a[1], 'version.txt'), 'w').write(version)
    print('version', version, 'entries', len(parse_pairs(mapping)) // 2)

main()
