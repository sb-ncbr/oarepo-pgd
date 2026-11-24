// Profile-guided deposition, deposit-form side.
//
// The plugin puts these components into the standard tabbed deposit form by
// itself. A host with its own form layout composes them instead:
//
//   import { withProfiles } from "@js/oarepo_pgd";
//   const sections = withProfiles(RDMCompleteSections);
export { ProfileFields } from "./ProfileFields";
export { useDepositionCheck } from "./hooks";
export { checkDeposit, countNotation, suggestType } from "./logic.mjs";
export { withProfiles } from "./sections";
