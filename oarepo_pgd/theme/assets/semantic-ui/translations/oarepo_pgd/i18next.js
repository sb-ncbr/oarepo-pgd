// The plugin's own i18next instance: the language comes from the page's
// <html lang>, English is the fallback, and keys are the English texts.
// It stays private: the plugin's components call its t() directly, and it is
// not registered with react-i18next, whose single default instance belongs to
// the repository's own texts.
import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { translations } from "./messages";

const i18next = i18n.createInstance();
i18next
  .use(LanguageDetector)
  .init({
    // Load the bundled catalogues synchronously, so the first t() calls are translated.
    initImmediate: false,
    fallbackLng: "en",
    returnEmptyString: false,
    resources: translations,
    keySeparator: false,
    nsSeparator: false,
    // React escapes rendered text; escaping here too would show "&#x2F;" in file names.
    interpolation: { escapeValue: false },
    detection: { order: ["htmlTag"], caches: [] },
  });

// Bound to the instance; it follows a change of language.
const t = i18next.getFixedT(null);

export { i18next, t };
