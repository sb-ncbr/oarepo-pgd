import { useFormikContext } from "formik";
import { useSelector } from "react-redux";
import { useFormConfig } from "@js/oarepo_ui/forms";
import { checkDeposit, storedKey } from "./logic.mjs";

/**
 * Configuration, uploaded files and the current check result for the deposit form.
 * The configuration comes with the form config, where DepositionProfilesComponent
 * puts it; it is undefined when the host has not added that component.
 */
export function useDepositionCheck(record) {
  const { values } = useFormikContext();
  const uploaded = useSelector((state) => state.files?.entries);
  const configuration = useFormConfig().config?.deposition_profiles;

  const inventory = uploaded ?? record?.files?.entries ?? [];
  const entries = Array.isArray(inventory)
    ? inventory
    : Object.entries(inventory).map(([key, value]) => ({ ...value, key }));
  // Annotations name files by the key the repository stores, which the check on the server uses.
  const name = (file) => storedKey(file.key ?? file.name, file.links);
  // Files still uploading are listed but do not count until they finish.
  const present = new Set(entries.map(name).filter(Boolean));
  const keys = [...new Set(entries.filter((file) => !file.status || ["finished", "completed"].includes(file.status))
    .map(name).filter(Boolean))];

  const metadata = values.metadata ?? {};
  const filesEnabled = values.files?.enabled ?? true;
  const result = configuration ? checkDeposit(configuration, metadata, keys) : { errors: [], counts: {}, states: {} };
  return { configuration, metadata, filesEnabled, present, keys, result };
}
