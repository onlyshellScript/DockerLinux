function normalizeText(value) {
  if (value === null || value === undefined) return null;
  let text = String(value).trim().toLowerCase();
  text = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  text = text.replace(/\s+/g, ' ').trim();
  return text;
}
module.exports = { normalizeText };
