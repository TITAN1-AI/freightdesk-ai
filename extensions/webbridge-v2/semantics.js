/**
 * Portions adapted from Playwright. Copyright (c) Microsoft Corporation.
 * Licensed under the Apache License, Version 2.0. See third_party/licenses/playwright/LICENSE.
 * Modified by FreightDesk: bounded metadata-only subset, no value reads, explicit unavailable
 * semantics, no CDP/executor/cache dependency. Pin, ranges and hashes in third_party/webbridge-v2-implementation.json.
 */
(() => {
  'use strict';
  // Adapted selection of roleUtils.ts kImplicitRoleByTagName/inputTypeToRole.
  function nativeRole(e) {
    const tag=e.localName;
    if(tag==='a')return e.hasAttribute('href')?'link':null;
    if(tag==='input') {
      const type=(e.getAttribute('type')||'text').toLowerCase();
      if(['hidden','password','file','date','time','datetime-local','color'].includes(type))return null;
      return {button:'button',submit:'button',reset:'button',image:'button',checkbox:'checkbox',radio:'radio',
        number:'spinbutton',range:'slider',search:'searchbox'}[type]||'textbox';
    }
    if(tag==='select')return e.hasAttribute('multiple')||Number(e.getAttribute('size'))>1?'listbox':'combobox';
    if(tag==='form'||tag==='section')return e.hasAttribute('aria-label')||e.hasAttribute('aria-labelledby')?(tag==='form'?'form':'region'):null;
    if(/^h[1-6]$/.test(tag))return 'heading';
    return {button:'button',fieldset:'group',textarea:'textbox',dialog:'dialog',details:'group',main:'main',nav:'navigation',
      table:'table',thead:'rowgroup',tbody:'rowgroup',tfoot:'rowgroup',tr:'row',td:'cell',ol:'list',ul:'list',li:'listitem'}[tag]||null;
  }
  // Adapted getExplicitAriaRole: caller passes the reviewed projection vocabulary. Presentation
  // conflicts are deliberately unavailable here rather than importing focus/value-related helpers.
  function role(e, allowed) {
    const tokens=(e.getAttribute('role')||'').split(/\s+/);
    if(tokens.some(r=>r==='none'||r==='presentation'))return null;
    return tokens.find(r=>allowed.has(r))||nativeRole(e);
  }
  // Adapted parentElementOrShadowHost; bounded caller owns traversal.
  function parent(e) {return e.parentElement || (e.parentNode?.nodeType===11?e.parentNode.host:null) || null;}
  // Adapted getIdRefs token/dedup step only. Resolution belongs to the scoped multimap; no
  // document.getElementById, first-match ambiguity, catch-and-empty fallback or raw IDs exported.
  function idRefs(raw, max) {
    const result=[];let token='';
    const add=()=>{if(token&&!result.includes(token)){if(result.length>=max)throw Error('REFERENCE_BOUND');result.push(token);}token='';};
    for(const c of raw||''){if(/\s/.test(c))add();else token+=c;}add();return result;
  }
  // Adapted Chromium branch of computeElementStyleVisibilityVisible. display:contents is a
  // structural wrapper; caller determines visibility from bounded observed descendants.
  function styleVisible(e,style) {
    if(style.visibility!=='visible'||style.display==='none')return false;
    if(style.display==='contents')return true;
    return typeof e.checkVisibility==='function'?e.checkVisibility():true;
  }
  globalThis.FreightDeskV2Semantics=Object.freeze({nativeRole,role,parent,idRefs,styleVisible});
})();
