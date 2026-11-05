import {createRequire} from 'node:module';
import {test} from 'node:test';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const controller=require('../assets/archive.js');
function fixture(){
  const events={};
  const make=(id)=>({id,hidden:false,inert:false,attrs:{},classList:{add(){},remove(){}},setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k]??null;},focus(){doc.activeElement=this;},contains(n){return n===this||n===link;}});
  const panel=make('static-wrapper'),opener=make('static-toggle'),close=make('static-close'),link=make('section');
  opener.closest=(s)=>s.includes('static-toggle')?opener:null;close.closest=(s)=>s.includes('static-close')?close:null;
  link.closest=(s)=>s.includes('a[href]')?link:null;link.attrs.href='#data';
  const target=make('data');
  const doc={activeElement:null,getElementById(id){return {'static-wrapper':panel,data:target}[id]??null;},querySelectorAll(){return [opener];},addEventListener(k,fn){events[k]=fn;}};
  const click=(node)=>{const e={target:node,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;}};events.click(e);return e;};
  return {doc,panel,opener,close,link,target,events,click};
}
test('menu toggles once, hides closed content and Escape restores opener focus',()=>{
  const f=fixture();controller.initializeMenu(f.doc);
  assert.equal(f.panel.hidden,true);assert.equal(f.panel.inert,true);
  let e=f.click(f.opener);assert.equal(e.stopped,true);assert.equal(f.panel.hidden,false);assert.equal(f.opener.attrs['aria-expanded'],'true');
  f.events.keydown({key:'Escape',preventDefault(){}});
  assert.equal(f.panel.hidden,true);assert.equal(f.panel.inert,true);assert.equal(f.doc.activeElement,f.opener);
});
test('section link closes nonmodal menu and moves focus to requested section',()=>{
  const f=fixture();controller.initializeMenu(f.doc);f.click(f.opener);f.click(f.link);
  assert.equal(f.panel.hidden,true);assert.equal(f.doc.activeElement,f.target);
});
test('map frame resize survives unavailable frame and calls same-origin callback',()=>{
  let count=0;
  assert.doesNotThrow(()=>controller.resizeFrame({get contentWindow(){throw new Error('cross origin');}}));
  controller.resizeFrame({contentWindow:{archiveResizeMap(){count++;}}});assert.equal(count,1);
});
