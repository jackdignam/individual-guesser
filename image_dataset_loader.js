/* Robust loader for the renamed BMW JSON dataset. */
const PAINT_DATA_URL = 'bmw_individual_colours_complete_five_models_with_images.json';
const BMW_MODEL_ALLOWLIST = new Set([
  'm340i', 'm340i touring', 'm3', 'm3 competition sedan', 'm3 competition touring',
  '4 series coupe', '4 series cabrio', 'm440i', 'm4 competition',
  'm4 competition cabrio', 'm440i gran coupe', 'i4', 'i4 m50', 'm2 coupe'
]);

function normaliseModel(value) {
  return String(value || '')
    .normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/^bmw\s+/, '')
    .replace(/[^a-z0-9]+/g, ' ').trim().replace(/\s+/g, ' ');
}

function getField(row, names) {
  for (const name of names) {
    if (row && row[name] != null && String(row[name]).trim()) return row[name];
  }
  return '';
}

function normaliseUrl(value) {
  if (!value) return '';
  let url = String(value).trim();
  if (url.startsWith('https//')) url = `https://${url.slice(8)}`;
  else if (url.startsWith('http//')) url = `http://${url.slice(7)}`;
  else if (url.startsWith('https:/') && !url.startsWith('https://')) url = url.replace(/^https:\/+/,'https://');
  else if (url.startsWith('http:/') && !url.startsWith('http://')) url = url.replace(/^http:\/+/,'http://');
  return url;
}

function normaliseFinish(value, name) {
  const type = `${value || ''} ${name || ''}`.toLowerCase();
  if (type.includes('frozen') || type.includes('matte')) return 'matte';
  if (type.includes('pearl') || type.includes('effect')) return 'pearl';
  if (type.includes('uni') || type.includes('uniflat') || type.includes('solid')) return 'solid';
  return 'metallic';
}

function inferIndividual(name, modelUrl) {
  return /individual/i.test(`${name} ${modelUrl}`);
}

function inferMColour(name) { return /^m\s/i.test(String(name || '')); }
function firstYear(code) { return { A15:2010, A90:2013, A96:2010, C38:2019, C56:2021, P28:2019, P9A:2019, P9C:2019, P9G:2019 }[code] || 2019; }

function collapsePaintRows(rows) {
  const groups = new Map();
  rows.forEach((row) => {
    const code = String(getField(row, ['paintcode','paint_code','paintCode','code','paint_id'])).trim();
    if (!code) return;
    if (!groups.has(code)) groups.set(code, []);
    groups.get(code).push(row);
  });

  return [...groups.entries()].flatMap(([code, group]) => {
    const eligibleRows = group.filter((row) => BMW_MODEL_ALLOWLIST.has(normaliseModel(getField(row, ['model']))));
    if (!eligibleRows.length) return [];

    // Use media and paint metadata from an allowed-model record only. A shared
    // paint code may also have records for models outside the allowlist.
    const eligibleGroup = eligibleRows;
    const first = eligibleGroup[0];
    const name = String(getField(first, ['paintname','paint_name','paintName','official_name','name']) || code).trim();
    const modelUrl = normaliseUrl(getField(first, ['modelurl','model_url','modelUrl','visualizer_url']));
    const videoUrl = normaliseUrl(getField(first, ['videourl','video_url','videoUrl','allvideourls','all_video_urls']));
    const imageUrl = normaliseUrl(getField(first, ['staticimageurl','static_image_url','staticImageUrl','image_url','imageUrl']));
    const individual = inferIndividual(name, modelUrl);

    return {
      paint_id: code, code, official_name: name,
      finish: normaliseFinish(getField(first, ['painttype','paint_type','paintType','finish']), name),
      color_family: String(getField(first, ['color_family','colour_family']) || 'Unreviewed').trim(),
      color_family_source: String(getField(first, ['color_family_source']) || 'unreviewed').trim(),
      color_family_status: String(getField(first, ['color_family_status']) || 'unreviewed').trim(),
      image_review_status: String(getField(first, ['image_review_status']) || 'unreviewed').trim(),
      type: individual ? 'individual' : 'factory',
      is_m_color: inferMColour(name), is_individual: individual,
      first_year_offered: firstYear(code), video_url: videoUrl, image_url: imageUrl,
      visualizer_url: modelUrl, models: [...new Set(eligibleGroup.map((r) => getField(r, ['model'])).filter(Boolean))],
      model_records: eligibleGroup, has_video: Boolean(videoUrl), has_image: Boolean(imageUrl), synonyms: []
    }];
  });
}

async function loadPaintDataset() {
  const response = await fetch(PAINT_DATA_URL, { cache: 'no-store' });
  if (!response.ok) throw new Error(`Dataset request failed: ${response.status}`);
  const raw = await response.json();
  const rows = Array.isArray(raw) ? raw : raw.data || raw.colours || raw.colors || raw.records || [];
  if (!rows.length) throw new Error('No paint records found in the JSON file.');
  return collapsePaintRows(rows);
}
