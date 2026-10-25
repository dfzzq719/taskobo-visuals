(() => {
  // Preserve links published before the showcase and tool were separated.
  if (location.pathname.replace(/\/$/, '') === '/free-tools/taskobo-visuals' && ['#request', '#install'].includes(location.hash)) {
    location.replace('/free-tools/taskobo-visuals/tool/' + location.hash);
    return;
  }
  const status = document.querySelector('[data-copy-status]');
  document.querySelectorAll('[data-copy]').forEach(button => {
    button.addEventListener('click', async () => {
      const source = document.getElementById(button.dataset.copy);
      try {
        await navigator.clipboard.writeText(source.value || source.textContent);
        (document.getElementById(button.dataset.status) || status).textContent = 'コピーした。利用中のAIに貼り付けて使える。';
      } catch {
        source.focus();
        if (source.select) source.select();
        (document.getElementById(button.dataset.status) || status).textContent = '自動コピーできなかった。表示された依頼文を選択してコピーできる。';
      }
    });
  });
  document.querySelectorAll('[data-accent]').forEach(button => {
    button.addEventListener('click', () => {
      const section = button.closest('[data-palette-scope]');
      section.style.setProperty('--sample-accent', button.dataset.accent);
      section.style.setProperty('--sample-wash', button.dataset.wash);
      section.querySelectorAll('[data-accent]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
      section.querySelector('[data-palette-status]').textContent = `${button.textContent.trim()}をプレビュー中。SVG・PNGの個別ダウンロードは元のサンプル配色。`;
    });
  });
  const form = document.getElementById('request-form');
  if (!form) return;
  const output = document.getElementById('request-output');
  const resultStatus = document.getElementById('request-status');
  const palette = form.elements.palette;
  const custom = form.elements.customColor;
  const colors = { blue: '#1456D9', teal: '#176C60', terra: '#A24530', indigo: '#5B4AA5' };
  const names = { blue: 'コバルトブルー', teal: 'ディープティール', terra: 'テラコッタ', indigo: 'インディゴ', custom: '指定色', document: '文書の配色に合わせる' };
  const presets = JSON.parse(document.getElementById('sample-presets').textContent);
  const preset = presets[new URLSearchParams(location.search).get('sample')];
  if (preset) {
    form.elements.topic.value = preset.theme;
    palette.value = 'custom';
    custom.value = preset.accent;
    const notice = document.getElementById('preset-status');
    notice.hidden = false;
    notice.textContent = `${preset.name}のテーマと配色を読み込んだ。自分の業務に合わせて変更できる。`;
  }
  let profile = null;
  function updateColor() {
    custom.disabled = palette.value !== 'custom';
    document.querySelector('[data-color-swatch]').style.setProperty('--swatch', palette.value === 'custom' ? custom.value : (colors[palette.value] || '#52637A'));
  }
  function updateFraming() {
    if (!form.elements.framing) return;
    const iconsOnly = form.elements.kind.value === 'icons';
    form.elements.framing.disabled = iconsOnly;
    const help = document.getElementById('framing-help');
    if (help) help.textContent = iconsOnly
      ? '独立アイコンは自然な輪郭・透過で制作する。'
      : '画風はそのままに、外形と背景を選ぶ。標準は自然な輪郭の透過素材。';
  }
  function createBrief(announce = true) {
    const data = new FormData(form);
    const topic = String(data.get('topic') || '').trim();
    if (!topic) { if (announce) form.elements.topic.reportValidity(); return false; }
    const kind = data.get('kind');
    const colorMode = data.get('palette');
    const primary = colorMode === 'custom' ? custom.value.toUpperCase() : (colors[colorMode] || null);
    const direction = data.get('direction');
    const framing = kind === 'icons' ? 'freeform' : (data.get('framing') || 'freeform');
    const framingNames = { freeform: '自然な輪郭・透過（枠なし）', vignette: '周辺をぼかす・透過（枠なし）', 'full-scene': '背景付きの場面（全面）' };
    const framingInstructions = {
      freeform: '人物・物・必要な場面の一部が自然な外形をつくる。写真枠、カード、四角い背景、楕円の切抜き、装飾用の色面は付けない。主要な人物や物を途中で切らず、透明な余白を広げすぎない。物自体の輪郭線は選んだ画法に従って残す。',
      vignette: '主役と動作は鮮明に保ち、周辺の場面だけを不規則な外形から完全な透明へなじませる。全体をぼかさず、白い縁、楕円・矩形の境界や額縁を付けない。画法は変えない。',
      'full-scene': '主イラストは背景を含む一つの場面で画面全体を構成する。外側に写真枠やカードを加えない。同じシリーズのアイコンは自然な輪郭の透過素材とする。'
    };
    const backgroundInstructions = framing === 'full-scene'
      ? '主イラストは明示した背景付きの不透明画像とし、内蔵imagegenでは transparent_background: false を指定する。独立アイコンは実際のAlphaを持つ透明PNGとし、transparent_background: true を指定する。'
      : '独立したイラストとアイコンは、実際のAlphaを持つ透明PNGとし、内蔵imagegenでは transparent_background: true を指定する。白い背景や市松模様を焼き込まず、外枠・背景プレート・展示台を付けない。選んだ画法で必要な影だけを半透明で残す。';
    const directionNames = { editorial: 'Editorial（企業エディトリアル）', 'enterprise-narrative': 'Enterprise Narrative（企業叙事イラスト）。成熟した人物、目的のある動作、紺の輪郭と控えめな水彩の質感', 'technical-spot': 'Technical Spot（技術テーマの小さな説明イラスト）。強弱のある輪郭と平面的な色面を使う2Dの説明イラスト。球面の陰影、膨らんだ立体、プラスチックの光沢、面取り、押出しの厚みは付けない。明度差は構造の説明に限定する。題材と配色は今回の条件に従い、正面・台座なし。視点は個別に指定でき、浅い等角でも展示台や背景プレートは付けない', precision: 'Precision（精密な輪郭と塗り）', dimensional: 'Dimensional（落ち着いた立体表現）' };
    const presetFamilies = { 'enterprise-narrative': 'editorial', 'technical-spot': 'precision' };
    profile = {
      schema: 'taskobo-illustration.visual-brief/v1',
      topic: { title: topic, origin: 'user', evidence: [] },
      direction: { ...(presetFamilies[direction] ? { styleId: direction } : {}), id: presetFamilies[direction] || direction, ...(presetFamilies[direction] ? { preset: direction } : {}), origin: 'user', status: 'draft' },
      palette: { mode: colorMode === 'document' ? 'document' : colorMode === 'custom' ? 'custom' : 'preset', roles: primary ? { primary, ink: '#0D2046', paper: '#FCFBF8' } : {}, lockedRoles: primary ? ['primary'] : [] },
      medium: { kind: data.get('use').includes('PPT') ? 'presentation' : 'document', purpose: data.get('use'), language: 'ja', background: 'light' },
      assets: [
        ...(kind !== 'icons' ? [{ id: 'illustration-01', kind: 'illustration', framing, background: framing === 'full-scene' ? 'opaque' : 'transparent', purpose: data.get('use'), sourceRefs: [], status: 'planned' }] : []),
        ...(kind !== 'illustration' ? Array.from({ length: 6 }, (_, index) => ({ id: `icon-${String(index + 1).padStart(2, '0')}`, kind: 'icon', framing: 'freeform', background: 'transparent', purpose: 'テーマに合う対象と行動を伝える', ...(direction === 'technical-spot' ? { iconSizePx: 96, detailLevel: 'compact' } : {}), sourceRefs: [], status: 'planned' })) : [])
      ]
    };
    output.value = `$taskobo-visuals を使い、次の条件で企業向けの素材を制作する。\n\n内容テーマ：${topic}\n用途：${data.get('use')}\n制作物：${kind === 'both' ? 'メインイラスト1点と、内容から選ぶテーマ別アイコン6点' : kind === 'icons' ? '内容から選ぶテーマ別アイコン6点' : 'メインイラスト1点'}\n画風：${directionNames[direction]}。イラストとアイコンは同じスタイルID・完全に同じ画法で制作する。線、塗り、材質、質感、光を共通にし、構図と細部の量だけを大きさに合わせる。別の似た画風には置き換えない。\n配色：${colorMode === 'document' ? '提供文書のテーマ定義と実際の用色を確認し、根拠を示して提案する。文書がない場合は必要な資料を確認する。' : `${names[colorMode]}。主色 ${primary}、濃色 #0D2046、配置先の参考背景 #FCFBF8（文書の参考色。素材の背景は外形の指定に従う）。`}\n外形：${framingNames[framing]}。${framingInstructions[framing]}\n背景：${backgroundInstructions}\n\n内容テーマ、画風、色系を分けて扱う。文書を添付した場合はページ・段落の根拠を示し、各素材の意味、対象・動作、誤解してはいけない条件を整理してから制作する。見本の対象や青色を固定せず、今回の文書から新しいアイコンを設計する。承認待ちを承認済みに描き替えず、推測を事実として描かない。業務上の数値や効果を創作しない。\nメインイラストは高解像度画像、図形として編集できるアイコンは独立SVGと透明PNGで納品する。ビットマップ画像をSVGと呼ばない。小サイズで確認し、全体一覧、配色、使用上の注意と生成プロンプトを保存する。`;
    if (direction === 'technical-spot') output.value += '\n06の小さな図は実表示96px・compactを起点にする。主対象1つと必要な補助1つまでとし、密集した端子・配線・放熱フィンや機器の寄せ集めを描かない。Skill同梱の現在のコンパクト参照を実際に画像生成ツールへ渡し、版・画法・参照・表示サイズ・細部の量・配色を記録する。';
    document.getElementById('download-brief').disabled = false;
    if (announce) resultStatus.textContent = '依頼文を更新した。画像の生成は、Skillを導入したAIで実行する。';
    return true;
  }
  form.addEventListener('submit', event => { event.preventDefault(); createBrief(); });
  palette.addEventListener('change', updateColor);
  form.elements.kind.addEventListener('change', updateFraming);
  custom.addEventListener('input', updateColor);
  form.addEventListener('input', () => {
    resultStatus.textContent = '条件を変更した。「依頼文を更新」で反映できる。';
    document.getElementById('download-brief').disabled = true;
  });
  document.getElementById('download-brief').addEventListener('click', () => {
    if (!profile) return;
    const blob = new Blob([JSON.stringify(profile, null, 2) + '\n'], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'taskobo-visuals-brief.json'; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    resultStatus.textContent = '制作ブリーフのJSONを保存した。利用中のAIに依頼文と一緒に渡せる。';
  });
  updateColor(); updateFraming(); createBrief(false);
})();
