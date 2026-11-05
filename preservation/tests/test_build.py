"""Regression and preservation contracts against the real deployed snapshot."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
import subprocess
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT.parents[1] / 'live-s3'

class Tags(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.tags=[]; self.feed(text)
    def handle_starttag(self,tag,attrs): self.tags.append((tag,dict(attrs)))

def load(name):
    path=ROOT/(name+'.py')
    if not path.exists(): return None
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module; spec.loader.exec_module(module); return module

class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder=load('build');cls.validator=load('validate');cls.temp=tempfile.TemporaryDirectory()
        cls.output=Path(cls.temp.name)/'site'
        if cls.builder: cls.builder.build(BASELINE,cls.output)
        else: cls.output=BASELINE
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def text(self,key):return (self.output/key).read_text()
    def test_archive_context_and_retired_feedback(self):
        for f in BASELINE.rglob('*.html'):
            key=f.relative_to(BASELINE);text=self.text(key)
            self.assertNotIn('pinform.js',text,str(key))
            self.assertNotIn('data-target="#PINpopover"',text,str(key))
            if 'role="main"' in f.read_text(): self.assertIn('January 2015',text,str(key))
        self.assertIn('Submissions are closed',self.text('share-your-thoughts/index.html'))
    def test_maps_bootstrap_tiles_and_county_legend(self):
        for key in ('hosmap','citymapdots','county','phoenix','pima','zipmap'):
            text=self.text('interactives/'+key+'.html')
            self.assertNotIn('http://',text)
            self.assertIn('https://tile.openstreetmap.org/{z}/{x}/{y}.png',text)
            self.assertIn('OpenStreetMap',text)
            self.assertIn('archiveResizeMap',text)
        for key in ('hosmap','citymapdots'):self.assertIn('src="js/leaflet.js"',self.text('interactives/'+key+'.html'))
        for key in ('hosmap','citymapdots'):
            self.assertIn('L.divIcon',self.text('interactives/'+key+'.html'))
            self.assertIn('pointToLayer',self.text('interactives/'+key+'.html'))
        self.assertNotIn('markers.addLayer',self.text('interactives/county.html'))
        self.assertIn('legend.addTo(map)',self.text('interactives/county.html'))
    def test_menu_semantics_and_mobile_about(self):
        text=self.text('index.html');tags=Tags(text).tags
        buttons=[a for t,a in tags if t=='button' and a.get('id') in ('static-toggle','menu-toggle')]
        self.assertTrue(buttons)
        self.assertTrue(all(a.get('aria-controls')=='static-wrapper' and a.get('aria-expanded')=='false' for a in buttons))
        panel=[a for t,a in tags if a.get('id')=='static-wrapper'][0]
        self.assertIn('hidden',panel);self.assertIn('inert',panel)
        self.assertNotRegex(text,r'<a[^>]+href="#"[^>]*>About</a>')
        self.assertIn('href="#archive-main"',text)
        self.assertEqual(sum(a.get('role')=='main' or t=='main' for t,a in tags),1)
        self.assertEqual(sum(t=='h1' for t,a in tags),1)
    def test_internal_iframes_have_stable_revision_and_valid_original_paths(self):
        count=0
        for path in self.output.rglob('*.html'):
            key=path.relative_to(self.output).as_posix()
            base='https://hookedaz.cronkitenewsonline.com/'+key
            for tag,attrs in Tags(path.read_text()).tags:
                if tag!='iframe' or not attrs.get('src'):continue
                resolved=urlsplit(urljoin(base,attrs['src']))
                if resolved.netloc!='hookedaz.cronkitenewsonline.com':continue
                self.assertEqual(parse_qs(resolved.query).get('archive'),['20261105-r2'],key)
                target=resolved.path.lstrip('/')
                if target.endswith('/'):target+='index.html'
                self.assertTrue((self.output/target).is_file(),key+' '+target)
                count+=1
        self.assertEqual(count,10)
    def test_frame_revision_preserves_other_queries_fragments_and_external_hosts(self):
        self.assertIsNotNone(self.builder)
        transform=getattr(self.builder,'version_internal_frames',None)
        self.assertIsNotNone(transform,'Missing same-site frame versioning')
        source='<iframe src="effects/effectsonMind.html?mode=full%20text&amp;view=1#stage"></iframe><iframe src="https://hookedaz.cronkitenewsonline.com/interactives/data.html?archive=old&amp;x=1"></iframe><iframe src="https://hookedaz.cronkitenewsonline.com.evil.test/video?x=1"></iframe><iframe src="https://www.youtube.com/embed/unchanged?si=abc"></iframe>'
        result=transform(source,'20261105-r2')
        sources=[a['src'] for t,a in Tags(result).tags if t=='iframe']
        self.assertEqual(sources,[
            'effects/effectsonMind.html?mode=full%20text&view=1&archive=20261105-r2#stage',
            'https://hookedaz.cronkitenewsonline.com/interactives/data.html?x=1&archive=20261105-r2',
            'https://hookedaz.cronkitenewsonline.com.evil.test/video?x=1',
            'https://www.youtube.com/embed/unchanged?si=abc'])
        self.assertEqual(transform(result,'20261105-r2'),result)
    def test_all_inline_scripts_parse_and_controller_is_executable_script(self):
        import re
        for f in BASELINE.rglob('*.html'):
            key=f.relative_to(BASELINE);text=self.text(key)
            self.assertEqual(len(re.findall(r'<script\b',text)),text.count('</script>'),str(key))
            for index,script in enumerate(re.findall(r'<script\b[^>]*>(.*?)</script>',text,re.S)):
                result=subprocess.run(['node','-e','new (require("node:vm").Script)(require("node:fs").readFileSync(0,"utf8"))'],input=script,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,str(key)+' script '+str(index)+' '+result.stderr[:300])
        self.assertIn('src="/assets/archive.js"',self.text('index.html'))
    def test_static_alternatives_names_zoom(self):
        for f in BASELINE.rglob('*.html'):
            key=f.relative_to(BASELINE);text=self.text(key);tags=Tags(text).tags
            self.assertNotIn('user-scalable=no',text,str(key))
            self.assertNotIn('maximum-scale=1',text,str(key))
            for tag,attrs in tags:
                if tag=='img':self.assertIn('alt',attrs,str(key))
                if tag=='iframe':self.assertTrue(attrs.get('title'),str(key))
        for slug in ('heroin-love','rehab'):
            text=self.text('slideshows/'+slug+'/index.html')
            self.assertIn('Photo descriptions',text);self.assertIn('<figcaption>',text)
        text=self.text('how-heroin-affects-the-body/index.html')
        self.assertIn('Animation text',text)
    def test_every_html_declares_utf8_before_new_archival_text(self):
        for f in BASELINE.rglob('*.html'):
            key=f.relative_to(BASELINE);tags=Tags(self.text(key)[:1024]).tags
            self.assertTrue(any(t=='meta' and (a.get('charset','').lower()=='utf-8' or 'charset=utf-8' in a.get('content','').lower()) for t,a in tags),str(key))
    def test_resource_and_download_dispositions(self):
        text=self.text('resources-for-addicts-and-families/index.html')
        bad=('drugfreeaz.org','flagcasa.org','greenleesubstanceawareness.org','navajocountydrugproject.com','theagapecenter.com','addictionwithdrawal.com','addictionsearch.com','Hooked-Resource-Book-Final.pdf')
        for t,a in Tags(text).tags:
            if t=='a':self.assertFalse(any(x in a.get('href','') for x in bad),a)
        self.assertIn('historical',text.lower());self.assertIn('unavailable',text.lower())
        self.assertNotIn('href="https://itunes.apple.com',self.text('index.html'))
        self.assertIn('unavailable',self.text('major-figures-throughout-heroin-history/index.html').lower())
    def test_chart_buttons_and_exact_data_tables(self):
        text=self.text('interactives/data.html');tags=Tags(text).tags
        self.assertEqual({a.get('id') for t,a in tags if t=='button'}, {'race','gender'})
        self.assertIn('aria-pressed="true"',text)
        self.assertIn('<caption>',text);self.assertIn('561',text)
        for key in ('county','phoenix','pima','zipmap','hosmap','citymapdots'):
            text=self.text('interactives/'+key+'.html')
            self.assertIn('<caption>',text,key);self.assertIn('scope="col"',text,key)
        self.assertIn('fewer than 11',self.text('interactives/county.html'))
    def test_mobile_data_disclosure_is_native_button(self):
        tags=Tags(self.text('data/index.html')).tags
        toggles=[a for t,a in tags if t=='button' and a.get('data-toggle')=='collapse']
        self.assertEqual(len(toggles),1)
        self.assertTrue(toggles[0].get('aria-controls'));self.assertEqual(toggles[0].get('aria-expanded'),'false')
    def test_hero_text_has_opaque_contrast_surface(self):
        css=(self.output/'assets/archive.css').read_text()
        self.assertIn('.home-brand .overlay h1, .home-brand .overlay p',css)
        self.assertIn('background: var(--uds-color-base-white)',css)
        self.assertIn('text-shadow: none !important',css)
    def test_decorative_hero_is_static_with_original_poster(self):
        tags=Tags(self.text('index.html')).tags
        video=[a for t,a in tags if t=='video' and a.get('id')=='snow'][0]
        self.assertNotIn('autoplay',video);self.assertNotIn('loop',video)
        self.assertEqual(video.get('poster'),'/assets/snowfall.png')
    def test_animation_alternative_is_adjacent_to_frame_inside_main(self):
        text=self.text('how-heroin-affects-the-body/index.html')
        self.assertLess(text.index('<summary>Animation text'),text.index('id="footer"'))
    def test_original_keys_binaries_data_and_external_media_preserved(self):
        original={str(f.relative_to(BASELINE)):f for f in BASELINE.rglob('*') if f.is_file()}
        for key,f in original.items():
            self.assertTrue((self.output/key).is_file(),key)
            if f.suffix!='.html':self.assertEqual(f.read_bytes(),(self.output/key).read_bytes(),key)
            else:
                old=[a for t,a in Tags(f.read_text()).tags if t=='iframe' and any(d in a.get('src','') for d in ('youtube.com','vimeo.com','soundcloud.com'))]
                new=[a for t,a in Tags(self.text(key)).tags if t=='iframe']
                for attrs in old:
                    self.assertTrue(any(all(candidate.get(k)==v for k,v in attrs.items()) for candidate in new),key)
    def test_validation_rejects_media_drift_missing_prose_and_suppressed_count(self):
        self.assertIsNotNone(self.validator,'Missing preservation validator')
        mutations=[('documentary/index.html','HI2yh2kKfmM','wrongVideo'),
                   ('relentless-cycle-of-addiction-often-begins-in-teenage-years/index.html','<p>','<p>REMOVED ORIGINAL '),
                   ('interactives/county.html','fewer than 11','11')]
        for key,old,new in mutations:
            path=self.output/key;raw=path.read_bytes();text=raw.decode()
            self.assertIn(old,text)
            if 'REMOVED' in new:
                import re
                text=re.sub(r'<p>.*?</p>','',text,count=1,flags=re.S)
            else:text=text.replace(old,new,1)
            path.write_text(text)
            try:self.assertTrue(self.validator.validate(BASELINE,self.output)['failures'],key)
            finally:path.write_bytes(raw)
    def test_builder_rejects_drift_and_output_symlink(self):
        self.assertIsNotNone(self.builder,'Missing guarded builder')
        with tempfile.TemporaryDirectory() as d:
            baseline=Path(d)/'source';shutil.copytree(BASELINE,baseline)
            (baseline/'index.html').write_text('Changed live source')
            with self.assertRaises(ValueError):self.builder.build(baseline,Path(d)/'out')
            (baseline/'index.html').write_bytes((BASELINE/'index.html').read_bytes())
            target=Path(d)/'link';target.symlink_to(baseline,target_is_directory=True)
            with self.assertRaises(ValueError):self.builder.build(BASELINE,target)
    def test_deterministic_manifest_and_clean_validation(self):
        self.assertIsNotNone(self.builder,'Missing deterministic builder')
        other=Path(self.temp.name)/'second';self.builder.build(BASELINE,other)
        digest=lambda p:{str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*') if f.is_file()}
        self.assertEqual(digest(self.output),digest(other))
        result=self.validator.validate(BASELINE,self.output)
        self.assertEqual(result['failures'],[])

if __name__=='__main__':unittest.main()
