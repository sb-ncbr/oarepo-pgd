// Catalogues of the form texts. Keys are the English texts, so English needs
// only its plural forms. A repository can add a language here, e.g. cs, with
// a translations.json using i18next's v3 plural suffixes (_0, _1, _2).
import TRANSLATE_EN from "./en/translations.json";

export const translations = {
  en: { translation: TRANSLATE_EN },
};
