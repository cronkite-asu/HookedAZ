#!/usr/bin/env python3
"""HookedAZ version-pinned backup and exact reviewed selective release adapter.

No bucket/distribution configuration, permission or permanent-delete operations.
Legacy guards are loaded in isolated modules; original tools are never edited.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import datetime
import hashlib
import importlib.util
import json
import mimetypes
import re
from pathlib import Path
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT.parent
BUCKET='hookedaz.cronkitenewsonline.com'
DEST_BUCKET='datasync-efs-shared-1.jmc.asu.edu'
DISTRIBUTION='E2FBUY3UNH70WK'
BASE='https://hookedaz.cronkitenewsonline.com/'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

guard=load('hookedaz_release_core',Path(__file__).with_name('_release_guard.py'))
guard.BUCKET=BUCKET;guard.PREFIX='';guard.DISTRIBUTION=DISTRIBUTION

sha=guard.digest
write=guard.write_json


HEAD_FIELDS=guard.HEAD_FIELDS+('Metadata',)

def serialize(value):return json.dumps(value,indent=2,sort_keys=True,default=lambda x:x.isoformat()).encode()+b'\n'
def canonical(value):return json.loads(serialize(value))
def metadata(head):return canonical({k:head[k] for k in HEAD_FIELDS if k in head})
def read_version(s3,bucket,key,version):
    stream=s3.get_object(Bucket=bucket,Key=key,VersionId=version)['Body']
    try:return stream.read()
    finally:stream.close()
def compare_inventory(before,after):
    if before!=after:raise RuntimeError('Current source inventory changed')
def manifest_digest(hashes):return sha(json.dumps(hashes,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('utf-8'))
def verify_distribution(cf):
    result=cf.get_distribution_config(Id=DISTRIBUTION)
    config=result.get('DistributionConfig',{})
    if BUCKET not in config.get('Aliases',{}).get('Items',[]):raise RuntimeError('Wrong distribution alias')
    origins=config.get('Origins',{}).get('Items',[])
    expected=BUCKET+'.s3-website-us-west-2.amazonaws.com'
    if len(origins)!=1 or origins[0].get('DomainName')!=expected or origins[0].get('OriginPath','')!='':raise RuntimeError('Wrong distribution origin')
    return result

def read_json(path):return json.loads(Path(path).read_text())
def tags(s3,bucket,key,version):return sorted(s3.get_object_tagging(Bucket=bucket,Key=key,VersionId=version)['TagSet'],key=lambda x:x['Key'])
def inventory(s3,bucket):
    return {guard.checked_key(x['Key']):{'Size':x['Size'],'ETag':x['ETag']} for p in s3.get_paginator('list_objects_v2').paginate(Bucket=bucket,Prefix='') for x in p.get('Contents',[])}
def parallel(fn,items):
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:return list(pool.map(fn,items))

class Backup:
    def __init__(self,state,baseline,s3,cf,public_proof):
        self.state=Path(state);self.baseline=Path(baseline);self.s3=s3;self.cf=cf;self.output=self.state/'backup';self.public_proof=public_proof
    def run(self,label):
        if label!='before-repairs':raise RuntimeError('Unknown backup stage')
        if self.output.exists():raise RuntimeError('Backup directory exists; retain earlier attempt and choose a fresh phase directory')
        for bucket in (BUCKET,DEST_BUCKET):
            if self.s3.get_bucket_versioning(Bucket=bucket).get('Status')!='Enabled':raise RuntimeError('Both buckets require enabled versioning')
        hosting=verify_distribution(self.cf)
        hashes=guard.tree_hashes(self.baseline);initial=inventory(self.s3,BUCKET)
        if not hashes or set(hashes)!=set(initial) or any((self.baseline/k).stat().st_size!=v['Size'] for k,v in initial.items()):raise RuntimeError('Local baseline differs from source inventory')
        public_hashes={r['key']:r['sha256'] for r in self.public_proof if r.get('status')==200 and (r.get('matches_s3') is True or r.get('passed') is True)}
        if any(public_hashes.get(k)!=v for k,v in hashes.items()):raise RuntimeError('Public baseline proof does not match source baseline')
        prefix=BUCKET+'/'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+label+'-'+uuid.uuid4().hex[:12]+'/'
        if self.s3.list_objects_v2(Bucket=DEST_BUCKET,Prefix=prefix,MaxKeys=1).get('KeyCount',0):raise RuntimeError('Backup destination already occupied')
        def pin(key):
            head=self.s3.head_object(Bucket=BUCKET,Key=key);vid=guard.valid_version(head.get('VersionId'));body=read_version(self.s3,BUCKET,key,vid)
            if sha(body)!=hashes[key] or len(body)!=initial[key]['Size'] or head['ETag']!=initial[key]['ETag']:raise RuntimeError('Source baseline content drift: '+key)
            return {'relative_key':key,'source_key':key,'source_version_id':vid,'source_etag':head['ETag'],'destination_key':prefix+'site/'+key,'bytes':len(body),'sha256':sha(body),'metadata':metadata(head),'tags':tags(self.s3,BUCKET,key,vid)}
        pinned=parallel(pin,sorted(initial))
        self.output.mkdir(parents=True)
        write(self.output/'pinned-source.json',{'destination_prefix':prefix,'objects':pinned},exclusive=True)
        hosting={'cloudfront':hosting,'website':self.s3.get_bucket_website(Bucket=BUCKET),'source_versioning':self.s3.get_bucket_versioning(Bucket=BUCKET),'destination_versioning':self.s3.get_bucket_versioning(Bucket=DEST_BUCKET)}
        write(self.output/'hosting.json',hosting,exclusive=True)
        def copy(row):
            response=self.s3.copy_object(Bucket=DEST_BUCKET,Key=row['destination_key'],CopySource={'Bucket':BUCKET,'Key':row['source_key'],'VersionId':row['source_version_id']},CopySourceIfMatch=row['source_etag'],MetadataDirective='COPY',TaggingDirective='COPY')
            vid=guard.valid_version(response.get('VersionId'));head=self.s3.head_object(Bucket=DEST_BUCKET,Key=row['destination_key'],VersionId=vid);body=read_version(self.s3,DEST_BUCKET,row['destination_key'],vid)
            if sha(body)!=row['sha256'] or len(body)!=row['bytes'] or metadata(head)!=row['metadata'] or tags(self.s3,DEST_BUCKET,row['destination_key'],vid)!=row['tags']:raise RuntimeError('Backup verification failed: '+row['relative_key'])
            return dict(row,destination_version_id=vid,verified=True)
        copied=parallel(copy,pinned)
        def current(row):
            head=self.s3.head_object(Bucket=BUCKET,Key=row['source_key'])
            if guard.valid_version(head.get('VersionId'))!=row['source_version_id'] or metadata(head)!=row['metadata'] or tags(self.s3,BUCKET,row['source_key'],row['source_version_id'])!=row['tags']:raise RuntimeError('Source version, metadata or tags changed: '+row['source_key'])
        compare_inventory(initial,inventory(self.s3,BUCKET));parallel(current,pinned);compare_inventory(initial,inventory(self.s3,BUCKET))
        def store(name,value):
            body=serialize(value);key=prefix+name;response=self.s3.put_object(Bucket=DEST_BUCKET,Key=key,Body=body,ContentType='application/json',Metadata={'sha256':sha(body)},IfNoneMatch='*');vid=guard.valid_version(response.get('VersionId'))
            if read_version(self.s3,DEST_BUCKET,key,vid)!=body:raise RuntimeError('Backup record failed verification')
            return {'uri':'s3://'+DEST_BUCKET+'/'+key,'version_id':vid,'sha256':sha(body)}
        config=store('hosting.json',hosting)
        manifest={'source_bucket':BUCKET,'source_prefix':'','destination_bucket':DEST_BUCKET,'destination_prefix':prefix,'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'hosting':config,'objects':copied}
        write(self.output/'manifest.json',manifest,exclusive=True)
        # Use the identical durable local bytes for the bound manifest record.
        m=store('manifest.json',manifest)
        # guard.write_json and legacy.serialize use different key ordering; receipt binds local bytes.
        local_body=serialize(manifest);(self.output/'manifest.json').write_bytes(local_body)
        complete={'status':'COMPLETE','backup_uri':'s3://'+DEST_BUCKET+'/'+prefix,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manifest_uri':m['uri'],'manifest_version_id':m['version_id'],'manifest_sha256':sha(local_body),'object_count':len(copied),'total_bytes':sum(x['bytes'] for x in copied),'sha256_verified':True,'metadata_and_tags_verified':True,'source_current_versions_unchanged':True,'source_mutations':0}
        c=store('completion.json',complete);receipt=dict(complete,completion_uri=c['uri'],completion_version_id=c['version_id'],completion_sha256=c['sha256']);write(self.output/'receipt.json',receipt,exclusive=True)
        shutil.copytree(self.baseline,self.state/'live-s3')
        write(self.state/'evidence/live-results.json',[{'key':k,'status':200,'matches_local_bytes':True,'sha256':v} for k,v in hashes.items()])
        return receipt

def prepare(state,build,validation,review):
    state=Path(state);build=Path(build);validation=Path(validation);review=Path(review)
    if (state/'build').exists() or (state/'reviewed-scope.json').exists():raise RuntimeError('Prepared release already exists')
    if not re.search(r'^## Assessment: APPROVED\s*$',review.read_text(),re.MULTILINE):raise RuntimeError('Independent APPROVED review required')
    hashes=guard.tree_hashes(build);baseline=guard.tree_hashes(state/'live-s3');report=read_json(validation)
    if report.get('failures')!=[] or report.get('build_sha256')!=hashes:raise RuntimeError('Validation differs from current build')
    if not set(baseline)<=set(hashes):raise RuntimeError('Every original key must be retained')
    approved=review.read_text()
    if 'Validation SHA-256: '+sha(validation.read_bytes()) not in approved or 'Build manifest SHA-256: '+manifest_digest(hashes) not in approved:raise RuntimeError('Independent review does not bind exact build/validation')
    manifest=read_json(state/'backup/manifest.json');receipt=read_json(state/'backup/receipt.json')
    if receipt.get('status')!='COMPLETE' or receipt.get('manifest_sha256')!=sha((state/'backup/manifest.json').read_bytes()) or {r['relative_key']:r['sha256'] for r in manifest['objects']}!=baseline:raise RuntimeError('Backup does not match baseline')
    frozen_review=state/'review.md'
    shutil.copyfile(review,frozen_review)
    scope={'bucket':BUCKET,'prefix':'','build_sha256':hashes,'baseline_sha256':baseline,'changed_keys':sorted(k for k in baseline if baseline[k]!=hashes[k]),'added_keys':sorted(set(hashes)-set(baseline)),'validation_sha256':sha(validation.read_bytes()),'review_path':str(frozen_review.resolve()),'review_sha256':sha(frozen_review.read_bytes()),'status':'APPROVED'}
    shutil.copytree(build,state/'build');(state/'repair').mkdir();shutil.copyfile(validation,state/'repair/validation.json');write(state/'repair/cleanup.json',[]);write(state/'reviewed-scope.json',scope,exclusive=True)
    if guard.tree_hashes(state/'build')!=hashes or guard.tree_hashes(build)!=hashes:raise RuntimeError('Build changed during preparation')
    return {'changed_keys':scope['changed_keys'],'added_keys':scope['added_keys'],'output_count':len(hashes),'deletes':0}

def configure(state):
    scope=read_json(Path(state)/'reviewed-scope.json');hashes=guard.tree_hashes(Path(state)/'build');baseline=guard.tree_hashes(Path(state)/'live-s3')
    if scope.get('status')!='APPROVED' or scope.get('bucket')!=BUCKET or scope.get('prefix')!='' or scope.get('build_sha256')!=hashes or scope.get('baseline_sha256')!=baseline or scope.get('changed_keys')!=sorted(k for k in baseline if baseline[k]!=hashes.get(k)) or scope.get('added_keys')!=sorted(set(hashes)-set(baseline)) or scope.get('validation_sha256')!=sha((Path(state)/'repair/validation.json').read_bytes()):raise RuntimeError('Frozen scope/build/validation mismatch')
    review=Path(scope['review_path'])
    if not review.is_file() or sha(review.read_bytes())!=scope['review_sha256']:raise RuntimeError('Reviewed evidence changed')
    guard.ADDED_KEYS=frozenset(scope['added_keys']);guard.EXPECTED_BASELINE_COUNT=len(baseline);return scope

class HookedAZRelease(guard.Release):
    def head(self,key):return canonical(super().head(key))


    def backup_rows(self):
        rows=super().backup_rows();manifest=read_json(self.root/'backup/manifest.json')
        receipt=read_json(self.root/'backup/receipt.json');uri=receipt.get('manifest_uri','');prefix='s3://'+DEST_BUCKET+'/'
        if not uri.startswith(prefix):raise RuntimeError('Wrong remote backup manifest destination')
        key=guard.checked_key(uri[len(prefix):]);vid=guard.valid_version(receipt.get('manifest_version_id'))
        if sha(read_version(self.s3,DEST_BUCKET,key,vid))!=receipt['manifest_sha256']:raise RuntimeError('Remote backup manifest changed')
        if manifest.get('destination_bucket')!=DEST_BUCKET or not manifest.get('destination_prefix','').startswith(BUCKET+'/'):raise RuntimeError('Wrong backup destination')
        def check(row):
            key=row.get('destination_key','');prefix=manifest['destination_prefix']+'site/'
            if key!=prefix+row['relative_key']:raise RuntimeError('Wrong backup object boundary')
            vid=guard.valid_version(row.get('destination_version_id'));head=self.s3.head_object(Bucket=DEST_BUCKET,Key=key,VersionId=vid)
            if sha(read_version(self.s3,DEST_BUCKET,key,vid))!=row['sha256'] or metadata(head)!=row['metadata'] or tags(self.s3,DEST_BUCKET,key,vid)!=row['tags']:raise RuntimeError('Remote backup verification failed: '+key)
        parallel(check,rows.values());return rows
    def preflight(self):
        verify_distribution(self.cloudfront)
        rows=self.backup_rows()
        for key,row in rows.items():
            h=self.s3.head_object(Bucket=BUCKET,Key=key)
            if metadata(h)!=row['metadata']:raise RuntimeError('Source metadata/headers changed since backup: '+key)
        return super().preflight()
    def upload(self):
        verify_distribution(self.cloudfront)
        if (self.state/'restore-complete.json').exists():raise RuntimeError('Cannot deploy a restored release')
        return super().upload()
    def restore(self):
        manifest=self.load_manifest();uploaded=self.logs('upload.jsonl',manifest);restored=self.logs('rollback.jsonl',manifest)
        self.current_guard(manifest,uploaded,restored)
        for row in reversed(manifest['objects']):
            key=row['key'];before=row['before']
            if key not in uploaded or key in restored or not before['exists']:continue
            path=self.state/'before'/key
            if not path.is_file() or sha(path.read_bytes())!=before['sha256']:raise RuntimeError('Rollback original missing or altered: '+key)
            expected={'exists':True,'version_id':uploaded[key]['version_id'],'tags':before.get('tags',[])}
            current=self.guard(key,expected)
            response=self.s3.put_object(Bucket=BUCKET,Key=key,Body=path.read_bytes(),Metadata=before.get('metadata',{}),**self.tagging(before),**before.get('headers',{}),**self.conditional(current))
            self.log('rollback.jsonl',{'key':key,'version_id':guard.valid_version(response.get('VersionId'))})
        self.current_guard(manifest,uploaded,self.logs('rollback.jsonl',manifest))
        result=self.invalidate(manifest,'restore')
        write(self.state/'restore-complete.json',{'release_id':manifest['release_id'],'restored_originals':len(self.logs('rollback.jsonl',manifest)),'added_objects_retained':True,'deletes':0},exclusive=True)
        return result
    rollback=restore

    @staticmethod
    def output_headers(key,before):
        if before['exists']:return dict(before.get('headers',{}))
        content_type=mimetypes.guess_type(key)[0] or 'application/octet-stream'
        if Path(key).suffix in ('.html','.css','.js','.json','.txt','.xml'):content_type+='; charset=utf-8'
        return {'ContentType':content_type,'CacheControl':'public, max-age=300'}
    def boundaries(self,hashes,baseline):
        super().boundaries(hashes,baseline);scope=configure(self.root)
        if hashes!=scope['build_sha256'] or {k:v['sha256'] for k,v in baseline.items()}!=scope['baseline_sha256']:raise RuntimeError('Exact scope baseline mismatch')
    def invalidate(self,manifest,operation):
        paths={'/'+x['key'] for x in manifest['objects']}
        for path in list(paths):
            if path.endswith('/index.html'):
                route=path.removesuffix('index.html');paths.add(route)
                if route!='/':paths.add(route.rstrip('/'))
        items=sorted(paths);response=self.cloudfront.create_invalidation(DistributionId=DISTRIBUTION,InvalidationBatch={'Paths':{'Quantity':len(items),'Items':items},'CallerReference':manifest['release_id']+'-'+operation});write(self.state/(operation+'-invalidation.json'),response);return response

def release_for(state,s3,cf):configure(state);return HookedAZRelease(state,s3,cf)

def public(state,opener=urllib.request.urlopen):
    state=Path(state);scope=configure(state)
    jobs=[(k,k,200,v) for k,v in scope['build_sha256'].items()]
    for key,digest in scope['build_sha256'].items():
        if key.endswith('index.html') and (key=='index.html' or key.endswith('/index.html')):
            route=key.removesuffix('index.html');jobs.append((route or '/',route,200,digest))
    jobs.append(('missing','__hookedaz_missing_release_check__.html',404,None))
    def check(job):
        key,path,status,digest=job;url=BASE+urllib.parse.quote(path,safe='/');out={'key':key,'url':url,'expected_status':status}
        try:
            req=urllib.request.Request(url,headers={'Accept-Encoding':'identity','User-Agent':'HookedAZPreservationVerification/1.0'})
            with opener(req,timeout=60) as r:
                body=r.read();out.update(status=r.status,sha256=sha(body),passed=r.status==status and (digest is None or sha(body)==digest))
        except urllib.error.HTTPError as e:out.update(status=e.code,passed=e.code==status and digest is None);e.close()
        except Exception as e:out.update(passed=False,error=str(e))
        return out
    results=parallel(check,jobs);report={'passed':all(x['passed'] for x in results),'requests':len(results),'failures':[x for x in results if not x['passed']],'results':results};write(state/'release/public-verification.json',report);return report

class ReadThroughCredentialCache:
    """Read CLI role credentials, retaining any refresh only in process memory."""
    def __init__(self,disk):self.disk=disk;self.memory={}
    def __contains__(self,key):return key in self.memory or key in self.disk
    def __getitem__(self,key):return self.memory[key] if key in self.memory else self.disk[key]
    def __setitem__(self,key,value):self.memory[key]=value


def configure_credential_cache(session,cache_dir=None,resolver_factory=None,cache_factory=None):
    # Match the CLI profile provider chain, including SSO role credential cache.
    # JSONFileCache reads are allowed; this wrapper never writes ~/.aws files.
    if resolver_factory is None or cache_factory is None:
        from awscli.botocore.credentials import create_credential_resolver, JSONFileCache
        resolver_factory=resolver_factory or create_credential_resolver
        cache_factory=cache_factory or JSONFileCache
    cache=ReadThroughCredentialCache(cache_factory(str(cache_dir or Path.home()/'.aws/cli/cache')))
    session.register_component('credential_provider',resolver_factory(session,cache=cache,region_name='us-west-2'))



def baseline_verify(baseline,s3):
    baseline=Path(baseline);hashes=guard.tree_hashes(baseline);initial=inventory(s3,BUCKET)
    if not hashes or set(hashes)!=set(initial):raise RuntimeError('Local baseline inventory differs from current S3')
    def check(item):
        key,expected=item;head=s3.head_object(Bucket=BUCKET,Key=key);vid=guard.valid_version(head.get('VersionId'))
        if head['ETag']!=initial[key]['ETag'] or sha(read_version(s3,BUCKET,key,vid))!=expected:raise RuntimeError('Current baseline content drift: '+key)
        return {'key':key,'version_id':vid,'sha256':expected,'metadata':metadata(head),'tags':tags(s3,BUCKET,key,vid)}
    rows=parallel(check,sorted(hashes.items()));compare_inventory(initial,inventory(s3,BUCKET))
    def current(row):
        h=s3.head_object(Bucket=BUCKET,Key=row['key'])
        if h.get('VersionId')!=row['version_id'] or metadata(h)!=row['metadata'] or tags(s3,BUCKET,row['key'],row['version_id'])!=row['tags']:raise RuntimeError('Current baseline settings drift: '+row['key'])
    parallel(current,rows)
    return {'passed':True,'object_count':len(rows),'total_bytes':sum((baseline/k).stat().st_size for k in hashes),'build_manifest_sha256':manifest_digest(hashes),'objects':rows}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['baseline','backup','plan','prepare','preflight','deploy','upload','verify','restore','public','wait'])
    parser.add_argument('--state',type=Path,default=ROOT/'operations-state')
    parser.add_argument('--baseline',type=Path,default=ROOT/'live-s3')
    parser.add_argument('--public-proof',type=Path,default=ROOT/'operations/public-baseline.json')
    parser.add_argument('--build',type=Path);parser.add_argument('--validation',type=Path);parser.add_argument('--review',type=Path)
    args=parser.parse_args();state=args.state
    if args.mode in ('plan','prepare'):
        if not all((args.build,args.validation,args.review)):parser.error('plan requires --build --validation --review')
        result=prepare(state,args.build,args.validation,args.review)
    elif args.mode=='public':result=public(state)
    else:
        import awscli.botocore.session
        from awscli.botocore.config import Config
        session=awscli.botocore.session.get_session();session.set_config_variable('profile','csjh');configure_credential_cache(session)
        config=Config(max_pool_connections=16,retries={'max_attempts':5,'mode':'standard'})
        s3=session.create_client('s3',region_name='us-west-2',config=config);cf=session.create_client('cloudfront',region_name='us-east-1',config=config)
        if args.mode=='baseline':
            result=baseline_verify(args.baseline,s3);write(state/'baseline-verification.json',result)
        elif args.mode=='backup':result=Backup(state,args.baseline,s3,cf,read_json(args.public_proof)).run('before-repairs')
        elif args.mode=='wait':
            record=read_json(state/'release/upload-invalidation.json');vid=record['Invalidation']['Id'];result=cf.get_invalidation(DistributionId=DISTRIBUTION,Id=vid);write(state/'release/invalidation-status.json',result)
        else:
            rel=release_for(state,s3,cf);result=getattr(rel,'upload' if args.mode=='deploy' else args.mode)()
            if args.mode=='preflight':result={'release_id':result['release_id'],'changed_keys':[x['key'] for x in result['objects']],'deletes':0}
    if args.mode=='baseline':result={k:v for k,v in result.items() if k!='objects'}
    print(json.dumps(result,indent=2,default=str))
    if isinstance(result,dict) and result.get('passed') is False:raise SystemExit(1)

if __name__=='__main__':main()
