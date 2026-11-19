/**
 * A minimal `t` over one catalogue, for the tests, which run without i18next. It
 * follows i18next's v3 conventions used by the plugin's catalogues: a missing
 * key falls back to the key, `count !== 1` selects the `_plural` entry, and
 * {{name}} placeholders are filled in.
 */
export function translator(catalogue = {}) {
  return (message, params = {}) => {
    const plural = params.count !== undefined && params.count !== 1 ? catalogue[`${message}_plural`] : undefined;
    const template = plural ?? catalogue[message] ?? message;
    return template.replace(/\{\{\s*(\w+)\s*\}\}/g, (match, name) => (name in params ? String(params[name]) : match));
  };
}
