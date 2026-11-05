import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

try:
    import manage
except ImportError:
    manage = None

class Error(Exception):
    def __init__(self, code):
        self.response={'Error':{'Code':str(code)},'ResponseMetadata':{'HTTPStatusCode':code}}

class FakeS3:
    def __init__(self): self.objects={}; self.serial=0; self.mutations=[]; self.after_copy=None
    def seed(self,bucket,key,body,**kw):
        self.serial+=1
        row={'VersionId':str(self.serial),'Body':body,'ETag':'"'+hashlib.md5(body).hexdigest()+'"','ContentType':'text/plain','Metadata':{},'TagSet':[]}
        row.update(kw);self.objects.setdefault((bucket,key),[]).append(row);return row
    def row(self,bucket,key,vid=None):
        rows=self.objects.get((bucket,key),[])
        row=next((x for x in rows if x['VersionId']==vid),None) if vid else (rows[-1] if rows else None)
        if not row or row.get('DeleteMarker'):raise Error(404)
        return row
    def get_paginator(self,name):
        client=self
        class Pager:
            def paginate(self,Bucket,Prefix):
                yield {'Contents':[{'Key':k,'Size':len(v[-1]['Body']),'ETag':v[-1]['ETag']} for (b,k),v in client.objects.items() if b==Bucket and k.startswith(Prefix) and not v[-1].get('DeleteMarker')]}
        return Pager()
    def list_objects_v2(self,**kw):
        keys=[k for b,k in self.objects if b==kw['Bucket'] and k.startswith(kw['Prefix'])]
        return {'KeyCount':len(keys),'Contents':[{'Key':k} for k in keys]}
    def head_object(self,Bucket,Key,VersionId=None):return {k:v for k,v in self.row(Bucket,Key,VersionId).items() if k not in ('Body','TagSet')}
    def get_object(self,Bucket,Key,VersionId=None):return {'Body':io.BytesIO(self.row(Bucket,Key,VersionId)['Body'])}
    def get_object_tagging(self,Bucket,Key,VersionId=None):return {'TagSet':self.row(Bucket,Key,VersionId)['TagSet']}
    def get_bucket_versioning(self,**kw):return {'Status':'Enabled'}
    def get_bucket_website(self,**kw):return {'IndexDocument':{'Suffix':'index.html'}}
    def copy_object(self,**kw):
        s=kw['CopySource'];r=self.row(s['Bucket'],s['Key'],s['VersionId']);self.mutations.append(('copy',kw))
        out=self.seed(kw['Bucket'],kw['Key'],r['Body'],**{k:v for k,v in r.items() if k not in ('Body','VersionId','ETag')})
        if self.after_copy: hook,self.after_copy=self.after_copy,None;hook()
        return out
    def put_object(self,**kw):
        from urllib.parse import parse_qsl
        try:r=self.row(kw['Bucket'],kw['Key'])
        except Error:r=None
        if kw.get('IfNoneMatch')=='*' and r:raise Error(412)
        if 'IfMatch' in kw and (r is None or r['ETag']!=kw['IfMatch']):raise Error(412)
        self.mutations.append(('put',kw))
        if isinstance(kw.get('Expires'),str):
            import datetime
            kw['Expires']=datetime.datetime.fromisoformat(kw['Expires'])
        return self.seed(kw['Bucket'],kw['Key'],kw['Body'],TagSet=[{'Key':k,'Value':v} for k,v in parse_qsl(kw.get('Tagging',''),keep_blank_values=True)],**{k:v for k,v in kw.items() if k not in ('Bucket','Key','Body','Tagging','IfMatch','IfNoneMatch')})
    def delete_object(self,**kw):
        r=self.row(kw['Bucket'],kw['Key'])
        if r['ETag']!=kw['IfMatch']:raise Error(412)
        self.serial+=1;row={'VersionId':str(self.serial),'DeleteMarker':True,'Body':b'','ETag':'deleted'};self.objects[(kw['Bucket'],kw['Key'])].append(row);self.mutations.append(('delete',kw));return row

class FakeCF:
    def __init__(self):self.calls=[]
    def get_distribution_config(self,**kw):return {'ETag':'config','DistributionConfig':{'Aliases':{'Items':['hookedaz.cronkitenewsonline.com']},'Origins':{'Items':[{'DomainName':'hookedaz.cronkitenewsonline.com.s3-website-us-west-2.amazonaws.com','OriginPath':''}]}}}
    def create_invalidation(self,**kw):self.calls.append(kw);return {'Invalidation':{'Id':'I1','Status':'InProgress'}}

class Operations(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(manage,'manage implementation absent')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.baseline=self.root/'baseline';self.baseline.mkdir();self.s3=FakeS3();self.cf=FakeCF()
        for k,b in {'index.html':b'old home','photo.jpg':b'photo'}.items():
            (self.baseline/k).write_bytes(b);self.s3.seed(manage.BUCKET,k,b,CacheControl='max-age=77',Metadata={'original':'yes'},TagSet=[{'Key':'site','Value':'HookedAZ'}])
        self.state=self.root/'phase1'
    def backup(self):
        proof=[{'key':p.name,'status':200,'sha256':manage.sha(p.read_bytes()),'matches_s3':True} for p in self.baseline.iterdir()]
        return manage.Backup(self.state,self.baseline,self.s3,self.cf,proof).run('before-repairs')
    def test_backup_pins_verifies_and_writes_only_destination(self):
        r=self.backup();self.assertEqual(r['status'],'COMPLETE');self.assertEqual(r['object_count'],2);self.assertTrue(r['source_current_versions_unchanged']);self.assertTrue(all(kw['Bucket']==manage.DEST_BUCKET for _,kw in self.s3.mutations));self.assertIn('hookedaz.cronkitenewsonline.com/',r['backup_uri'])
        manifest=json.loads((self.state/'backup/manifest.json').read_text());self.assertTrue(all(x['verified'] for x in manifest['objects']));self.assertTrue((self.state/'backup/hosting.json').exists())
    def test_backup_requires_versioning_before_any_write(self):
        self.s3.get_bucket_versioning=lambda **kw:{}
        with self.assertRaisesRegex(RuntimeError,"versioning"):self.backup()
        self.assertFalse(self.s3.mutations)
    def test_backup_refuses_local_drift_before_destination_write(self):
        (self.baseline/'index.html').write_bytes(b'wrong')
        with self.assertRaisesRegex(RuntimeError,'baseline|drift'):self.backup()
        self.assertFalse(self.s3.mutations)
    def test_backup_detects_same_body_new_version(self):
        self.s3.after_copy=lambda:self.s3.seed(manage.BUCKET,'index.html',b'old home')
        with self.assertRaisesRegex(RuntimeError,'version|changed'):self.backup()
        self.assertFalse((self.state/'backup/receipt.json').exists())
    def test_backup_detects_tag_drift(self):
        self.s3.after_copy=lambda:self.s3.row(manage.BUCKET,'photo.jpg').update(TagSet=[{'Key':'changed','Value':'yes'}])
        with self.assertRaisesRegex(RuntimeError,'tags|changed|verification'):self.backup()
    def test_refuses_to_overwrite_backup(self):
        self.backup();before=len(self.s3.mutations)
        with self.assertRaises(RuntimeError):self.backup()
        self.assertEqual(before,len(self.s3.mutations))
    def candidate(self):
        build=self.root/'candidate';build.mkdir()
        for k,b in {'index.html':b'new home','photo.jpg':b'photo','archive-assets/archive.css':b'css'}.items():
            p=build/k;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        validation=self.root/'validation.json';validation.write_text(json.dumps({'failures':[],'build_sha256':manage.guard.tree_hashes(build)}));review=self.root/'review.md';review.write_text('## Assessment: APPROVED\nValidation SHA-256: '+manage.sha(validation.read_bytes())+'\nBuild manifest SHA-256: '+manage.manifest_digest(manage.guard.tree_hashes(build))+'\n');return build,validation,review
    def release(self):
        self.backup();b,v,r=self.candidate();manage.prepare(self.state,b,v,r);return manage.release_for(self.state,self.s3,self.cf)
    def test_exact_scope_rejects_late_build_and_preserves_original_headers(self):
        rel=self.release();m=rel.preflight();self.assertEqual(len(m['objects']),2);rel.upload();self.assertEqual(self.s3.row(manage.BUCKET,'index.html')['CacheControl'],'max-age=77');self.assertEqual(self.s3.row(manage.BUCKET,'index.html')['Metadata']['original'],'yes');self.assertTrue(all(x['passed'] for x in rel.verify()));self.assertEqual(self.cf.calls[-1]['InvalidationBatch']['Paths']['Items'],['/','/archive-assets/archive.css','/index.html'])
        self.assertEqual([kw['Key'] for action,kw in self.s3.mutations if action=='put' and kw['Bucket']==manage.BUCKET],['archive-assets/archive.css','index.html'])
    def test_restore_preserves_additions_without_any_deletion(self):
        rel=self.release();rel.preflight();rel.upload();rel.restore();self.assertEqual(self.s3.row(manage.BUCKET,'index.html')['Body'],b'old home');self.assertEqual(self.s3.row(manage.BUCKET,'archive-assets/archive.css')['Body'],b'css');self.assertFalse([kw for action,kw in self.s3.mutations if action=='delete']);self.assertGreater(len(self.s3.objects[(manage.BUCKET,'index.html')]),1)
    def test_drift_blocks_upload_before_any_production_write(self):
        rel=self.release();rel.preflight();self.s3.seed(manage.BUCKET,'photo.jpg',b'photo')
        with self.assertRaisesRegex(RuntimeError,'Concurrent|version'):rel.upload()
        self.assertFalse([kw for a,kw in self.s3.mutations if kw['Bucket']==manage.BUCKET])
    def test_scope_tampering_rejected(self):
        rel=self.release();p=self.state/'reviewed-scope.json';s=json.loads(p.read_text());s['added_keys']=[];p.write_text(json.dumps(s))
        with self.assertRaises(RuntimeError):manage.release_for(self.state,self.s3,self.cf).preflight()

    def test_baseline_mode_verifies_all_current_objects_without_writes(self):
        result=manage.baseline_verify(self.baseline,self.s3)
        self.assertEqual(result['object_count'],2);self.assertTrue(result['passed']);self.assertFalse(self.s3.mutations)
        self.s3.seed(manage.BUCKET,'index.html',b'wrong')
        with self.assertRaisesRegex(RuntimeError,'baseline|drift'):manage.baseline_verify(self.baseline,self.s3)
    def test_cli_has_only_explicit_guarded_modes(self):
        import subprocess
        result=subprocess.run([sys.executable,str(Path(manage.__file__)),'--help'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0);self.assertIn('baseline',result.stdout);self.assertIn('backup',result.stdout);self.assertIn('deploy',result.stdout);self.assertIn('restore',result.stdout)
    def test_rejected_review_cannot_smuggle_approval_marker(self):
        self.backup();b,v,r=self.candidate();r.write_text(r.read_text().replace('## Assessment: APPROVED','## Assessment: CHANGES_REQUIRED\nPrior text: Assessment: APPROVED'))
        with self.assertRaisesRegex(RuntimeError,'review|Review'):manage.prepare(self.state,b,v,r)

    def test_review_must_bind_exact_validation_and_build_manifest(self):
        self.backup();b,v,r=self.candidate();r.write_text('## Assessment: APPROVED\n')
        with self.assertRaisesRegex(RuntimeError,'review|Review'):manage.prepare(self.state,b,v,r)
        self.assertFalse((self.state/'build').exists())
    def test_remote_backup_body_tamper_blocks_production_preflight(self):
        rel=self.release();m=json.loads((self.state/'backup/manifest.json').read_text());row=m['objects'][0]
        self.s3.row(manage.DEST_BUCKET,row['destination_key'],row['destination_version_id'])['Body']=b'corrupt'
        with self.assertRaisesRegex(RuntimeError,'backup|Backup'):rel.preflight()
        self.assertFalse([kw for action,kw in self.s3.mutations if kw['Bucket']==manage.BUCKET])
    def test_timestamp_headers_survive_backup_and_release_roundtrip(self):
        import datetime
        expiry=datetime.datetime(2027,1,1,tzinfo=datetime.timezone.utc)
        self.s3.row(manage.BUCKET,'index.html')['Expires']=expiry
        rel=self.release();rel.preflight();rel.upload();self.assertTrue(all(r['passed'] for r in rel.verify()))
    def test_empty_tag_values_preserved(self):
        self.s3.row(manage.BUCKET,'index.html')['TagSet']=[{'Key':'empty','Value':''}]
        rel=self.release();rel.preflight();rel.upload();self.assertEqual(self.s3.row(manage.BUCKET,'index.html')['TagSet'],[{'Key':'empty','Value':''}]);self.assertTrue(all(r['passed'] for r in rel.verify()))

    def test_backup_rejects_correct_alias_with_wrong_origin(self):
        self.cf.get_distribution_config=lambda **kw:{'DistributionConfig':{'Aliases':{'Items':[manage.BUCKET]},'Origins':{'Items':[{'DomainName':'other-bucket.s3.amazonaws.com','OriginPath':''}]}}}
        with self.assertRaisesRegex(RuntimeError,'origin'):self.backup()
        self.assertFalse(self.s3.mutations)
    def test_backup_remote_manifest_tamper_blocks_preflight(self):
        rel=self.release();receipt=json.loads((self.state/'backup/receipt.json').read_text());key=receipt['manifest_uri'].removeprefix('s3://'+manage.DEST_BUCKET+'/')
        self.s3.row(manage.DEST_BUCKET,key,receipt['manifest_version_id'])['Body']=b'{}'
        with self.assertRaisesRegex(RuntimeError,'manifest|backup|Backup'):rel.preflight()
    def test_deploy_refuses_terminal_restored_release(self):
        rel=self.release();rel.preflight();rel.upload();rel.restore()
        with self.assertRaisesRegex(RuntimeError,'restor|rolled'):rel.upload()

    def test_backup_requires_correct_distribution_alias(self):
        self.cf.get_distribution_config=lambda **kw:{'DistributionConfig':{'Aliases':{'Items':['other.example']}}}
        with self.assertRaisesRegex(RuntimeError,'distribution|alias'):self.backup()
        self.assertFalse(self.s3.mutations)
    def test_backup_rejects_pinned_metadata_drift(self):
        self.s3.after_copy=lambda:self.s3.row(manage.BUCKET,'index.html').update(Metadata={'changed':'true'})
        with self.assertRaisesRegex(RuntimeError,'changed|verification'):self.backup()
        self.assertFalse((self.state/'backup/receipt.json').exists())
    def test_route_aliases_included_in_invalidation(self):
        rel=self.release();b=self.state/'build';(b/'story').mkdir();(b/'story/index.html').write_bytes(b'story')
        # Prepare a fresh exact reviewed release, rather than mutate prepared evidence.
        import shutil
        shutil.rmtree(b);(self.state/'reviewed-scope.json').unlink();shutil.rmtree(self.state/'repair');(self.state/'review.md').unlink()
        build,v,r=self.candidate_reuse();(build/'story').mkdir();(build/'story/index.html').write_bytes(b'story')
        v.write_text(json.dumps({'failures':[],'build_sha256':manage.guard.tree_hashes(build)}));r.write_text('## Assessment: APPROVED\nValidation SHA-256: '+manage.sha(v.read_bytes())+'\nBuild manifest SHA-256: '+manage.manifest_digest(manage.guard.tree_hashes(build))+'\n')
        manage.prepare(self.state,build,v,r);rel=manage.release_for(self.state,self.s3,self.cf);rel.preflight();rel.upload()
        paths=self.cf.calls[-1]['InvalidationBatch']['Paths']['Items'];self.assertTrue({'/story','/story/','/story/index.html'}<=set(paths));self.assertNotIn('/*',paths)
    def candidate_reuse(self):
        import shutil
        shutil.rmtree(self.root/'candidate');return self.candidate()
    def test_preflight_rejects_source_headers_changed_under_same_version(self):
        rel=self.release();self.s3.row(manage.BUCKET,'photo.jpg')['CacheControl']='wrong'
        with self.assertRaisesRegex(RuntimeError,'metadata|headers|changed|backup'):rel.preflight()
    def test_symlink_and_path_traversal_rejected(self):
        self.backup();b,v,r=self.candidate();(b/'leak').symlink_to('/etc/hosts')
        with self.assertRaisesRegex(RuntimeError,'Symlink'):manage.prepare(self.state,b,v,r)
        with self.assertRaisesRegex(RuntimeError,'Unsafe'):manage.guard.checked_key('../other')
    def test_public_checks_directory_routes_and_real_missing_control(self):
        self.release();requested=[]
        def opener(req,timeout):
            requested.append(req.full_url)
            if '__hookedaz_missing_release_check__' in req.full_url:raise __import__('urllib.error').error.HTTPError(req.full_url,404,'missing',{},None)
            key=req.full_url.removeprefix(manage.BASE) or 'index.html';body=(self.state/'build'/key).read_bytes()
            class Response(io.BytesIO):status=200
            return Response(body)
        report=manage.public(self.state,opener=opener);self.assertTrue(report['passed']);self.assertIn(manage.BASE,requested)


class CredentialCacheTests(unittest.TestCase):
    def test_provider_chain_gets_read_through_cache_without_secret_output(self):
        import contextlib
        import types
        disk={'existing':{'Credentials':{'SecretAccessKey':'test-secret'}}}
        registrations=[];received=[]
        session=types.SimpleNamespace(register_component=lambda *a:registrations.append(a))
        def resolver_factory(s,cache,region_name):
            self.assertIs(s,session);self.assertEqual(region_name,'us-west-2');self.assertEqual(cache['existing'],disk['existing']);received.append(cache);return 'resolver'
        output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
            manage.configure_credential_cache(session,resolver_factory=resolver_factory,cache_factory=lambda p:disk)
        self.assertEqual(output.getvalue(),'');self.assertEqual(registrations,[('credential_provider','resolver')]);received[0]['refreshed']={'secret':'new-secret'};self.assertNotIn('refreshed',disk);self.assertIn('refreshed',received[0])
    def test_cache_reads_existing_cli_entry_and_keeps_new_entries_memory_only(self):
        disk={'cached':{'secret':'existing'}};cache=manage.ReadThroughCredentialCache(disk)
        self.assertIn('cached',cache);self.assertEqual(cache['cached'],disk['cached']);cache['new']={'secret':'new'};self.assertEqual(cache['new'],{'secret':'new'});self.assertEqual(disk,{'cached':{'secret':'existing'}})

if __name__=='__main__':unittest.main()
