#!/usr/bin/env python3
"""Validate the actual release tree, original reporting and generated data values."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote,urljoin,urlsplit
import build

ROOT=Path(__file__).resolve().parent

def paragraphs(text):
    doc=build.Document(text);result=[]
    for node in doc.nodes:
        if node.tag!='p':continue
        ancestor=node.parent;skip=False
        while ancestor:
            if ancestor.attrs.get('id') in ('PINpopover','footer') or 'archive-' in ancestor.attrs.get('class',''):
                skip=True;break
            ancestor=ancestor.parent
        if not skip:
            value=doc.plain(node)
            if value:result.append(value)
    return result

def cells(text):
    doc=build.Document(text);return [doc.plain(n) for n in doc.nodes if n.tag in ('th','td')]

def validate(baseline,output):
    baseline=Path(baseline);output=Path(output);failures=[]
    def fail(message):failures.append(message)
    try:
        old=build.hashes(baseline);new=build.hashes(output)
    except (OSError,ValueError) as exc:return {'failures':[str(exc)]}
    expected={k:v['sha256'] for k,v in json.loads(build.read(ROOT/'baseline-manifest.json'))['objects'].items()}
    if old!=expected:fail('Baseline differs from reviewed snapshot')
    if not set(old)<=set(new):fail('Original keys were deleted')
    additions=set(new)-set(old)
    if additions!=set(build.ASSETS):fail('Unexpected additions: '+str(sorted(additions)))
    config=json.loads(build.read(ROOT/'repairs.json'))
    for key,oldsha in old.items():
        if key not in new:continue
        if not key.endswith('.html'):
            if oldsha!=new[key]:fail('Original binary/data/asset changed: '+key)
            continue
        original=build.read(baseline/key);text=build.read(output/key);doc=build.Document(text);before=build.Document(original)
        # Independent semantic invariants complement exact generated-byte comparison.
        old_images=[n.attrs.get('src') for n in before.nodes if n.tag=='img']
        new_images=[n.attrs.get('src') for n in doc.nodes if n.tag=='img']
        if any(new_images.count(src)<count for src,count in Counter(old_images).items()):fail('Original image lost: '+key)
        media=[n.attrs for n in before.nodes if n.tag=='iframe' and any(host in n.attrs.get('src','') for host in ('youtube.com','vimeo.com','soundcloud.com'))]
        for attrs in media:
            if not any(n.tag=='iframe' and all(n.attrs.get(k)==v for k,v in attrs.items()) for n in doc.nodes):fail('External media attributes changed: '+key)
        visible=build.plain(text)
        for paragraph in paragraphs(original):
            if paragraph not in visible:fail('Original paragraph/caption lost: '+key+' '+paragraph[:90])
        for node in doc.nodes:
            if node.tag=='img' and 'alt' not in node.attrs:fail('Image alternative missing: '+key)
            if node.tag=='iframe' and not node.attrs.get('title'):fail('Frame title missing: '+key)
            if node.attrs.get('src','').startswith('http://'):fail('HTTP subresource: '+key)
            if node.attrs.get('data-target')=='#PINpopover':fail('Active closed feedback control: '+key)
            if 'pinform.js' in node.attrs.get('src',''):fail('Feedback loader remains: '+key)
        if 'role="main"' in original:
            if sum(n.tag=='h1' for n in doc.nodes)!=1:fail('Full page needs one topic h1: '+key)
            if sum(n.tag=='main' or n.attrs.get('role')=='main' for n in doc.nodes)!=1:fail('Full page needs one main landmark: '+key)
            if sum(n.attrs.get('id')=='archive-main' for n in doc.nodes)!=1:fail('Main target missing/duplicate: '+key)
            if 'January 2015' not in text:fail('Archive context missing: '+key)
        ids=[n.attrs['id'] for n in doc.nodes if n.attrs.get('id')]
        # The original effects wrapper uses a single frame; no repeated markup IDs added.
        oldids=[n.attrs['id'] for n in before.nodes if n.attrs.get('id')]
        newduplicates={i:c for i,c in Counter(ids).items() if c>max(1,Counter(oldids)[i])}
        if newduplicates:fail('Duplicate added IDs: '+key+' '+str(newduplicates))
        if key.startswith('interactives/') and key.rsplit('/',1)[-1].removesuffix('.html') in build.MAPS:
            name=key.rsplit('/',1)[-1].removesuffix('.html')
            if cells(text)!=cells(build.data_alternative(baseline,name)):fail('Reported map data table changed: '+key)
        if key=='interactives/data.html' and cells(text)!=cells(build.chart_alternative(original)):fail('Chart data table changed')
        # Check every transformation's output, including untouched attributes and notices.
        try:expected_html=build.transform(original,key,baseline,config)
        except ValueError as exc:fail(str(exc));continue
        if text!=expected_html:fail('Output differs from deterministic transformation: '+key)
    for key,asset in build.ASSETS.items():
        if key not in new or (output/key).read_bytes()!=(ROOT/'assets'/asset).read_bytes():fail('Shared asset differs from reviewed source: '+key)
    # Resolve only the original site's HTML resource references; external services are separate.
    for path in output.rglob('*.html'):
        key=path.relative_to(output).as_posix();doc=build.Document(build.read(path));base='https://hookedaz.cronkitenewsonline.com/'+key
        for node in doc.nodes:
            for attr in ('src','href','poster'):
                value=node.attrs.get(attr,'')
                if not value or value.startswith(('mailto:','tel:','javascript:','data:','#')):continue
                url=urlsplit(urljoin(base,value))
                if url.netloc!='hookedaz.cronkitenewsonline.com':continue
                target=unquote(url.path).lstrip('/')
                if not target or target.endswith('/'):target+='index.html'
                elif target not in new and target+'/index.html' in new:target+='/index.html'
                if target not in new:fail('Missing internal reference: '+key+' -> '+target)
    return {'failures':sorted(set(failures)),'baseline_sha256':old,'build_sha256':new,'changed_keys':sorted(k for k in old if new.get(k)!=old[k]),'added_keys':sorted(additions),'deleted_keys':sorted(set(old)-set(new))}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--baseline',type=Path,required=True);parser.add_argument('--build',type=Path,required=True);parser.add_argument('--output',type=Path,default=ROOT/'validation.json');args=parser.parse_args()
    result=validate(args.baseline,args.build);args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps({'failures':result['failures'],'changed':len(result.get('changed_keys',[])),'added':len(result.get('added_keys',[]))},indent=2));raise SystemExit(bool(result['failures']))
if __name__=='__main__':main()
