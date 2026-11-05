#!/usr/bin/env python3
"""Reproducible, fail-closed overlay over the reviewed current HookedAZ snapshot."""
from __future__ import annotations
import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlsplit, urlunsplit

ROOT=Path(__file__).resolve().parent
ASSETS={'assets/archive.css':'archive.css','assets/archive.js':'archive.js'}
MAPS={'county':('az1.js','Arizona counties'),'phoenix':('phoenix.js','Maricopa ZIP codes'),'pima':('pima.js','Pima ZIP codes'),'zipmap':('zips.js','ZIP codes'),'hosmap':('hos.js','Hospitals'),'citymapdots':('cityDots.js','Cities')}
ESC=html.escape

def read(path):return Path(path).read_text(encoding='utf-8')
def hashes(root):
    root=Path(root)
    if root.is_symlink():raise ValueError('Symlink tree root')
    result={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():raise ValueError('Symlink in tree: '+str(p))
        if p.is_file():result[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result

class Node:
    def __init__(self,tag,attrs,start,open_end,parent):
        self.tag=tag;self.attrs=dict(attrs);self.start=start;self.open_end=open_end;self.close_start=open_end;self.end=open_end;self.parent=parent

class Document(HTMLParser):
    VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self,text):
        super().__init__(convert_charrefs=True);self.text=text;self.nodes=[];self.stack=[]
        self.lines=[0]+[m.end() for m in re.finditer('\n',text)];self.feed(text)
    def position_offset(self):
        line,col=self.getpos();return self.lines[line-1]+col
    def handle_starttag(self,tag,attrs):
        start=self.position_offset();node=Node(tag,attrs,start,start+len(self.get_starttag_text()),self.stack[-1] if self.stack else None);self.nodes.append(node)
        if tag not in self.VOID:self.stack.append(node)
    def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i].tag==tag:
                node=self.stack[i];node.close_start=self.position_offset();node.end=self.text.find('>',node.close_start)+1;del self.stack[i:];break
    def inner(self,node):return self.text[node.open_end:node.close_start]
    def plain(self,node):return plain(self.inner(node))

def plain(text):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',text))).strip()
def tag(name,attrs):return '<'+name+''.join(' '+k+('="'+ESC(str(v),quote=True)+'"' if v is not None else '') for k,v in attrs.items())+'>'
def edits(text,changes):
    previous=len(text)+1
    for start,end,new in sorted(changes,reverse=True):
        if end>previous:raise ValueError('Overlapping transformation')
        text=text[:start]+new+text[end:];previous=start
    return text
def replace_nodes(text,predicate,render):
    doc=Document(text);return edits(text,[(n.start,n.end,render(doc,n)) for n in doc.nodes if predicate(n)])

def version_internal_frames(text,revision):
    """Select a fresh browser cache key for local frames; external media is immutable."""
    doc=Document(text);changes=[]
    for node in doc.nodes:
        if node.tag!='iframe' or not node.attrs.get('src'):continue
        source=urlsplit(node.attrs['src'])
        if source.scheme not in ('','http','https') or source.netloc.lower() not in ('','hookedaz.cronkitenewsonline.com'):continue
        query=[part for part in source.query.split('&') if part and unquote(part.split('=',1)[0])!='archive']
        query.append('archive='+revision)
        attrs=dict(node.attrs);attrs['src']=urlunsplit(source._replace(query='&'.join(query)))
        changes.append((node.start,node.open_end,tag('iframe',attrs)))
    return edits(text,changes)
def top_tag(text,node,**attrs):
    current=dict(node.attrs);current.update(attrs);return tag(node.tag,current)

def load_geo(path):
    match=re.fullmatch(r'\s*var\s+[A-Za-z_$][\w$]*\s*=\s*(\{.*\})\s*;?\s*',read(path),re.S)
    if not match:raise ValueError('Unrecognized static GeoJSON: '+str(path))
    result=json.loads(match[1])
    if result.get('type')!='FeatureCollection' or not isinstance(result.get('features'),list):raise ValueError('Invalid feature collection')
    return result

def table(title,headers,rows):
    return '<div class="archive-table-scroll"><table class="archive-table"><caption>'+ESC(title)+'</caption><thead><tr>'+''.join('<th scope="col">'+ESC(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<th scope="row">'+ESC(str(v))+'</th>' if i==0 else '<td>'+ESC(str(v))+'</td>' for i,v in enumerate(row))+'</tr>' for row in rows)+'</tbody></table></div>'

def data_alternative(baseline,name):
    filename,title=MAPS[name];data=load_geo(baseline/'interactives/data'/filename);rows=[]
    for feature in data['features']:
        props=feature['properties'];value=props['Overdose'] if name=='county' else props['Total']
        if not isinstance(value,(str,int,float)) or not isinstance(props['name'],str):raise ValueError('Invalid reported map value')
        rows.append((props['name'],value))
    return '<details class="archive-tables"><summary>Read '+ESC(title.lower())+' data as a table</summary>'+table(title+' — overdose cases, 2009–2013',['Location','Reported cases'],rows)+'<p>Source: Cronkite News analysis of Arizona Hospital Discharge Data, 2009–2013. Original labels and suppression values are retained.</p></details>'

def chart_alternative(text):
    match=re.search(r'var data\s*=\s*\{(.*?)\}\s*;',text,re.S)
    if not match:raise ValueError('Missing chart arrays')
    pairs=re.findall(r'(\w+)\s*:\s*(\[[^\]]*\])',match[1]);data={key:json.loads(value) for key,value in pairs}
    expected={'year','total','female','male','latino','white','other'}
    if set(data)!=expected or any(len(v)!=6 for v in data.values()):raise ValueError('Unrecognized chart arrays')
    keys=['year','total','female','male','latino','white','other']
    return '<details class="archive-tables"><summary>Read race and gender data as a table</summary>'+table('Heroin emergency-room cases in Arizona, 2009–2013',[str(data[k][0]).title() for k in keys],[[data[k][i] for k in keys] for i in range(1,6)])+'</details>'

def map_page(text,baseline,name):
    text=text.replace('http://cdn.leafletjs.com/leaflet-0.7/leaflet.js','js/leaflet.js')
    text=re.sub(r'http://\{s\}\.tile\.(?:osm|openstreetmap)\.org/\{z\}/\{x\}/\{y\}\.png','https://tile.openstreetmap.org/{z}/{x}/{y}.png',text)
    text=text.replace('maxZoom: 18,','maxZoom: 18,\n attribution: \'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors\',')
    if name=='county':
        text,n=re.subn(r'\s*var geoJsonLayer = L.geoJson\(az, \{.*?markers\.addLayer\(geoJsonLayer\);','',text,flags=re.S)
        if n!=1:raise ValueError('County repair anchor missing')
    if name in ('hosmap','citymapdots'):
        # The snapshot has no Leaflet default marker PNGs. A local DivIcon avoids
        # missing resources while retaining the original point coordinates/popups.
        text,n=re.subn(r'(var geoJsonLayer = L.geoJson\((?:hos|cities), \{)',r'''\1
            pointToLayer: function (feature, latlng) {
                return L.marker(latlng, {title: feature.properties.name + ': ' + feature.properties.Total + ' overdose cases',
                    icon: L.divIcon({className: 'archive-map-marker', html: '<span aria-hidden="true">&#9679;</span>', iconSize: [24, 24], iconAnchor: [12, 12]})});
            },''',text)
        if n!=1:raise ValueError('Point map marker anchor missing: '+name)
    title=MAPS[name][1]
    text=text.replace('<body>','<body>\n<h1 class="archive-map-title">'+ESC(title)+' overdose cases, 2009–2013</h1>')
    text=re.sub(r'<div id="(map|county)"></div>',r'<div id="\1" class="archive-map" role="region" aria-label="'+ESC(title)+r' interactive map"></div>',text)
    script="""<script>
window.archiveResizeMap = function () { if (window.map && typeof window.map.invalidateSize === 'function') window.map.invalidateSize(false); };
window.addEventListener('resize', window.archiveResizeMap);
window.addEventListener('load', window.archiveResizeMap);
</script>"""
    text=text.replace('</body>',script+data_alternative(baseline,name)+'</body>')
    return text

def close_feedback(text):
    # Remove the complete modal, including its disconnected remote script and empty form holder.
    text=replace_nodes(text,lambda n:n.attrs.get('id')=='PINpopover',lambda d,n:'')
    text=replace_nodes(text,lambda n:n.tag=='script' and 'publicinsightnetwork.org' in n.attrs.get('src',''),lambda d,n:'')
    text=replace_nodes(text,lambda n:n.attrs.get('data-target')=='#PINpopover',lambda d,n:'<p class="archive-closed">Submissions are closed for this archived project.</p>')
    text=replace_nodes(text,lambda n:n.tag=='a' and n.attrs.get('href')=='/share-your-thoughts/',lambda d,n:'<a href="/share-your-thoughts/" class="archive-status">About the closed submissions archive</a>')
    text=replace_nodes(text,lambda n:n.attrs.get('id','').startswith('pin-query-'),lambda d,n:'<p class="archive-closed">Submissions are closed. This January 2015 project no longer accepts responses.</p>')
    return text

def dispositions(text,key,config):
    if key=='resources-for-addicts-and-families/index.html':
        doc=Document(text);changes=[]
        for node in doc.nodes:
            if node.tag!='a':continue
            href=node.attrs.get('href','');reason=next((v for k,v in config['unavailable_resources'].items() if k in href),None)
            if reason:changes.append((node.start,node.end,'<span>'+doc.inner(node)+'</span> <span class="archive-status">('+ESC(reason)+')</span>'))
        text=edits(text,changes)
    if key=='index.html':
        text=replace_nodes(text,lambda n:n.tag=='a' and 'itunes.apple.com/us/app/highly-potent/' in n.attrs.get('href',''),lambda d,n:'<span>'+d.inner(n)+'</span><span class="archive-status"> (Original App Store download unavailable.)</span>')
    if key=='major-figures-throughout-heroin-history/index.html':
        text=replace_nodes(text,lambda n:n.tag=='iframe' and n.attrs.get('src')=='/interactives/player/majorfigures.html',lambda d,n:'<p class="archive-unavailable">The original history interactive is unavailable in this archive.</p>')
    return text

def image_alt(doc,node):
    src=node.attrs.get('src','')
    if 'logo_nav' in src or 'logo-invert' in src:return 'HookedAZ'
    if '/logos/n21' in src:return 'News21'
    if '/app-store' in src:return 'Apple App Store badge; download unavailable'
    # All article stills have retained adjacent publication captions.
    later=doc.text[node.open_end:]
    match=re.search(r'<p\b[^>]*class="[^"]*photo-(?:big-)?caption[^"]*"[^>]*>(.*?)</p>',later,re.S)
    if match and later.find('<img') not in range(0,match.start()):return plain(match[1])
    raise ValueError('No verified image caption for '+src)

def shared_markup(text,key):
    text=text.replace('http://fonts.googleapis.com','https://fonts.googleapis.com')
    text=text.replace('/interactives/assets/js/jquery.responsiveiframe.js','/assets/js/jquery.responsiveiframe.js')
    text=text.replace('This story is from Gun Wars, a News21 investigation of rights and regulations in America.','This story is from HookedAZ: Tracking Heroin’s Hold on Arizona')
    text=text.replace('Check out this story from News21:','Check out this story from Cronkite News:')
    text=text.replace('user-scalable=no,','').replace(', user-scalable=no','').replace('maximum-scale=1','')
    doc=Document(text);changes=[];main_seen=False
    for n in doc.nodes:
        attrs=dict(n.attrs);new_tag=n.tag;changed=False
        if n.tag=='link' and 'favicon.ico' in attrs.get('href',''):changes.append((n.start,n.end,''));continue
        if n.tag=='html' and 'lang' not in attrs:attrs['lang']='en';changed=True
        if n.tag=='img' and 'alt' not in attrs:attrs['alt']=image_alt(doc,n);changed=True
        if n.tag=='iframe' and not attrs.get('title'):
            src=attrs.get('src','');title='Embedded media for '+plain(re.search(r'<title>(.*?)</title>',text,re.S)[1]).split('|')[0].strip()
            if src.startswith('/interactives/'):title='Interactive visualization: '+src.rsplit('/',1)[-1].replace('.html','')
            if '/slideshows/' in src:title='Photo slideshow with descriptions'
            attrs['title']=title;changed=True
        if n.tag=='video' and attrs.get('id')=='snow':
            attrs.pop('autoplay',None);attrs.pop('loop',None);attrs.update({'poster':'/assets/snowfall.png','aria-hidden':'true','tabindex':'-1'});changed=True
        if attrs.get('id') in ('static-toggle','menu-toggle','static-close','menu-close'):
            new_tag='button';attrs.pop('href',None);attrs['type']='button';attrs['aria-label']='Close navigation' if 'close' in attrs['id'] else 'Open navigation';attrs['aria-controls']='static-wrapper'
            if 'toggle' in attrs['id']:attrs['aria-expanded']='false'
            changed=True
        if attrs.get('id')=='static-wrapper':attrs.update({'hidden':None,'inert':None,'role':'navigation','aria-label':'Mobile navigation'});changed=True
        if n.tag=='i' and 'fa' in attrs.get('class',''):attrs['aria-hidden']='true';changed=True
        if n.tag=='a':
            href=attrs.get('href','')
            if 'navbar-brand' in attrs.get('class',''):attrs['aria-label']='HookedAZ home';changed=True
            if 'facebook.com/sharer/' in href:attrs['aria-label']='Share this page on Facebook';changed=True
            if 'twitter.com/share' in href:attrs['aria-label']='Share this page on X';changed=True
            if href.startswith('mailto:'):attrs['aria-label']='Share this page by email';changed=True
            if doc.plain(n)=='About' and href=='#':attrs['href']='/about/';changed=True
            if attrs.get('role')=='tab':
                ident=attrs['href'].lstrip('#');attrs.update({'id':'tab-'+ident,'aria-controls':ident,'aria-selected':'true' if ident=='data' else 'false','tabindex':'0' if ident=='data' else '-1'});changed=True
            if attrs.get('data-toggle')=='collapse' and attrs.get('data-target')=='#data-nav':
                new_tag='button';attrs.update({'type':'button','aria-controls':'data-nav','aria-expanded':'false'});changed=True
        if attrs.get('role')=='main':
            if key=='index.html':attrs.pop('role')
            elif not main_seen:attrs['id']='archive-main';attrs['tabindex']='-1';main_seen=True
            else:attrs.pop('role')
            changed=True
        if attrs.get('id') in ('data','county','maricopa','pima','hos','city') and 'tab-pane' in attrs.get('class',''):
            attrs.update({'role':'tabpanel','aria-labelledby':'tab-'+attrs['id']});changed=True
        if n.tag in ('h4','h5') and 'byline' in attrs.get('class',''):new_tag='p';changed=True
        if key=='index.html':
            if n.tag=='h3' and 'proj-desc' in attrs.get('class',''):new_tag='h1';changed=True
            elif n.tag=='h1':new_tag='h2';changed=True
            elif n.tag=='h4':new_tag='p';changed=True
        elif n.tag in ('h3','h4') and not ('byline' in attrs.get('class','')):
            # Template sections are siblings under the article's topic heading.
            new_tag='h2';changed=True
        if changed:
            changes.append((n.start,n.open_end,tag(new_tag,attrs)))
            if new_tag!=n.tag and n.close_start>n.open_end:changes.append((n.close_start,n.end,'</'+new_tag+'>'))
    text=edits(text,changes)
    return text

def animation_alternative(baseline):
    source=read(baseline/'interactives/effects/effectsonMind_edge.js');strings=[]
    for m in re.finditer(r'\btext:\s*("(?:[^"\\]|\\.)*")',source):
        value=plain(json.loads(m[1]))
        if value and value not in strings:strings.append(value)
    if len(strings)<15:raise ValueError('Animation text could not be recovered')
    return '<details class="archive-alternative"><summary>Animation text</summary><p>The following text is preserved from the original 2015 animation.</p>'+''.join('<p>'+ESC(s)+'</p>' for s in strings)+'</details>'

def gallery_alternative(baseline,slug):
    path=baseline/'slideshows'/slug/(slug+'.json');data=json.loads(read(path));figures=[]
    for item in data:
        caption=plain(item['description']);src=item['image']
        if not src.startswith('/slideshows/'+slug+'/'):raise ValueError('Unexpected gallery image path')
        figures.append('<figure><img loading="lazy" src="'+ESC(src,quote=True)+'" alt="'+ESC(caption,quote=True)+'"><figcaption>'+ESC(caption)+'</figcaption></figure>')
    return '<details class="archive-alternative archive-gallery"><summary>Photo descriptions and accessible image list</summary>'+''.join(figures)+'</details>'

def transform(text,key,baseline,config):
    if not re.search(r'<meta\b[^>]*(?:charset=["\']?utf-8|charset=utf-8)',text[:1024],re.I):
        text=text.replace('<head>','<head>\n<meta charset="utf-8">',1)
    if key=='index.html':
        if len(re.findall(r'<script\b',text))-text.count('</script>')!=1:raise ValueError('Homepage script repair anchor changed')
        text=text.replace('</body>','</script>\n</body>',1)
    full='role="main"' in text
    text=close_feedback(text);text=dispositions(text,key,config)
    if key.startswith('interactives/') and key.rsplit('/',1)[-1].removesuffix('.html') in MAPS:
        text=map_page(text,baseline,key.rsplit('/',1)[-1].removesuffix('.html'))
    if key=='interactives/data.html':
        text=text.replace('bindto: \'#chart\',','bindto: \'#chart\',\n transition: {duration: window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 350},')
        text=text.replace('<span class ="tag" id = "race">View By Race</span>','<button type="button" class="tag" id="race" aria-pressed="true">View By Race</button>')
        text=text.replace('<span class ="tag" id = "gender">View By Gender</span>','<button type="button" class="tag" id="gender" aria-pressed="false">View By Gender</button>')
        text=text.replace('<div style="margin-top:100px">','<div class="archive-chart-controls" style="margin-top:1rem">')
        text=text.replace('$("#gender").click(function(){','$("#gender").click(function(){\n $("#gender").attr("aria-pressed","true"); $("#race").attr("aria-pressed","false");')
        text=text.replace('$("#race").click(function(){','$("#race").click(function(){\n $("#race").attr("aria-pressed","true"); $("#gender").attr("aria-pressed","false");')
        text=text.replace('</body>',chart_alternative(text)+'</body>')
        text=text.replace('<body>','<body><h1 class="archive-map-title">Heroin emergency-room cases in Arizona, 2009–2013</h1>')
    if key in ('how-heroin-affects-the-body/index.html','interactives/effects.html'):
        alternative=animation_alternative(baseline)
        text=replace_nodes(text,lambda n:n.tag=='iframe' and n.attrs.get('src','').endswith('effectsonMind.html'),lambda d,n:d.text[n.start:n.end]+alternative)
    if key in ('slideshows/heroin-love/index.html','slideshows/rehab/index.html'):
        slug=key.split('/')[1];text=text.replace('</body',gallery_alternative(baseline,slug)+'</body',1)
    text=shared_markup(text,key)
    text=version_internal_frames(text,config['internal_frame_revision'])
    if full:
        notice='<aside class="archive-notice" aria-label="Archive information">'+ESC(config['archive_notice'])+'</aside>'
        if key=='index.html':
            # Homepage originally had four main landmarks. One wrapper covers its entire topic.
            text=re.sub(r'\srole="main"','',text)
            text=text.replace('<div class="home-brand phototron jumbotron">','<main id="archive-main" tabindex="-1">'+notice+'<div class="home-brand phototron jumbotron">',1)
            footer=text.find('<div class="container-full" id="footer">')
            if footer<0:raise ValueError('Missing homepage footer anchor')
            text=text[:footer]+'</main>'+text[footer:]
        else:
            text=re.sub(r'(<[^>]+id="archive-main"[^>]*>)',r'\1'+notice,text,count=1)
            if not re.search(r'<h1\b',text):
                title=plain(re.search(r'<title>(.*?)</title>',text,re.S)[1]).split('|')[0].strip()
                text=text.replace(notice,notice+'<h1>'+ESC(title)+'</h1>',1)
        text=re.sub(r'(<body\b[^>]*>)',r'\1<a class="archive-skip" href="#archive-main">Skip to main content</a>',text,count=1)
    if key.endswith('index.html') and key.startswith('slideshows/'):
        # Original slideshow documents have a malformed closing body token.
        text=text.replace('</body</','</body></')
        if '</html>' not in text:text+='\n</html>\n'
    if key!='interactives/effects/effectsonMind.html':
        text=text.replace('</head>','<link rel="stylesheet" href="/assets/archive.css">\n</head>',1)
        if full:text=text.replace('</body>','<script defer src="/assets/archive.js"></script>\n</body>',1)
    return text

def build(baseline,output):
    baseline=Path(baseline);output=Path(output)
    if output.is_symlink() or output.resolve()==baseline.resolve() or output.resolve().is_relative_to(baseline.resolve()) or baseline.resolve().is_relative_to(output.resolve()) or ROOT.resolve().is_relative_to(output.resolve()):raise ValueError('Unsafe output path')
    expected=json.loads(read(ROOT/'baseline-manifest.json'))['objects'];actual=hashes(baseline)
    if actual!={k:v['sha256'] for k,v in expected.items()}:raise ValueError('Baseline differs from reviewed manifest')
    for f in (ROOT/'baseline').rglob('*'):
        if f.is_file() and f.read_bytes()!=(baseline/f.relative_to(ROOT/'baseline')).read_bytes():raise ValueError('Tracked input differs from baseline')
    if output.exists():
        existing=hashes(output)
        if existing and set(existing) not in (set(actual),set(actual)|set(ASSETS)):raise ValueError('Output is not an existing HookedAZ build')
        if any(output.iterdir()):shutil.rmtree(output)
    shutil.copytree(baseline,output,dirs_exist_ok=True)
    config=json.loads(read(ROOT/'repairs.json'))
    for f in sorted(baseline.rglob('*.html')):
        key=f.relative_to(baseline).as_posix();(output/key).write_text(transform(read(f),key,baseline,config),encoding='utf-8',newline='\n')
    for key,name in ASSETS.items():(output/key).write_bytes((ROOT/'assets'/name).read_bytes())
    return hashes(output)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--baseline',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=build(args.baseline,args.output);print(json.dumps({'files':len(result),'added_keys':sorted(set(result)-set(hashes(args.baseline)))},indent=2))
if __name__=='__main__':main()
