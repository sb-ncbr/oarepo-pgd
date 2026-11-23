// Catalogues of the form texts. Keys are the English texts, so English needs
// only its plural forms. Czech uses i18next's v3 plural suffixes (_0, _1, _2);
// another language is added the same way.
import TRANSLATE_CS from "./cs/translations.json";
import TRANSLATE_EN from "./en/translations.json";

export const translations = {
  cs: { translation: TRANSLATE_CS },
  en: { translation: TRANSLATE_EN },
};
