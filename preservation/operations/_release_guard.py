#!/usr/bin/env python3
"""Reviewed legacy archive release core adapted for HookedAZ; no permission/configuration operations.

Forward releases retain every original key. Rollback restores retained bodies
using conditional PutObject and uses recoverable delete markers only for keys
introduced by this release. No version is purged.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import hashlib
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import shutil
from urllib.parse import urlencode
import uuid

BUCKET='hookedaz.cronkitenewsonline.com'
PREFIX=''
DISTRIBUTION='E2FBUY3UNH70WK'
ROOT=Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_COUNT=527
ADDED_KEYS=frozenset()
RETIRED_KEYS=frozenset()
HEAD_FIELDS=('ContentType','CacheControl','ContentDisposition','ContentEncoding','ContentLanguage','Expires','WebsiteRedirectLocation')


def digest(body):return hashlib.sha256(body).hexdigest()


def checked_key(key):
    if not isinstance(key,str) or not key or '\\' in key or key.startswith('/') or '..' in PurePosixPath(key).parts or PurePosixPath(key).as_posix()!=key:
        raise RuntimeError(f'Unsafe archive key: {key!r}')
    return key


def tree_hashes(directory):
    result={}
    for path in sorted(Path(directory).rglob('*')):
        if path.is_symlink():raise RuntimeError(f'Symlink is not a release file: {path}')
        if path.is_file():result[checked_key(path.relative_to(directory).as_posix())]=digest(path.read_bytes())
    return result


def write_json(path,value,exclusive=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    body=json.dumps(value,indent=2,default=str)+'\n'
    if exclusive:
        with path.open('x') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
    else:
        temp=path.with_name(path.name+'.tmp');temp.write_text(body);temp.replace(path)


def valid_version(value):
    if not value or value=='null':raise RuntimeError('Retained object version is required')
    return value


class Release:
    def __init__(self,root,s3,cloudfront):
        self.root=Path(root);self.build=self.root/'build';self.baseline=self.root/'live-s3';self.state=self.root/'release';self.s3=s3;self.cloudfront=cloudfront

    def remote_key(self,key):return PREFIX+checked_key(key)

    def head(self,key):
        try:
            value=self.s3.head_object(Bucket=BUCKET,Key=self.remote_key(key))
            return {'exists':True,'version_id':valid_version(value.get('VersionId')),'etag':value['ETag'],'metadata':value.get('Metadata',{}),'headers':{k:value[k] for k in HEAD_FIELDS if k in value}}
        except Exception as error:
            response=getattr(error,'response',{});code=response.get('ResponseMetadata',{}).get('HTTPStatusCode')
            if code==404 or str(response.get('Error',{}).get('Code')) in ('404','NoSuchKey','NotFound'):
                headers=response.get('ResponseMetadata',{}).get('HTTPHeaders',{})
                return {'exists':False,'version_id':headers.get('x-amz-version-id'),'delete_marker':headers.get('x-amz-delete-marker')=='true'}
            raise

    def body(self,key,version_id):
        response=self.s3.get_object(Bucket=BUCKET,Key=self.remote_key(key),VersionId=version_id);stream=response['Body']
        try:return stream.read()
        finally:stream.close()

    def inventory(self):
        keys=set()
        for page in self.s3.get_paginator('list_objects_v2').paginate(Bucket=BUCKET,Prefix=PREFIX):
            for row in page.get('Contents',[]):
                key=row['Key']
                if not key.startswith(PREFIX):raise RuntimeError('Out-of-prefix inventory key')
                keys.add(checked_key(key.removeprefix(PREFIX)))
        return keys

    def backup_rows(self):
        path=self.root/'backup/manifest.json';receipt=json.loads((self.root/'backup/receipt.json').read_text());raw=path.read_bytes()
        if receipt.get('status')!='COMPLETE' or receipt.get('manifest_sha256')!=digest(raw) or any(receipt.get(k) is not True for k in ('sha256_verified','metadata_and_tags_verified','source_current_versions_unchanged')) or receipt.get('source_mutations')!=0:
            raise RuntimeError('Verified backup receipt does not match backup manifest')
        manifest=json.loads(raw)
        if (manifest.get('source_bucket'),manifest.get('source_prefix'))!=(BUCKET,PREFIX):raise RuntimeError('Backup targets another archive')
        rows=manifest.get('objects',[]);mapping={}
        for row in rows:
            key=checked_key(row['relative_key'])
            if key in mapping or row.get('source_key')!=self.remote_key(key) or row.get('verified') is not True:raise RuntimeError('Invalid backup object boundary')
            valid_version(row.get('source_version_id'));mapping[key]=row
        if len(mapping)!=EXPECTED_BASELINE_COUNT or receipt.get('object_count')!=len(mapping) or receipt.get('total_bytes')!=sum(x['bytes'] for x in rows):raise RuntimeError('Backup object count/bytes differ from frozen baseline')
        actual=tree_hashes(self.baseline);expected={k:v['sha256'] for k,v in mapping.items()}
        evidence=json.loads((self.root/'evidence/live-results.json').read_text());http={checked_key(r['key']):r['sha256'] for r in evidence if r.get('matches_local_bytes') and r.get('status')==200}
        if actual!=expected or actual!=http:raise RuntimeError('Immutable baseline differs from verified backup/public evidence')
        return mapping

    def validated_build(self):
        report=json.loads((self.root/'repair/validation.json').read_text());hashes=tree_hashes(self.build)
        if report.get('failures')!=[] or not hashes or report.get('build_sha256')!=hashes:raise RuntimeError('Validation is not bound to complete current build')
        return hashes

    def boundaries(self,hashes,baseline):
        if json.loads((self.root/'repair/cleanup.json').read_text())!=[]:raise RuntimeError('No forward deletion or cleanup is allowed')
        if not set(baseline)<=set(hashes):raise RuntimeError('Every original key must be retained')
        if not set(hashes)-set(baseline)<=ADDED_KEYS:raise RuntimeError('New keys exceed the explicit added-key allowlist')

    @staticmethod
    def same_version(actual,expected):return (actual['exists'],actual.get('version_id'))==(expected['exists'],expected.get('version_id'))

    def guard(self,key,expected):
        actual=self.head(key)
        if not self.same_version(actual,expected):raise RuntimeError(f'Concurrent current version change: {key}')
        # Object tag sets are mutable without creating a new object version.
        # Compare even an empty expected set; absence of a field is distinct.
        if actual['exists'] and 'tags' in expected:
            tags=self.s3.get_object_tagging(Bucket=BUCKET,Key=self.remote_key(key),VersionId=actual['version_id'])['TagSet']
            if sorted(tags,key=lambda x:x['Key'])!=sorted(expected['tags'],key=lambda x:x['Key']):raise RuntimeError(f'Concurrent object tag change: {key}')
        return actual

    def preflight(self):
        if (self.state/'preflight.json').exists():raise RuntimeError('Existing preflight must not be overwritten')
        backup=self.backup_rows();hashes=self.validated_build();self.boundaries(hashes,backup)
        if self.inventory()!=set(backup):raise RuntimeError('Remote inventory differs from backed-up baseline')
        def capture(item):
            key,row=item
            head=self.guard(key,{'exists':True,'version_id':row['source_version_id']})
            if digest(self.body(key,head['version_id']))!=row['sha256']:raise RuntimeError(f'Remote baseline content drift: {key}')
            tags=self.s3.get_object_tagging(Bucket=BUCKET,Key=self.remote_key(key),VersionId=head['version_id'])['TagSet']
            if 'tags' in row and sorted(tags,key=lambda x:x['Key'])!=row['tags']:raise RuntimeError(f'Backed-up source tags changed: {key}')
            head.update({'sha256':row['sha256'],'tags':sorted(tags,key=lambda x:x['Key'])})
            return key,head
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:before=dict(pool.map(capture,sorted(backup.items())))
        objects=[]
        for key,sha in sorted(hashes.items()):
            if key in backup and backup[key]['sha256']==sha:continue
            current=before.get(key) or self.head(key)
            if key not in backup and current['exists']:raise RuntimeError(f'Unexpected existing new key: {key}')
            objects.append({'key':key,'action':'put','sha256':sha,'bytes':(self.build/key).stat().st_size,'before':current})
        if self.inventory()!=set(backup):raise RuntimeError('Remote inventory changed during preflight')
        self.guard_many(before)
        self.state.mkdir(parents=True,exist_ok=True)
        for row in objects:
            if row['before']['exists']:
                path=self.state/'before'/row['key'];path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(self.baseline/row['key'],path)
        manifest={'release_id':str(uuid.uuid4()),'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'bucket':BUCKET,'prefix':PREFIX,'distribution':DISTRIBUTION,'build_sha256':hashes,'baseline':before,'objects':objects,'permissions_changed':False,'configuration_changed':False}
        write_json(self.state/'preflight.json',manifest,exclusive=True);return manifest

    def load_manifest(self):
        manifest=json.loads((self.state/'preflight.json').read_text());backup=self.backup_rows()
        if (manifest.get('bucket'),manifest.get('prefix'),manifest.get('distribution'))!=(BUCKET,PREFIX,DISTRIBUTION) or not manifest.get('release_id'):raise RuntimeError('Invalid release archive target')
        hashes=manifest.get('build_sha256',{});self.boundaries(hashes,backup)
        for key in hashes:checked_key(key)
        baseline=manifest.get('baseline',{})
        if set(baseline)!=set(backup) or any(baseline[k].get('version_id')!=v['source_version_id'] or baseline[k].get('sha256')!=v['sha256'] or baseline[k].get('exists') is not True for k,v in backup.items()):raise RuntimeError('Frozen baseline differs from backup')
        expected={k for k,v in hashes.items() if backup.get(k,{}).get('sha256')!=v};seen=set()
        for row in manifest.get('objects',[]):
            key=checked_key(row['key'])
            if key in seen or key not in expected or row.get('action')!='put' or row.get('sha256')!=hashes[key]:raise RuntimeError('Invalid or duplicate release key/action')
            if key in baseline and row.get('before')!=baseline[key]:raise RuntimeError('Changed rollback baseline')
            if key not in baseline and row.get('before',{}).get('exists') is not False:raise RuntimeError('New release key has an invalid prior state')
            seen.add(key)
        if seen!=expected:raise RuntimeError('Release object key set is incomplete')
        return manifest

    def log(self,filename,row):
        self.state.mkdir(parents=True,exist_ok=True)
        with (self.state/filename).open('a') as stream:stream.write(json.dumps(row,default=str)+'\n');stream.flush();os.fsync(stream.fileno())

    def logs(self,filename,manifest):
        path=self.state/filename;rows=[json.loads(x) for x in path.read_text().splitlines() if x] if path.exists() else [];result={};allowed={r['key'] for r in manifest['objects']}
        for row in rows:
            key=checked_key(row['key']);valid_version(row.get('version_id'))
            if key not in allowed or key in result:raise RuntimeError('Invalid or duplicate release journal key')
            result[key]=row
        return result

    def current_guard(self,manifest,uploaded,restored=None):
        restored=restored or {};rows={r['key']:r for r in manifest['objects']};expected=dict(manifest['baseline'])
        for key,row in rows.items():
            if key in restored:expected[key]={'exists':row['before']['exists'],'version_id':restored[key]['version_id'],'tags':row['before'].get('tags',[])}
            elif key in uploaded:expected[key]={'exists':True,'version_id':uploaded[key]['version_id'],'tags':row['before'].get('tags',[])}
            elif key not in expected:expected[key]=row['before']
        expected_keys={k for k,v in expected.items() if v['exists']}
        if self.inventory()!=expected_keys:raise RuntimeError('Concurrent remote inventory change')
        self.guard_many(expected)

    def guard_many(self,expected):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda item:self.guard(*item),expected.items()))

    @staticmethod
    def conditional(before):return {'IfMatch':before['etag']} if before['exists'] else {'IfNoneMatch':'*'}

    @staticmethod
    def output_headers(key,before):
        typ=mimetypes.guess_type(key)[0] or 'application/octet-stream'
        if Path(key).suffix in ('.html','.css','.js','.json','.txt','.xml'):typ+='; charset=utf-8'
        preserved={k:v for k,v in before.get('headers',{}).items() if k in ('ContentLanguage','ContentDisposition')}
        return dict(preserved,ContentType=typ,CacheControl='public, max-age=300')

    def invalidate(self,manifest,operation):
        response=self.cloudfront.create_invalidation(DistributionId=DISTRIBUTION,InvalidationBatch={'Paths':{'Quantity':1,'Items':['/'+PREFIX+'*']},'CallerReference':manifest['release_id']+'-'+operation});write_json(self.state/(operation+'-invalidation.json'),response);return response

    def upload(self):
        manifest=self.load_manifest()
        if (self.state/'rollback.jsonl').exists():raise RuntimeError('Cannot upload a rolled-back release')
        if self.validated_build()!=manifest['build_sha256']:raise RuntimeError('Build changed since preflight')
        uploaded=self.logs('upload.jsonl',manifest);self.current_guard(manifest,uploaded)
        rows=sorted(manifest['objects'],key=lambda r:(2 if r['key']=='index.html' else 1 if r['key'].endswith('.html') else 0,r['key']))
        for row in rows:
            key=row['key']
            if key in uploaded:continue
            current=self.guard(key,row['before']);body=(self.build/key).read_bytes()
            if digest(body)!=row['sha256']:raise RuntimeError('Build payload changed during upload')
            metadata=dict(current.get('metadata',{}));metadata.update({'archive-release':manifest['release_id'],'sha256':row['sha256']})
            tags=self.tagging(row['before'])
            current=self.guard(key,row['before'])
            response=self.s3.put_object(Bucket=BUCKET,Key=self.remote_key(key),Body=body,Metadata=metadata,**tags,**self.output_headers(key,row['before']),**self.conditional(current))
            self.log('upload.jsonl',{'key':key,'version_id':valid_version(response.get('VersionId')),'etag':response.get('ETag'),'sha256':row['sha256']})
        return self.invalidate(manifest,'upload')

    def verify(self):
        manifest=self.load_manifest();uploaded=self.logs('upload.jsonl',manifest)
        if set(uploaded)!={r['key'] for r in manifest['objects']}:raise RuntimeError('Release upload journal is incomplete')
        self.current_guard(manifest,uploaded)
        changed={r['key']:r for r in manifest['objects']}
        def check_object(item):
            key,sha=item
            expected=uploaded.get(key) or manifest['baseline'][key];head=self.head(key)
            passed=digest(self.body(key,expected['version_id']))==sha
            if key in uploaded:
                tags=self.s3.get_object_tagging(Bucket=BUCKET,Key=self.remote_key(key),VersionId=head['version_id'])['TagSet'];row=changed[key]
                expected_meta=dict(row['before'].get('metadata',{}));expected_meta.update({'archive-release':manifest['release_id'],'sha256':sha})
                passed=passed and sorted(tags,key=lambda x:x['Key'])==row['before'].get('tags',[]) and head.get('metadata',{})==expected_meta and head.get('headers',{})==self.output_headers(key,row['before'])
            return {'key':key,'passed':passed}
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(check_object,sorted(manifest['build_sha256'].items())))
        write_json(self.state/'object-verification.json',results)
        if not all(x['passed'] for x in results):raise RuntimeError('Release object verification failed')
        return results

    @staticmethod
    def tagging(before):
        tags=before.get('tags',[])
        return {'Tagging':urlencode([(x['Key'],x['Value']) for x in tags])} if tags else {}

    def rollback(self):
        manifest=self.load_manifest();uploaded=self.logs('upload.jsonl',manifest);restored=self.logs('rollback.jsonl',manifest)
        for row in manifest['objects']:
            key=row['key']
            if key not in uploaded and not self.same_version(self.head(key),row['before']):raise RuntimeError(f'Unjournaled remote change: {key}; inspect retained versions before manual recovery')
            if key in uploaded and row['before']['exists']:
                path=self.state/'before'/key
                if not path.is_file() or digest(path.read_bytes())!=row['before']['sha256']:raise RuntimeError(f'Private rollback backup missing or altered: {key}')
        self.current_guard(manifest,uploaded,restored)
        for row in reversed(manifest['objects']):
            key=row['key']
            if key not in uploaded or key in restored:continue
            before=row['before'];expected={'exists':True,'version_id':uploaded[key]['version_id'],'tags':before.get('tags',[])}
            current=self.guard(key,expected)
            if before['exists']:
                body=(self.state/'before'/key).read_bytes()
                if digest(body)!=before['sha256']:raise RuntimeError('Rollback backup changed during restore')
                # PutObject supports destination IfMatch; CopyObject does not.
                current=self.guard(key,expected)
                response=self.s3.put_object(Bucket=BUCKET,Key=self.remote_key(key),Body=body,Metadata=before.get('metadata',{}),**self.tagging(before),**before.get('headers',{}),**self.conditional(current))
            else:
                current=self.guard(key,expected)
                response=self.s3.delete_object(Bucket=BUCKET,Key=self.remote_key(key),IfMatch=current['etag'])
                if response.get('DeleteMarker') is not True:raise RuntimeError('Rollback deletion returned no recoverable marker')
            self.log('rollback.jsonl',{'key':key,'version_id':valid_version(response.get('VersionId'))})
        return self.invalidate(manifest,'rollback')

