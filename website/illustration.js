(() => {
  'use strict';
  const FONTS = { 'zh-CN': 'Microsoft YaHei', ja: 'Meiryo UI' };
  const clone = value => JSON.parse(JSON.stringify(value));
  const validHex = value => typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value);
  const fontMap = fonts => {
    const result = { ...FONTS, ...(fonts || {}) };
    if (Object.keys(result).some(key => !Object.hasOwn(FONTS, key) || result[key] !== FONTS[key])) throw new Error('文字の基準は日本語 Meiryo UI、中国語 Microsoft YaHei。対応するフォントを指定する。');
    return result;
  };
  function styleFor(catalog, id) {
    const found = catalog.styles.find(style => style.id === id && style.status === 'active');
    if (!found) throw new Error('この画風は現在のSkillで選択できない。共通の画風一覧から選ぶ。');
    return found;
  }
  function validateOrganization(value, catalog) {
    if (!value || value.schema !== 'taskobo-visuals.organization-profile/v1') throw new Error('Taskobo Visualsの社内基準JSONを選ぶ。');
    if (typeof value.name !== 'string' || !value.name.trim() || value.name.length > 160 || !/^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?$/.test(value.version || '')) throw new Error('基準名と版（例 1.0.0）が必要。');
    const style = styleFor(catalog, value.styleId);
    if (String(value.styleVersion) !== style.styleVersion) throw new Error('画法の版が異なる。配布元に現在のSkillに合う基準を確認する。');
    const palette = value.palette;
    if (!palette || !palette.roles || !validHex(palette.roles.primary) || !validHex(palette.roles.ink) || Object.values(palette.roles).some(color => !validHex(color))) throw new Error('主色・濃色を含む6桁HEXの配色が必要。');
    if (!Array.isArray(palette.lockedRoles) || palette.lockedRoles.some(role => !Object.hasOwn(palette.roles, role)) || new Set(palette.lockedRoles).size !== palette.lockedRoles.length) throw new Error('固定する色の役割を確認する。');
    if (!value.typography || typeof value.typography !== 'object' || Object.keys(value.typography).length !== 2 || Object.keys(FONTS).some(language => value.typography[language] !== FONTS[language])) throw new Error('社内基準には日本語 Meiryo UI と中国語 Microsoft YaHei の両方の字体を指定する。');
    const typography = fontMap(value.typography);
    const refs = value.references || [];
    if (!Array.isArray(refs) || refs.length > 62 || refs.some(ref => !ref || typeof ref.file !== 'string' || !ref.file || ref.file.includes('\\') || ref.file.startsWith('/') || ref.file.split('/').some(part => !part || part === '..' || part === '.') || /[:\x00-\x1f]/.test(ref.file) || ref.file.split('/').some(part => /[. ]$/.test(part) || /^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$/i.test(part)) || !/\.(?:png|jpe?g|webp)$/i.test(ref.file) || !/^[a-f0-9]{64}$/.test(ref.sha256 || '') || typeof ref.role !== 'string' || !ref.role.trim())) throw new Error('参照見本は安全な相対パス・SHA-256・用途を持つ必要がある。');
    if (new Set(refs.map(ref => ref.file.toLowerCase())).size !== refs.length) throw new Error('参照見本のファイル名が重複している。');
    return { schema: value.schema, name: value.name.trim(), version: value.version, styleId: style.id, styleVersion: style.styleVersion, palette: clone(palette), typography, references: clone(refs) };
  }
  function buildDraft(values, catalog, organization = null) {
    const style = styleFor(catalog, values.direction);
    const roles = values.palette === 'document' ? {} : { primary: values.primary.toUpperCase(), ink: '#0D2046', paper: '#FCFBF8' };
    if (organization) {
      if (organization.styleId !== style.id || organization.styleVersion !== style.styleVersion) throw new Error('社内基準と画風が異なる。基準を解除してから個別の条件を選ぶ。');
      for (const [role, color] of Object.entries(organization.palette.roles)) {
        if (organization.palette.lockedRoles.includes(role)) {
          if (role === 'primary' && roles.primary && roles.primary.toUpperCase() !== color.toUpperCase()) throw new Error('社内基準で固定した主色と異なる。');
          roles[role] = color;
        } else if (role !== 'primary') roles[role] = color;
      }
    }
    if (Object.values(roles).some(color => !validHex(color))) throw new Error('配色は6桁のHEXで指定する。');
    if (!['both', 'illustration', 'icons'].includes(values.kind)) throw new Error('制作物の種類を選ぶ。');
    if (!['ja', 'zh-CN'].includes(values.language)) throw new Error('対応する文字の言語を選ぶ。');
    if (!['freeform', 'vignette', 'full-scene'].includes(values.framing)) throw new Error('対応する外形を選ぶ。');
    const iconSize = Number(values.iconSizePx);
    if (!Number.isInteger(iconSize) || iconSize < 24 || iconSize > 1024) throw new Error('アイコンの実表示サイズは24〜1024pxで指定する。');
    const framing = values.kind === 'icons' ? 'freeform' : values.framing;
    const count = Number(values.iconCount);
    if (!Number.isInteger(count) || count < 1 || count > 24) throw new Error('アイコン数は1〜24点で指定する。');
    const typography = fontMap(organization?.typography);
    const assets = [];
    if (values.kind !== 'icons') assets.push({ id: 'illustration-01', kind: 'illustration', framing, background: framing === 'full-scene' ? 'opaque' : 'transparent', purpose: values.use, displaySize: values.targetSize, meaning: '', subject: '', sourceRefs: [], status: 'draft' });
    if (values.kind !== 'illustration') for (let index = 0; index < count; index++) assets.push({ id: `icon-${String(index + 1).padStart(2, '0')}`, kind: 'icon', framing: 'freeform', background: 'transparent', purpose: 'テーマに合う対象と行動を伝える', iconSizePx: Number(values.iconSizePx), ...(style.id === 'technical-spot' ? { detailLevel: Number(values.iconSizePx) <= 48 ? 'symbol' : Number(values.iconSizePx) <= 128 ? 'compact' : 'standard' } : {}), meaning: '', subject: '', sourceRefs: [], status: 'draft' });
    return {
      schema: 'taskobo-illustration.visual-brief/v1', status: 'draft',
      topic: { title: values.topic.trim(), origin: 'user', evidence: [] },
      direction: { styleId: style.id, origin: organization ? 'organization' : 'user', status: 'selected' },
      styleLock: { skillVersion: catalog.skillVersion, styleId: style.id, styleVersion: style.styleVersion, referenceImages: style.styleReference ? [clone(style.styleReference)] : [] },
      palette: { mode: organization ? 'organization' : values.palette === 'document' ? 'document' : values.palette === 'custom' ? 'custom' : 'preset', roles, lockedRoles: organization ? clone(organization.palette.lockedRoles) : Object.hasOwn(roles, 'primary') ? ['primary'] : [] },
      typography,
      medium: { kind: values.use.includes('PPT') ? 'presentation' : 'document', purpose: values.use, language: values.language, targetSize: values.targetSize, background: 'light' },
      ...(organization ? { organization: { name: organization.name, version: organization.version }, organizationProfile: clone(organization) } : {}),
      assets,
    };
  }
  function makeOrganization(brief, catalog, name, version, existing = null) {
    return validateOrganization({ schema: 'taskobo-visuals.organization-profile/v1', name, version, styleId: brief.direction.styleId, styleVersion: styleFor(catalog, brief.direction.styleId).styleVersion, palette: { roles: clone(brief.palette.roles), lockedRoles: clone(brief.palette.lockedRoles) }, typography: clone(brief.typography), references: existing ? clone(existing.references) : [] }, catalog);
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { buildDraft, validateOrganization, makeOrganization, styleFor };
  if (typeof document === 'undefined') return;
  // Keep published sample, request and install links working.
  if (location.pathname.replace(/\/$/, '') === '/free-tools/taskobo-visuals' && ['#request', '#install'].includes(location.hash)) {
    location.replace('/free-tools/taskobo-visuals/tool/' + location.hash); return;
  }
  const copyStatus = document.querySelector('[data-copy-status]');
  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
    const source = document.getElementById(button.dataset.copy);
    try { await navigator.clipboard.writeText(source.value || source.textContent); (document.getElementById(button.dataset.status) || copyStatus).textContent = 'コピーした。利用中のAIに貼り付けて使える。'; }
    catch { source.focus(); if (source.select) source.select(); (document.getElementById(button.dataset.status) || copyStatus).textContent = '表示された依頼文を選択してコピーできる。'; }
  }));
  document.querySelectorAll('[data-accent]').forEach(button => button.addEventListener('click', () => {
    const section = button.closest('[data-palette-scope]');
    section.style.setProperty('--sample-accent', button.dataset.accent); section.style.setProperty('--sample-wash', button.dataset.wash);
    section.querySelectorAll('[data-accent]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    section.querySelector('[data-palette-status]').textContent = `${button.textContent.trim()}をプレビュー中。SVG・PNGの個別ダウンロードは元のサンプル配色。`;
  }));
  const form = document.getElementById('request-form');
  if (!form) return;
  const catalog = JSON.parse(document.getElementById('style-catalog').textContent);
  const output = document.getElementById('request-output');
  const resultStatus = document.getElementById('request-status');
  const profileStatus = document.getElementById('organization-status');
  const palette = form.elements.palette, custom = form.elements.customColor;
  const colors = { blue: '#1456D9', teal: '#176C60', terra: '#A24530', indigo: '#5B4AA5' };
  const framingNames = { freeform: '自然な輪郭・透過（枠なし）', vignette: '周辺をぼかす・透過（枠なし）', 'full-scene': '背景付きの場面（全面）' };
  const framingInstructions = {
    freeform: '人物・物・必要な場面の一部が自然な外形をつくる。写真枠、カード、四角い背景、楕円の切抜き、装飾用の色面は付けない。主体を途中で切らず、透明な余白を広げすぎない。物自体の輪郭線は選んだ画法に従う。',
    vignette: '主役と動作は鮮明に保ち、周辺だけを不規則な外形から完全な透明へなじませる。全体をぼかさず、白い縁や矩形・楕円の境界を付けない。',
    'full-scene': '主イラストは背景を含む場面を画面全体に構成する。同じシリーズの独立アイコンは自然な輪郭の透過素材とする。'
  };
  const presets = JSON.parse(document.getElementById('sample-presets').textContent);
  const sampleId = new URLSearchParams(location.search).get('sample');
  const preset = Object.hasOwn(presets, sampleId) ? presets[sampleId] : null;
  if (preset) {
    form.elements.topic.value = preset.theme; palette.value = 'custom'; custom.value = preset.accent;
    const notice = document.getElementById('preset-status'); notice.hidden = false; notice.textContent = `${preset.name}のテーマと配色を読み込んだ。自分の業務に合わせて変更できる。`;
  }
  let brief = null, organization = null, pendingOrganization = null;
  function updateColor() {
    const locked = organization?.palette.lockedRoles.includes('primary');
    palette.disabled = Boolean(locked); custom.disabled = locked || palette.value !== 'custom';
    document.querySelector('[data-color-swatch]').style.setProperty('--swatch', palette.value === 'custom' ? custom.value : colors[palette.value] || '#52637A');
  }
  function updateStyle() {
    const style = styleFor(catalog, form.elements.direction.value);
    form.elements.direction.disabled = Boolean(organization);
    const reference = style.styleReference ? '生成に渡す参照見本あり' : '画法の定義から制作する方向';
    const validation = style.validation || {};
    const evidence = validation.icon === 'not-pair-validated' || validation.illustration === 'not-pair-validated' ? '全題材での挿絵・アイコンの組合せを検証済みという意味ではない。' : '公開されている作例の範囲を検証記録で確認できる。';
    document.getElementById('style-evidence').textContent = `${reference}・画法の版 ${style.styleVersion}。${evidence}`;
  }
  function updateFraming() {
    const iconsOnly = form.elements.kind.value === 'icons';
    form.elements.framing.disabled = iconsOnly;
    form.elements.iconCount.disabled = form.elements.kind.value === 'illustration';
    form.elements.iconSizePx.disabled = form.elements.kind.value === 'illustration';
    document.getElementById('framing-help').textContent = iconsOnly ? '独立アイコンは自然な輪郭・透過で制作する。' : '画風はそのままに、外形と背景を選ぶ。標準は自然な輪郭の透過素材。';
  }
  function values() {
    return Object.fromEntries(['topic','use','kind','direction','framing','palette','language','targetSize','iconCount','iconSizePx'].map(name => [name, form.elements[name].value]).concat([['primary', palette.value === 'custom' ? custom.value : colors[palette.value] || null]]));
  }
  function createBrief(announce = true) {
    if (!form.elements.topic.value.trim()) { if (announce) form.elements.topic.reportValidity(); document.getElementById('download-brief').disabled = true; document.getElementById('export-organization').disabled = true; return false; }
    try {
      brief = buildDraft(values(), catalog, organization);
      const style = styleFor(catalog, brief.direction.styleId), roleText = Object.entries(brief.palette.roles).map(([role,color]) => `${role} ${color}`).join('、');
      const kind = form.elements.kind.value, framing = kind === 'icons' ? 'freeform' : form.elements.framing.value;
      output.value = `$taskobo-visuals を使い、次の制作意向から企業向け素材を制作する。添付するJSONは status: draft のため、そのまま生成タスクとして実行しない。内容の根拠から各素材の meaning・subject・必要なsourceRefsを補い、検証してreadyにする。\n\n内容テーマ：${brief.topic.title}\n用途：${brief.medium.purpose}\n制作物：${kind === 'both' ? 'メインイラスト1点と' + form.elements.iconCount.value + '点のテーマ別アイコン' : kind === 'icons' ? form.elements.iconCount.value + '点のテーマ別アイコン' : 'メインイラスト1点'}\n画風：${style.nameJa}（styleId: ${style.id}、画法の版 ${style.styleVersion}）。挿絵とアイコンは完全に同じ画法を使い、線・塗り・材質・質感・光を共通化する。構図と細部の量だけをサイズに合わせる。\n配色：${roleText || '提供文書から根拠を示して提案し、色の役割を補う。'}\n${organization ? '社内基準：' + organization.name + ' v' + organization.version + '。固定した画法・色・字体と異なる場合は上書きせず確認する。\n' : ''}配置先：${brief.medium.targetSize}。独立アイコンの実表示サイズ ${form.elements.iconSizePx.value}px。\n文字：${brief.medium.language === 'ja' ? '日本語 Meiryo UI' : '中国語 Microsoft YaHei'}。字体と正確な文字が必要な場合は、対応字体のある文字の配置処理で確認する。純粋な画像生成だけで字体の一致を保証しない。\n外形：${framingNames[framing]}。${framingInstructions[framing]}\n背景：${framing === 'full-scene' ? '主イラストは不透明（transparent_background: false）。独立アイコンは実際のAlphaを持つ透明PNG（transparent_background: true）。' : '実際のAlphaを持つ透明PNG（transparent_background: true）。白い背景や市松模様を焼き込まない。'}\n\n内容と画法と配色を分ける。文書の状態・対象・行動を確認し、見本の対象物や青色を固定しない。承認待ちを承認済みに描き替えず、数字や導入効果を創作しない。Skill同梱の選択画法の参照見本があれば実際に画像生成ツールへ渡す。\n実際に生成した原図と提示詞を保存し、Alpha・輪郭の切れ・明暗の背景・実際の表示サイズを確認する。図形として編集できるものだけをSVGと呼び、ビットマップ画像をSVGと呼ばない。\n制作記録：Skillのローカル機能で素材ごとの試行を記録し、実際に使った提示詞・参照見本・ツールの応答と原画像を結び付ける。取得できなかったモデル・seed・リクエストIDは推測で補わない。\n再制作：失敗・修正対象の素材だけを、記録した条件から明示的に選ぶ。採用済みの原図を上書きせず、試行回数の上限内で行う。結果が不明な場合は、重複生成の前に出力を確認する。\n納品と再利用：各素材に対応する独立ファイルを確認する。一覧画像を個別の納品物として数えない。ファイル検査と見た目・業務上の採用判定を分け、明示的に採用した素材だけを再利用カタログへ登録する。`;
      if (style.id === 'technical-spot') output.value += '\n06の小図は1つの主対象と必要な補助1つまで。小さな端子・放熱フィン・機器の寄せ集めを避け、現在のコンパクト参照を実際に画像生成ツールへ渡す。';
      document.getElementById('download-brief').disabled = false;
      document.getElementById('export-organization').disabled = !validHex(brief.palette.roles.primary);
      if (announce) resultStatus.textContent = '制作意向を更新した。AIが意味と対象を補い、検証してから画像を生成する。';
      resultStatus.classList.remove('ill-error'); return true;
    } catch (error) { resultStatus.textContent = error.message; resultStatus.classList.add('ill-error'); document.getElementById('download-brief').disabled = true; document.getElementById('export-organization').disabled = true; return false; }
  }
  function download(value, name) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value,null,2) + '\n'], { type:'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
  }
  form.addEventListener('submit', event => { event.preventDefault(); createBrief(); });
  palette.addEventListener('change', updateColor); custom.addEventListener('input', updateColor);
  form.elements.direction.addEventListener('change', updateStyle); form.elements.kind.addEventListener('change', updateFraming);
  form.addEventListener('input', () => { resultStatus.textContent = '条件を変更した。「依頼文を更新」で反映できる。'; document.getElementById('download-brief').disabled = true; document.getElementById('export-organization').disabled = true; });
  document.getElementById('download-brief').addEventListener('click', () => { if (brief) { download(brief,'taskobo-visuals-brief.json'); resultStatus.textContent = '制作意向のJSONを保存した。依頼文と一緒にAIへ渡す。意味と対象はAIが補う。'; } });
  document.getElementById('export-organization').addEventListener('click', () => {
    if (!createBrief(false)) return;
    try {
      const name = document.getElementById('organization-name').value, version = document.getElementById('organization-version').value;
      const value = makeOrganization(brief,catalog,name,version,organization);
      download(value,'taskobo-visuals-organization.json'); profileStatus.textContent = '画法・配色・字体の社内基準JSONを保存した。採用した参照見本の実ファイルはSkillの配布ツールで追加・照合する。'; profileStatus.classList.remove('ill-error');
    } catch(error) { profileStatus.textContent = error.message; profileStatus.classList.add('ill-error'); }
  });
  document.getElementById('import-organization').addEventListener('change', async event => {
    const file = event.target.files[0]; if (!file) return;
    try {
      if (file.size > 262144) throw new Error('社内基準JSONは256KiB以内のファイルを選ぶ。');
      pendingOrganization = validateOrganization(JSON.parse(await file.text()),catalog);
      profileStatus.textContent = `「${pendingOrganization.name} v${pendingOrganization.version}」を読み込んだ。「この基準を適用」で画風を${styleFor(catalog,pendingOrganization.styleId).nameJa}、主色を${pendingOrganization.palette.roles.primary}に変更する。テーマ・用途・構図は保持する。追加見本の実ファイル照合はSkillで行う。`;
      profileStatus.classList.remove('ill-error'); document.getElementById('apply-organization').disabled = false;
    } catch(error) { pendingOrganization = null; document.getElementById('apply-organization').disabled = true; profileStatus.textContent = error.message; profileStatus.classList.add('ill-error'); }
    event.target.value = '';
  });
  document.getElementById('apply-organization').addEventListener('click', () => {
    if (!pendingOrganization) return;
    organization = pendingOrganization; pendingOrganization = null;
    form.elements.direction.value = organization.styleId; palette.value = 'custom'; custom.value = organization.palette.roles.primary;
    document.getElementById('organization-name').value = organization.name; document.getElementById('organization-version').value = organization.version;
    document.getElementById('apply-organization').disabled = true; document.getElementById('release-organization').disabled = false;
    updateStyle(); updateColor(); createBrief(); profileStatus.textContent = `「${organization.name} v${organization.version}」を適用中。画風・字体と指定の色を固定した。個別に変更する場合は基準を解除する。`;
  });
  document.getElementById('release-organization').addEventListener('click', () => {
    organization = null; document.getElementById('release-organization').disabled = true; updateStyle(); updateColor(); createBrief(); profileStatus.textContent = '社内基準の固定を解除した。現在の画風・配色は保持している。';
  });
  updateColor(); updateStyle(); updateFraming(); createBrief(false);
})();
