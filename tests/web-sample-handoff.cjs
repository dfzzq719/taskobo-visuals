const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {sampleRequestURL,resolveSampleRequest,buildDraft,validateOrganization}=require('../website/illustration.js');
const root=path.resolve(__dirname,'..'),cases=JSON.parse(fs.readFileSync(path.join(root,'examples/catalog.json'),'utf8'));
const presets=Object.fromEntries(cases.map(c=>[c.id,{name:c.name,theme:c.theme,accent:c.accent}]));
const catalog=JSON.parse(fs.readFileSync(path.join(root,'references/style-recipes.json'),'utf8'));catalog.skillVersion='0.5.2';
let checks=0;
for(const item of cases){
  assert.equal(resolveSampleRequest('?sample='+item.id,presets).accent,item.accent);checks++;
  for(const color of cases.map(c=>c.accent)){
    const url=sampleRequestURL(item.id,color.toLowerCase()),selected=resolveSampleRequest(new URL(url,'https://taskobo.com').search,presets);
    assert.equal(selected.theme,item.theme);assert.equal(selected.accent,color.toUpperCase());
    const values={topic:selected.theme,use:'社内研修のPPT',kind:'both',direction:'enterprise-narrative',framing:'freeform',palette:'custom',primary:selected.accent,language:'ja',targetSize:'16:9の資料・半ページ程度',iconCount:'6',iconSizePx:'96'};
    const brief=buildDraft(values,catalog);assert.equal(brief.palette.roles.primary,color.toUpperCase());assert.equal(brief.topic.title,item.theme);checks++;
  }
  for(const invalid of ['red','#123','javascript:alert(1)','#12345678','<script>'])assert.equal(resolveSampleRequest('?sample='+item.id+'&accent='+encodeURIComponent(invalid),presets).accent,item.accent);
}
assert.equal(resolveSampleRequest('?sample=__proto__&accent=%23abcdef',presets),null);
assert.equal(resolveSampleRequest('?accent=%23abcdef',presets),null);
assert.equal(resolveSampleRequest('?sample=unknown&accent=%23abcdef',presets),null);
assert.throws(()=>sampleRequestURL('../private','#123456'));
assert.throws(()=>sampleRequestURL(cases[0].id,'red'));
const profile=validateOrganization({schema:'taskobo-visuals.organization-profile/v1',name:'研修共通',version:'1.0.0',styleId:'enterprise-narrative',styleVersion:catalog.styles.find(s=>s.id==='enterprise-narrative').styleVersion,palette:{roles:{primary:'#112233',ink:'#0D2046'},lockedRoles:['primary']},typography:{ja:'Meiryo UI','zh-CN':'Microsoft YaHei'},references:[]},catalog);
assert.throws(()=>buildDraft({topic:'研修',use:'社内研修のPPT',kind:'both',direction:'enterprise-narrative',framing:'freeform',palette:'custom',primary:'#5B4AA5',language:'ja',targetSize:'16:9の資料',iconCount:6,iconSizePx:96},catalog,profile),/固定した主色/);
console.log(JSON.stringify({passed:true,sampleColorCombinations:16,legacyLinks:4,checks,invalidQueriesIgnored:true,organizationLockRetained:true}));
