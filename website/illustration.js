(() => {
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
  let profile = null;
  function updateColor() {
    custom.disabled = palette.value !== 'custom';
    document.querySelector('[data-color-swatch]').style.setProperty('--swatch', palette.value === 'custom' ? custom.value : (colors[palette.value] || '#52637A'));
  }
  function createBrief(announce = true) {
    const data = new FormData(form);
    const topic = String(data.get('topic') || '').trim();
    if (!topic) { if (announce) form.elements.topic.reportValidity(); return false; }
    const kind = data.get('kind');
    const colorMode = data.get('palette');
    const primary = colorMode === 'custom' ? custom.value.toUpperCase() : (colors[colorMode] || null);
    const direction = data.get('direction');
    const directionNames = { editorial: 'Editorial（企業エディトリアル）', precision: 'Precision（精密な輪郭と塗り）', dimensional: 'Dimensional（落ち着いた立体表現）' };
    profile = {
      schema: 'taskobo-illustration.visual-brief/v1',
      topic: { title: topic, origin: 'user', evidence: [] },
      direction: { id: direction, origin: 'user', status: 'draft' },
      palette: { mode: colorMode === 'document' ? 'document' : colorMode === 'custom' ? 'custom' : 'preset', roles: primary ? { primary, ink: '#0D2046', paper: '#FCFBF8' } : {}, lockedRoles: primary ? ['primary'] : [] },
      medium: { kind: data.get('use').includes('PPT') ? 'presentation' : 'document', purpose: data.get('use'), language: 'ja', background: 'light' },
      assets: [
        ...(kind !== 'icons' ? [{ id: 'illustration-01', kind: 'illustration', purpose: data.get('use'), sourceRefs: [], status: 'planned' }] : []),
        ...(kind !== 'illustration' ? Array.from({ length: 6 }, (_, index) => ({ id: `icon-${String(index + 1).padStart(2, '0')}`, kind: 'icon', purpose: 'テーマに合う対象と行動を伝える', sourceRefs: [], status: 'planned' })) : [])
      ]
    };
    output.value = `$taskobo-illustration を使い、次の条件で企業向けの素材を制作する。\n\n内容テーマ：${topic}\n用途：${data.get('use')}\n制作物：${kind === 'both' ? 'メインイラスト1点と、内容から選ぶテーマ別アイコン6点' : kind === 'icons' ? '内容から選ぶテーマ別アイコン6点' : 'メインイラスト1点'}\n画風：${directionNames[direction]}。アイコンは一貫した輪郭と塗りで整える。\n配色：${colorMode === 'document' ? '提供文書のテーマ定義と実際の用色を確認し、根拠を示して提案する。文書がない場合は必要な資料を確認する。' : `${names[colorMode]}。主色 ${primary}、濃色 #0D2046、背景 #FCFBF8。`}\n\n内容テーマ、画風、色系を分けて扱う。文書を添付した場合はページ・段落の根拠を示して挿絵計画を立て、推測を事実として描かない。業務上の数値や効果を創作しない。\nメインイラストは高解像度画像、図形として編集できるアイコンは独立SVGと透明PNGで納品する。ビットマップ画像をSVGと呼ばない。小サイズで確認し、全体一覧、配色、使用上の注意と生成プロンプトを保存する。`;
    document.getElementById('download-brief').disabled = false;
    if (announce) resultStatus.textContent = '依頼文を更新した。画像の生成は、Skillを導入したAIで実行する。';
    return true;
  }
  form.addEventListener('submit', event => { event.preventDefault(); createBrief(); });
  palette.addEventListener('change', updateColor);
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
    a.href = url; a.download = 'taskobo-illustration-brief.json'; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    resultStatus.textContent = '制作ブリーフのJSONを保存した。利用中のAIに依頼文と一緒に渡せる。';
  });
  updateColor(); createBrief(false);
})();
