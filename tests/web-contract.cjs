const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { buildDraft, validateOrganization, makeOrganization } = require('../website/illustration.js');
const root = path.resolve(__dirname, '..');
const catalog = JSON.parse(fs.readFileSync(path.join(root,'references/style-recipes.json'),'utf8'));
catalog.skillVersion = /version:\s*"([^"]+)"/.exec(fs.readFileSync(path.join(root,'SKILL.md'),'utf8'))[1];
const values = { topic:'取引先への追加確認と契約準備', use:'サービス紹介の提案書', kind:'both', direction:'enterprise-narrative', framing:'freeform', palette:'custom', primary:'#7D3C98', language:'ja', targetSize:'16:9の資料・半ページ程度', iconCount:'4', iconSizePx:'96' };
const first = buildDraft(values,catalog);
assert.equal(first.status,'draft');
assert.equal(first.assets.length,5);
assert.ok(first.assets.every(asset=>asset.status==='draft' && asset.meaning==='' && asset.subject==='' && asset.sourceRefs.length===0));
assert.equal(first.palette.roles.primary,'#7D3C98');
assert.equal(first.typography.ja,'Meiryo UI');
assert.equal(first.typography['zh-CN'],'Microsoft YaHei');
for (const style of catalog.styles.filter(s=>s.status==='active')) {
  const brief = buildDraft({...values,direction:style.id},catalog);
  assert.equal(brief.direction.styleId,style.id);
  assert.equal(brief.styleLock.styleVersion,style.styleVersion);
  assert.equal(brief.styleLock.referenceImages.length,style.styleReference ? 1 : 0);
  assert.ok(brief.assets.every(a=>!('styleId' in a))); // One shared style, no per-asset replacements.
}
const full = buildDraft({...values,framing:'full-scene',language:'zh-CN'},catalog);
assert.equal(full.assets[0].background,'opaque');
assert.ok(full.assets.slice(1).every(asset=>asset.background==='transparent' && asset.framing==='freeform'));
assert.deepEqual(full.palette,first.palette);
assert.deepEqual(full.direction,first.direction);
assert.equal(full.medium.language,'zh-CN');
const onlyIcons = buildDraft({...values,kind:'icons',framing:'full-scene',iconSizePx:'48'},catalog);
assert.ok(onlyIcons.assets.every(a=>a.background==='transparent' && a.framing==='freeform'));
const documentBrief = buildDraft({...values,palette:'document',primary:null},catalog);
assert.deepEqual(documentBrief.palette.roles,{});
assert.equal(documentBrief.status,'draft');
const org = makeOrganization(first,catalog,'調達部の共通基準','1.2.0');
assert.equal(org.schema,'taskobo-visuals.organization-profile/v1');
assert.deepEqual(org.references,[]);
assert.equal(validateOrganization({...org,version:'1.2.0-preview.1'},catalog).version,'1.2.0-preview.1');
const applied = buildDraft({...values,topic:'新しい業務の内容'},catalog,org);
assert.equal(applied.topic.title,'新しい業務の内容');
assert.equal(applied.organization.version,'1.2.0');
assert.deepEqual(applied.organizationProfile,org);
assert.throws(()=>buildDraft({...values,direction:'monoline'},catalog,org),/社内基準/);
assert.throws(()=>buildDraft({...values,primary:'#176C60'},catalog,org),/固定した主色/);
for (const profile of [
  {...org,schema:'other'}, {...org,version:'latest'}, {...org,styleId:'missing'},
  {...org,styleVersion:'999'}, {...org,typography:{ja:'Arial'}}, {...org,typography:{ja:'Meiryo UI'}},
  {...org,palette:{roles:{ink:'#000000',primary:'red'},lockedRoles:['primary']}},
  {...org,palette:{roles:{ink:'#000000',primary:'#7D3C98'},lockedRoles:['missing']}},
  {...org,references:[{file:'../private.png',sha256:'a'.repeat(64),role:'style'}]},
  {...org,references:[{file:'C:/private.png',sha256:'a'.repeat(64),role:'style'}]},
  {...org,references:[{file:'CON.png',sha256:'a'.repeat(64),role:'style'}]},
  {...org,references:[{file:'nested/file.svg',sha256:'a'.repeat(64),role:'style'}]},
  {...org,references:[{file:'master.png',sha256:'A'.repeat(64),role:'style'}]},
  {...org,references:[{file:'A.png',sha256:'a'.repeat(64),role:'style'},{file:'a.png',sha256:'a'.repeat(64),role:'style'}]},
]) assert.throws(()=>validateOrganization(profile,catalog));
assert.throws(()=>buildDraft({...values,iconCount:'48'},catalog),/1〜24/);
assert.throws(()=>buildDraft({...values,iconSizePx:'1'},catalog),/24〜1024/);
assert.throws(()=>buildDraft({...values,kind:'unknown'},catalog));
assert.throws(()=>buildDraft({...values,framing:'circle'},catalog));
assert.throws(()=>buildDraft({...values,language:'en'},catalog));
const unlocked = validateOrganization({...org,palette:{roles:org.palette.roles,lockedRoles:['ink']}},catalog);
assert.equal(buildDraft({...values,palette:'document',primary:null},catalog,unlocked).palette.roles.primary,undefined);
assert.throws(()=>buildDraft({...values,direction:'editorial'},catalog),/選択できない/);
assert.equal(first.status,'draft'); // Exporting or applying a standard never invents ready semantics.
console.log(JSON.stringify({passed:true,activeStyles:catalog.styles.filter(s=>s.status==='active').length,scope:'Pure Web handoff/profile behavior; browser layout and file input are verified separately.'}));
